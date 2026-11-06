"""
LLM Client Module for Amour Companion Inference.

Provides dual-tier LLM inference with:
- Primary: AWS Bedrock Mistral Large 2 (mistral.mistral-large-2407-v1:0) via Converse API
- Automated Failover: Groq LPUs (qwen/qwen3.8-27b / gpt-oss-120b)
- Pydantic-powered robust JSON response parsing & validation
"""

import os
import re
import time
import json
import logging
import boto3
from botocore.config import Config
from pydantic import BaseModel, Field, field_validator
from django.conf import settings

logger = logging.getLogger("amour.llm")

# AWS Bedrock Client Cache
_bedrock_client = None


def get_bedrock_runtime_client():
    """Initializes and returns cached AWS Bedrock Runtime client."""
    global _bedrock_client
    if _bedrock_client is not None:
        return _bedrock_client

    region = os.getenv("AWS_REGION") or getattr(settings, "AWS_REGION", "us-west-2")
    access_key = os.getenv("AWS_ACCESS_KEY_ID") or getattr(settings, "AWS_ACCESS_KEY_ID", None)
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY") or getattr(settings, "AWS_SECRET_ACCESS_KEY", None)

    cfg = Config(
        region_name=region,
        retries={"max_attempts": 2, "mode": "standard"},
        connect_timeout=5,
        read_timeout=25,
    )

    client_kwargs = {"service_name": "bedrock-runtime", "config": cfg}
    if access_key and secret_key:
        client_kwargs["aws_access_key_id"] = access_key
        client_kwargs["aws_secret_access_key"] = secret_key

    try:
        _bedrock_client = boto3.client(**client_kwargs)
        return _bedrock_client
    except Exception as exc:
        logger.warning(f"Failed to initialize AWS Bedrock client: {exc}")
        return None


def normalize_bedrock_messages(raw_messages: list, persona_name: str = "Companion") -> list:
    """
    Normalize canonical sender/text turns for Bedrock Converse.

    Consecutive roles are merged. Assistant-first history gets a neutral
    continuation marker rather than an invented scene-opening action.
    """
    normalized = []
    for item in raw_messages or []:
        if not isinstance(item, dict):
            continue

        sender = (item.get("sender") or item.get("role") or "").strip().lower()
        if sender in {"bot", "assistant", "ai", "companion"}:
            role = "assistant"
        elif sender in {"user", "human"}:
            role = "user"
        else:
            logger.warning("[Bedrock History] Skipping unknown sender: %s", sender or "<empty>")
            continue

        text = item.get("text")
        if text is None:
            text = item.get("content", "")
        if not isinstance(text, str) or not text.strip():
            continue
        text = text.strip()

        if normalized and normalized[-1]["role"] == role:
            normalized[-1]["content"][0]["text"] += "\n\n" + text
        else:
            normalized.append({"role": role, "content": [{"text": text}]})

    if not normalized:
        return [{"role": "user", "content": [{"text": "Hello"}]}]

    if normalized[0]["role"] == "assistant":
        normalized.insert(0, {
            "role": "user",
            "content": [{
                "text": (
                    f"The conversation with {persona_name} is already underway. "
                    "The following assistant message is previously delivered context. "
                    "Continue from it; do not restart or reenact the opening scene."
                )
            }]
        })
    return normalized

def call_bedrock_mistral_large(system_prompt: str, messages: list) -> str | None:
    """
    Executes inference against AWS Bedrock Mistral Large 2 (mistral.mistral-large-2407-v1:0)
    using the Converse API. Returns the raw output text or None on failure.
    """
    client = get_bedrock_runtime_client()
    if not client:
        return None

    target_model = getattr(settings, "BEDROCK_MODEL_ID", "mistral.mistral-large-2407-v1:0")

    try:
        start_t = time.time()
        system_prompts = [{"text": system_prompt}]
        inference_config = {
            "maxTokens": 750,
            "temperature": 0.8,
            "topP": 0.9,
        }

        resp = client.converse(
            modelId=target_model,
            messages=messages,
            system=system_prompts,
            inferenceConfig=inference_config,
        )
        duration = time.time() - start_t

        output_msg = resp.get("output", {}).get("message", {})
        content_blocks = output_msg.get("content", [])
        if content_blocks and "text" in content_blocks[0]:
            raw_text = content_blocks[0]["text"].strip()
            logger.info(f"[Bedrock Mistral Large] Model: {target_model} | Duration: {duration:.2f}s | Length: {len(raw_text)}")
            return raw_text
    except Exception as exc:
        logger.warning(f"[Bedrock Mistral Large] Inference failed: {exc}")
    return None


def call_groq_fallback(
    system_prompt: str,
    messages: list,
    model: str = "qwen/qwen3.8-27b",
    max_tokens: int = 750,
    temperature: float = 0.8,
) -> str | None:
    """
    Automated failover to Groq LPUs when AWS Bedrock hits rate limits or latency spikes.
    """
    groq_api_key = getattr(settings, "GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
    llm_base_url = (getattr(settings, "LLM_BASE_URL", "") or os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1")).rstrip("/")

    if not groq_api_key:
        return None

    import urllib.request
    try:
        url = f"{llm_base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {groq_api_key}",
        }

        # Convert Converse messages format to OpenAI format
        openai_msgs = [{"role": "system", "content": system_prompt}]
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", [])
            text = content[0].get("text", "") if content else ""
            openai_msgs.append({"role": role, "content": text})

        payload = {
            "model": model,
            "messages": openai_msgs,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        start_t = time.time()
        with urllib.request.urlopen(req, timeout=12) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            duration = time.time() - start_t
            raw_text = res_data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            logger.info(f"[Groq LPU Failover] Model: {model} | Duration: {duration:.2f}s | Length: {len(raw_text)}")
            return raw_text
    except Exception as exc:
        logger.warning(f"[Groq LPU Failover] Failed: {exc}")
        return None


class CompanionReplyPayload(BaseModel):
    """Pydantic model validating companion reply JSON output."""
    reply: str = Field(default="")
    conflict_stage: int = Field(default=0)

    @field_validator("conflict_stage", mode="before")
    @classmethod
    def validate_conflict_stage(cls, v):
        try:
            val = int(v)
            return max(0, min(3, val))
        except (ValueError, TypeError):
            return 0

    @field_validator("reply", mode="before")
    @classmethod
    def validate_reply(cls, v):
        if v is None:
            return ""
        return str(v).strip()


def parse_memory_store_decision(raw_content: str) -> bool:
    """Read the LLM's strict boolean memory decision from its chat-response JSON.

    Missing, malformed, or non-boolean metadata fails closed. This does not
    make a second model call and contains no keyword/category decision rules.
    """
    if not raw_content or not raw_content.strip():
        return False

    text = raw_content.strip()
    decoder = json.JSONDecoder()
    candidates = []

    try:
        value = json.loads(text)
        if isinstance(value, str):
            value = json.loads(value)
        if isinstance(value, dict):
            candidates.append(value)
    except (json.JSONDecodeError, TypeError):
        pass

    if not candidates:
        for index, char in enumerate(text):
            if char != "{":
                continue
            try:
                value, _end = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                candidates.append(value)
                break

    for candidate in candidates:
        decision = candidate.get("remember_user_fact")
        if isinstance(decision, bool):
            return decision
    return False


def parse_model_json_reply(raw_content: str, default_conflict_stage: int = 0) -> tuple[str, int]:
    """
    Return only the user-facing companion reply and its internal conflict stage.

    Models sometimes wrap the JSON in Markdown, prepend explanatory text, or
    append a second JSON envelope after the prose. Search for a valid payload
    instead of returning the raw model output (which can leak JSON into chat).
    """
    if not raw_content or not raw_content.strip():
        return "", default_conflict_stage

    text = raw_content.strip()
    decoder = json.JSONDecoder()

    def validated_payload(value):
        if isinstance(value, str):
            # Some providers double-encode the JSON object as a JSON string.
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return None
        if not isinstance(value, dict) or "reply" not in value:
            return None
        try:
            return CompanionReplyPayload.model_validate(value)
        except Exception:
            return None

    # First try the complete response, including a normal JSON string response.
    try:
        parsed = validated_payload(json.loads(text))
        if parsed and parsed.reply:
            return parsed.reply, parsed.conflict_stage
    except (json.JSONDecodeError, TypeError):
        pass

    # Then scan for complete JSON objects inside Markdown fences or surrounding
    # explanatory prose. A valid {"reply": ..., "conflict_stage": ...} wins.
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        parsed = validated_payload(value)
        if parsed and parsed.reply:
            return parsed.reply, parsed.conflict_stage

    # Handle a truncated outer object when the reply value itself is complete.
    # JSONDecoder safely unescapes quotes/newlines without unicode_escape damage.
    reply_key = re.search(r'"reply"\s*:\s*', text)
    if reply_key:
        value_start = reply_key.end()
        try:
            reply_value, _end = decoder.raw_decode(text[value_start:])
            if isinstance(reply_value, str) and reply_value.strip():
                stage_match = re.search(r'"conflict_stage"\s*:\s*(-?\d+)', text)
                stage = int(stage_match.group(1)) if stage_match else default_conflict_stage
                stage = max(0, min(3, stage))
                return reply_value.strip(), stage
        except (json.JSONDecodeError, ValueError):
            pass

    # Never show a malformed JSON envelope, schema keys, or Markdown JSON fence
    # to the user. Plain-text provider responses remain a safe last resort.
    looks_structured = (
        text.lstrip().lower().startswith(("{", "[", "```json"))
        or '"conflict_stage"' in text
        or re.search(r'"reply"\s*:', text) is not None
    )
    if looks_structured:
        logger.warning("[LLM Parser] Model returned an invalid companion JSON payload")
        return "", default_conflict_stage

    # Remove generic Markdown fences around a plain-text response, if any.
    plain_text = re.sub(r"^```(?:text)?\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()
    return plain_text, default_conflict_stage
