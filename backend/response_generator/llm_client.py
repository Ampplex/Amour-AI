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

from .observability import extract_token_usage, record_llm_request

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


def get_groq_api_keys() -> list[str]:
    """
    Resolve list of Groq API keys for automatic 429 key failover / rotation.
    Supports comma-separated GROQ_API_KEY, GROQ_API_KEYS list, or GROQ_API_KEY_FALLBACK.
    """
    raw_keys = []

    # 1. GROQ_API_KEYS (e.g. "key1,key2,key3" or list)
    env_keys = os.environ.get("GROQ_API_KEYS", "") or getattr(settings, "GROQ_API_KEYS", None)
    if env_keys:
        if isinstance(env_keys, str):
            raw_keys.extend([k.strip() for k in env_keys.split(",") if k.strip()])
        elif isinstance(env_keys, (list, tuple)):
            raw_keys.extend([str(k).strip() for k in env_keys if str(k).strip()])

    # 2. GROQ_API_KEY (single key or comma-separated)
    primary = os.environ.get("GROQ_API_KEY", "") or getattr(settings, "GROQ_API_KEY", "")
    if primary:
        if isinstance(primary, str) and "," in primary:
            raw_keys.extend([k.strip() for k in primary.split(",") if k.strip()])
        elif str(primary).strip():
            raw_keys.append(str(primary).strip())

    # 3. GROQ_API_KEY_FALLBACK
    fallback = os.environ.get("GROQ_API_KEY_FALLBACK", "") or getattr(settings, "GROQ_API_KEY_FALLBACK", "")
    if fallback:
        if isinstance(fallback, str) and "," in fallback:
            raw_keys.extend([k.strip() for k in fallback.split(",") if k.strip()])
        elif str(fallback).strip():
            raw_keys.append(str(fallback).strip())

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for k in raw_keys:
        if k not in seen:
            seen.add(k)
            unique.append(k)

    return unique


def get_llm_configuration() -> tuple[str, str, list[str]]:
    """
    Resolve API key, endpoint, and fallback model chain.
    Defaults to Groq with qwen/qwen3.8-27b.
    """
    provider = (
        getattr(settings, "RESPONSE_LLM_PROVIDER", "")
        or os.environ.get("RESPONSE_LLM_PROVIDER", "")
        or getattr(settings, "LLM_PROVIDER", "")
        or os.environ.get("LLM_PROVIDER", "groq")
    ).strip().lower()

    if provider == "groq":
        api_key = getattr(settings, "GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
        base_url = (
            getattr(settings, "LLM_BASE_URL", "")
            or os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1")
        ).strip().rstrip("/")
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
                or os.environ.get("GROQ_CHAT_MODEL", "")
                or getattr(settings, "LLM_MODEL", "")
                or os.environ.get("LLM_MODEL", "qwen/qwen3.8-27b")
            ).strip()
            models_to_try = [primary] if primary else ["qwen/qwen3.8-27b"]

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
    frequency_penalty: float = 0.5,
    presence_penalty: float = 0.5,
) -> tuple[str | None, str | None]:
    """
    Direct LLM call with fallback model chain.
    Returns (raw_reply_text, model_name) or (None, None) on total failure.
    """
    llm_api_key, llm_base_url, models_to_try = get_llm_configuration()
    is_bedrock = (urlparse(llm_base_url).hostname or "").startswith("bedrock-runtime.")
    configured_provider = (
        getattr(settings, "RESPONSE_LLM_PROVIDER", "")
        or os.environ.get("RESPONSE_LLM_PROVIDER", "")
        or getattr(settings, "LLM_PROVIDER", "")
        or os.environ.get("LLM_PROVIDER", "groq")
    ).strip().lower()
    provider = "bedrock" if is_bedrock else (
        "groq" if configured_provider == "groq" else "openai_compatible"
    )

    for current_model in models_to_try:
        cooldown = get_model_rate_limit_cooldown(llm_base_url, current_model)
        if cooldown > 0:
            logger.info("Skipping model %s; in cooldown for %.1fs", current_model, cooldown)
            continue

        attempt_started_at = None
        attempt_recorded = False
        try:
            if is_bedrock:
                parsed_url = urlparse(llm_base_url)
                hostname = parsed_url.hostname or ""
                match = re.fullmatch(r"bedrock-runtime\.([a-z0-9-]+)\.amazonaws\.com", hostname)
                region = match.group(1) if match else "us-west-2"

                system_blocks, conversation = prepare_bedrock_converse_messages(messages)
                client = boto3.client("bedrock-runtime", region_name=region)

                attempt_started_at = time.time()
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
                duration = time.time() - attempt_started_at

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
                input_tokens, output_tokens = extract_token_usage(response.get("usage"))
                metadata = response.get("ResponseMetadata", {})
                record_llm_request(
                    provider=provider,
                    model=current_model,
                    status="success" if raw_text else "error",
                    duration_ms=int(duration * 1000),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    response_status=metadata.get("HTTPStatusCode"),
                    error_type="" if raw_text else "EmptyResponse",
                )
                attempt_recorded = True

                logger.info(
                    "Bedrock model %s responded in %.2fs (%s chars)",
                    current_model,
                    duration,
                    len(raw_text),
                )
                if raw_text:
                    return raw_text, current_model

            else:
                # OpenAI / Groq compatible completions with multi-key 429 failover
                api_keys_to_try = get_groq_api_keys() if provider == "groq" else [llm_api_key]
                if not api_keys_to_try and llm_api_key:
                    api_keys_to_try = [llm_api_key]

                for api_key_attempt in api_keys_to_try:
                    key_id = api_key_attempt[-8:] if len(api_key_attempt) >= 8 else api_key_attempt
                    key_cooldown = get_model_rate_limit_cooldown(llm_base_url, key_id)
                    if key_cooldown > 0:
                        logger.info("Groq key ...%s in cooldown for %.1fs; trying next key", key_id, key_cooldown)
                        continue

                    headers = {
                        "Authorization": f"Bearer {api_key_attempt}",
                        "Content-Type": "application/json",
                    }
                    payload = {
                        "model": current_model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": min(max_tokens, 3072),
                        "frequency_penalty": frequency_penalty,
                        "presence_penalty": presence_penalty,
                        "top_p": 0.9,
                    }
                    url = f"{llm_base_url}/chat/completions"

                    attempt_recorded = False
                    attempt_started_at = time.time()
                    resp = requests.post(url, headers=headers, json=payload, timeout=25)
                    duration = time.time() - attempt_started_at

                    if resp.status_code == 429:
                        record_llm_request(
                            provider=provider,
                            model=current_model,
                            status="rate_limited",
                            duration_ms=int(duration * 1000),
                            response_status=resp.status_code,
                            error_type="RateLimit",
                            rate_limit_headers=resp.headers,
                        )
                        attempt_recorded = True
                        cd = record_model_rate_limit(llm_base_url, key_id, resp.headers)
                        logger.warning(
                            "Groq key ...%s hit 429 rate limit (cooling for %.1fs); failing over to next key for %s",
                            key_id,
                            cd,
                            current_model,
                        )
                        continue

                    if resp.status_code != 200:
                        record_llm_request(
                            provider=provider,
                            model=current_model,
                            status="error",
                            duration_ms=int(duration * 1000),
                            response_status=resp.status_code,
                            error_type="HTTPError",
                            rate_limit_headers=resp.headers,
                        )
                        attempt_recorded = True
                        logger.warning(
                            "Model %s returned HTTP %s with key ...%s: %s",
                            current_model,
                            resp.status_code,
                            key_id,
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
                    input_tokens, output_tokens = extract_token_usage(data.get("usage"))
                    record_llm_request(
                        provider=provider,
                        model=current_model,
                        status="success" if raw_text else "error",
                        duration_ms=int(duration * 1000),
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        response_status=resp.status_code,
                        error_type="" if raw_text else "EmptyResponse",
                        rate_limit_headers=resp.headers,
                    )
                    attempt_recorded = True
                    logger.info(
                        "Model %s responded in %.2fs (%s chars) via key ...%s",
                        current_model,
                        duration,
                        len(raw_text),
                        key_id,
                    )
                    if raw_text:
                        return raw_text, current_model

        except ClientError as exc:
            err_code = exc.response.get("Error", {}).get("Code", "")
            if attempt_started_at is not None and not attempt_recorded:
                is_rate_limited = err_code in (
                    "ThrottlingException",
                    "TooManyRequestsException",
                    "ServiceQuotaExceededException",
                )
                record_llm_request(
                    provider=provider,
                    model=current_model,
                    status="rate_limited" if is_rate_limited else "error",
                    duration_ms=int((time.time() - attempt_started_at) * 1000),
                    error_type=err_code or type(exc).__name__,
                )
                attempt_recorded = True
            if err_code in ("ThrottlingException", "TooManyRequestsException", "ServiceQuotaExceededException"):
                cd = record_model_rate_limit(llm_base_url, current_model)
                logger.warning("Bedrock model %s throttled (%s); cooldown %.1fs", current_model, err_code, cd)
            else:
                logger.error("Bedrock ClientError for %s: %s", current_model, err_code)
            continue
        except Exception as exc:
            if attempt_started_at is not None and not attempt_recorded:
                record_llm_request(
                    provider=provider,
                    model=current_model,
                    status="error",
                    duration_ms=int((time.time() - attempt_started_at) * 1000),
                    error_type=type(exc).__name__,
                )
                attempt_recorded = True
            logger.exception("Unexpected error calling LLM model %s: %s", current_model, type(exc).__name__)
            continue

    return None, None
