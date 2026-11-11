"""
LLM Client handling Amazon Bedrock Converse API, Groq, and OpenAI-compatible providers,
with transparent rate-limit cooldown tracking and model failover.
"""

import os
import re
import time
import logging
import threading
from urllib.parse import urlparse

import requests
import boto3
from botocore.exceptions import ClientError
from django.conf import settings

logger = logging.getLogger("amour.llm_client")

_RATE_LIMIT_COOLDOWNS: dict[str, float] = {}
_COOLDOWN_LOCK = threading.Lock()
DEFAULT_COOLDOWN_SECONDS = 60.0


def get_model_rate_limit_cooldown(endpoint: str, model_id: str) -> float:
    """Return remaining cooldown seconds for a model at endpoint, or 0.0 if available."""
    key = f"{endpoint}:{model_id}"
    with _COOLDOWN_LOCK:
        expires_at = _RATE_LIMIT_COOLDOWNS.get(key, 0.0)
        remaining = expires_at - time.time()
        if remaining <= 0:
            _RATE_LIMIT_COOLDOWNS.pop(key, None)
            return 0.0
        return remaining


def record_model_rate_limit(
    endpoint: str,
    model_id: str,
    headers: dict | None = None,
) -> float:
    """Record an HTTP 429 for a model, parse retry-after header if present, and return cooldown."""
    cooldown = DEFAULT_COOLDOWN_SECONDS
    if headers:
        retry_after = (
            headers.get("retry-after")
            or headers.get("Retry-After")
            or headers.get("x-ratelimit-reset-requests")
            or headers.get("x-ratelimit-reset-tokens")
        )
        if retry_after:
            try:
                cooldown = max(1.0, float(retry_after))
            except (ValueError, TypeError):
                pass

    key = f"{endpoint}:{model_id}"
    with _COOLDOWN_LOCK:
        _RATE_LIMIT_COOLDOWNS[key] = time.time() + cooldown
    return cooldown


def get_llm_configuration() -> tuple[str, str, list[str]]:
    """
    Resolve API key, endpoint, and fallback model chain.
    Defaults to Bedrock Mistral Large v1.
    """
    provider = (
        getattr(settings, "LLM_PROVIDER", "")
        or os.environ.get("LLM_PROVIDER", "bedrock")
    ).strip().lower()

    if provider == "groq":
        api_key = getattr(settings, "GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
        base_url = "https://api.groq.com/openai/v1"
        configured_models = (
            getattr(settings, "GROQ_CHAT_MODELS", None)
            or os.environ.get("GROQ_CHAT_MODELS", "")
        )
        if configured_models:
            if isinstance(configured_models, str):
                models_to_try = [m.strip() for m in configured_models.split(",") if m.strip()]
            else:
                models_to_try = list(configured_models)
        else:
            primary = (
                getattr(settings, "GROQ_CHAT_MODEL", "")
                or os.environ.get("GROQ_CHAT_MODEL", "llama-3.3-70b-versatile")
            ).strip()
            models_to_try = [primary] if primary else ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]

    elif provider in ("openai", "openai_compatible"):
        api_key = getattr(settings, "OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
        base_url = (
            getattr(settings, "OPENAI_BASE_URL", "")
            or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        ).strip().rstrip("/")
        primary = (
            getattr(settings, "OPENAI_CHAT_MODEL", "")
            or os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o")
        ).strip()
        models_to_try = [primary] if primary else ["gpt-4o"]

    else:
        # Default: Amazon Bedrock Converse API
        aws_region = (
            getattr(settings, "AWS_REGION", "")
            or os.environ.get("AWS_REGION", "us-west-2")
        ).strip()
        base_url = f"https://bedrock-runtime.{aws_region}.amazonaws.com"
        api_key = (
            getattr(settings, "BEDROCK_API_KEY", "")
            or os.environ.get("BEDROCK_API_KEY", "")
        ).strip()

        configured_models = (
            getattr(settings, "BEDROCK_MODEL_IDS", None)
            or os.environ.get("BEDROCK_MODEL_IDS", "")
        )
        if configured_models:
            if isinstance(configured_models, str):
                models_to_try = [m.strip() for m in configured_models.split(",") if m.strip()]
            else:
                models_to_try = list(configured_models)
        else:
            primary = (
                getattr(settings, "BEDROCK_MODEL_ID", "")
                or os.environ.get("BEDROCK_MODEL_ID", "mistral.mistral-large-2407-v1:0")
            ).strip()
            models_to_try = [primary] if primary else ["mistral.mistral-large-2407-v1:0"]

    return api_key, base_url, models_to_try


def prepare_bedrock_converse_messages(messages: list) -> tuple[list[dict], list[dict]]:
    """Convert OpenAI-style message list to Bedrock Converse format (system + conversation)."""
    system_blocks = []
    conversation = []

    for item in messages:
        role = item.get("role")
        content = item.get("content", "")
        if not isinstance(content, str) or not content.strip():
            continue

        if role == "system":
            system_blocks.append({"text": content.strip()})
        elif role in ("user", "assistant"):
            if conversation and conversation[-1]["role"] == role:
                conversation[-1]["content"].append({"text": content.strip()})
            else:
                conversation.append({
                    "role": role,
                    "content": [{"text": content.strip()}],
                })

    while conversation and conversation[0]["role"] == "assistant":
        conversation.pop(0)

    if not conversation:
        conversation.append({"role": "user", "content": [{"text": "Hello"}]})
    elif conversation[-1]["role"] != "user":
        # Bedrock requires the last message to be user
        conversation.append({"role": "user", "content": [{"text": "Please continue."}]})

    return system_blocks, conversation


def call_llm(
    messages: list,
    max_tokens: int = 1024,
    temperature: float = 0.88,
) -> tuple[str | None, str | None]:
    """
    Direct LLM call with fallback model chain.
    Returns (raw_reply_text, model_name) or (None, None) on total failure.
    """
    llm_api_key, llm_base_url, models_to_try = get_llm_configuration()
    is_bedrock = (urlparse(llm_base_url).hostname or "").startswith("bedrock-runtime.")

    for current_model in models_to_try:
        cooldown = get_model_rate_limit_cooldown(llm_base_url, current_model)
        if cooldown > 0:
            logger.info("Skipping model %s; in cooldown for %.1fs", current_model, cooldown)
            continue

        try:
            if is_bedrock:
                parsed_url = urlparse(llm_base_url)
                hostname = parsed_url.hostname or ""
                match = re.fullmatch(r"bedrock-runtime\.([a-z0-9-]+)\.amazonaws\.com", hostname)
                region = match.group(1) if match else "us-west-2"

                system_blocks, conversation = prepare_bedrock_converse_messages(messages)
                client = boto3.client("bedrock-runtime", region_name=region)

                start_time = time.time()
                response = client.converse(
                    modelId=current_model,
                    system=system_blocks,
                    messages=conversation,
                    inferenceConfig={
                        "maxTokens": max_tokens,
                        "temperature": temperature,
                        "topP": 0.9,
                    },
                )
                duration = time.time() - start_time

                content_blocks = (
                    response.get("output", {})
                    .get("message", {})
                    .get("content", [])
                )
                raw_text = "".join(
                    block.get("text", "")
                    for block in content_blocks
                    if isinstance(block, dict) and isinstance(block.get("text"), str)
                ).strip()

                logger.info(
                    "Bedrock model %s responded in %.2fs (%s chars)",
                    current_model,
                    duration,
                    len(raw_text),
                )
                if raw_text:
                    return raw_text, current_model

            else:
                # OpenAI / Groq compatible completions
                headers = {
                    "Authorization": f"Bearer {llm_api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": current_model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": min(max_tokens, 768 if "groq" in llm_base_url else max_tokens),
                    "frequency_penalty": 0.5,
                    "presence_penalty": 0.5,
                    "top_p": 0.9,
                }
                url = f"{llm_base_url}/chat/completions"

                start_time = time.time()
                resp = requests.post(url, headers=headers, json=payload, timeout=25)
                duration = time.time() - start_time

                if resp.status_code == 429:
                    cd = record_model_rate_limit(llm_base_url, current_model, resp.headers)
                    logger.warning("Model %s hit 429; cooling down for %.1fs", current_model, cd)
                    continue

                if resp.status_code != 200:
                    logger.warning(
                        "Model %s returned HTTP %s: %s",
                        current_model,
                        resp.status_code,
                        resp.text[:300],
                    )
                    continue

                data = resp.json()
                raw_text = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    .strip()
                )
                logger.info(
                    "Model %s responded in %.2fs (%s chars)",
                    current_model,
                    duration,
                    len(raw_text),
                )
                if raw_text:
                    return raw_text, current_model

        except ClientError as exc:
            err_code = exc.response.get("Error", {}).get("Code", "")
            if err_code in ("ThrottlingException", "TooManyRequestsException", "ServiceQuotaExceededException"):
                cd = record_model_rate_limit(llm_base_url, current_model)
                logger.warning("Bedrock model %s throttled (%s); cooldown %.1fs", current_model, err_code, cd)
            else:
                logger.error("Bedrock ClientError for %s: %s", current_model, exc)
            continue
        except Exception as exc:
            logger.exception("Unexpected error calling LLM model %s: %s", current_model, exc)
            continue

    return None, None
