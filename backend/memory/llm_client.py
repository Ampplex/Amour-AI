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
    Normalizes a list of messages for the AWS Bedrock Converse API:
    1. Roles must strictly alternate: 'user' -> 'assistant' -> 'user' -> ...
    2. The first message must always have role 'user'.
    3. Consecutive messages of the same role are merged.
    """
    if not raw_messages:
        return [{"role": "user", "content": [{"text": "Hello"}]}]

    normalized = []
    for m in raw_messages:
        role = "assistant" if m.get("sender") == "bot" else "user"
        text = (m.get("text") or "").strip()
        if not text:
            continue

        if not normalized:
            if role == "assistant":
                normalized.append({
                    "role": "user",
                    "content": [{"text": f"[Scene begins: {persona_name} approaches]"}]
                })
            normalized.append({"role": role, "content": [{"text": text}]})
        else:
            if normalized[-1]["role"] == role:
                prev_text = normalized[-1]["content"][0]["text"]
                normalized[-1]["content"][0]["text"] = f"{prev_text}\n{text}"
            else:
                normalized.append({"role": role, "content": [{"text": text}]})

    if not normalized:
        return [{"role": "user", "content": [{"text": "Hello"}]}]

    if normalized[0]["role"] != "user":
        normalized.insert(0, {
            "role": "user",
            "content": [{"text": f"[Scene begins: {persona_name} approaches]"}]
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


def parse_model_json_reply(raw_content: str, default_conflict_stage: int = 0) -> tuple[str, int]:
    """
    Parses companion JSON reply using Pydantic, handling markdown fences and LLM formatting quirks.
    """
    if not raw_content:
        return "", default_conflict_stage
    text = raw_content.strip()

    # 1. Strip markdown code fence if present
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence_match:
        text = fence_match.group(1).strip()

    # 2. Extract outermost JSON object {...}
    json_match = re.search(r"\{[\s\S]*\}", text)
    candidate_json = json_match.group(0) if json_match else text

    # 3. Pydantic fast schema validation
    try:
        parsed = CompanionReplyPayload.model_validate_json(candidate_json)
        if parsed.reply:
            return parsed.reply, parsed.conflict_stage
    except Exception:
        pass

    # 4. Fallback regex extraction if JSON is slightly truncated or has unescaped characters
    reply_m = re.search(r'"reply"\s*:\s*"([\s\S]*?)(?<!\\)"', text)
    if reply_m:
        try:
            reply = reply_m.group(1).encode().decode("unicode_escape").strip()
            return reply, default_conflict_stage
        except Exception:
            pass

    return text, default_conflict_stage
