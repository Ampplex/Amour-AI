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
_ROTATION_LOCK = threading.Lock()
_GROQ_KEY_ROTATION_IDX = 0
DEFAULT_COOLDOWN_SECONDS = 60.0
SHORT_RATE_LIMIT_RETRY_MAX_SECONDS = 2.5

_DURATION_PART_RE = re.compile(r"(\d+(?:\.\d+)?)(ms|h|m(?!s)|s)")
_DURATION_FULL_RE = re.compile(r"^(?:\d+(?:\.\d+)?(?:ms|h|m(?!s)|s))+$")


def _parse_retry_after_seconds(value) -> float | None:
    """Parse numeric or Go-style duration headers (e.g. '968ms', '42.265s', '1m30s') into seconds."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return max(0.1, float(value))

    raw = str(value).strip().lower()
    if not raw:
        return None

    try:
        return max(0.1, float(raw))
    except (ValueError, TypeError):
        pass

    compact = re.sub(r"\s+", "", raw)
    if not _DURATION_FULL_RE.fullmatch(compact):
        return None

    total_seconds = 0.0
    for amount_str, unit in _DURATION_PART_RE.findall(compact):
        amount = float(amount_str)
        if unit == "ms":
            total_seconds += amount / 1000.0
        elif unit == "s":
            total_seconds += amount
        elif unit == "m":
            total_seconds += amount * 60.0
        elif unit == "h":
            total_seconds += amount * 3600.0
    return max(0.1, total_seconds) if total_seconds > 0 else None


def _select_rate_limit_reset_value(headers: dict | None):
    """Choose the relevant reset header, preferring retry-after or token reset on TPM exhaustion."""
    if not headers:
        return None
    normalized = {str(k).lower(): v for k, v in headers.items() if v is not None}

    retry_after = normalized.get("retry-after")
    if retry_after is not None and str(retry_after).strip():
        return retry_after

    rem_req = normalized.get("x-ratelimit-remaining-requests")
    if rem_req is not None and str(rem_req).strip() == "0":
        return normalized.get("x-ratelimit-reset-requests") or normalized.get("x-ratelimit-reset-tokens")

    return normalized.get("x-ratelimit-reset-tokens") or normalized.get("x-ratelimit-reset-requests")


def _rotate_api_keys(keys: list[str]) -> list[str]:
    """Return API keys rotated round-robin so traffic spreads evenly across the key pool."""
    global _GROQ_KEY_ROTATION_IDX
    if len(keys) <= 1:
        return list(keys)
    with _ROTATION_LOCK:
        start = _GROQ_KEY_ROTATION_IDX % len(keys)
        _GROQ_KEY_ROTATION_IDX = (_GROQ_KEY_ROTATION_IDX + 1) % len(keys)
    return list(keys[start:]) + list(keys[:start])


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
    """Record an HTTP 429 for a model, parse retry-after/reset header, and return cooldown."""
    cooldown = DEFAULT_COOLDOWN_SECONDS
    reset_val = _select_rate_limit_reset_value(headers)
    parsed = _parse_retry_after_seconds(reset_val)
    if parsed is not None:
        cooldown = parsed

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


def _post_openai_compatible_completion(
    *,
    provider: str,
    llm_base_url: str,
    current_model: str,
    api_key_attempt: str,
    messages: list,
    max_tokens: int,
    temperature: float,
    frequency_penalty: float,
    presence_penalty: float,
) -> tuple[str, str | float | None]:
    """Execute one OpenAI/Groq completion attempt and record usage/429 observability."""
    key_id = api_key_attempt[-8:] if len(api_key_attempt) >= 8 else api_key_attempt
    cooldown_key = f"{current_model}:{key_id}"
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
        cd = record_model_rate_limit(llm_base_url, cooldown_key, resp.headers)
        logger.warning(
            "Groq key ...%s hit 429 rate limit (cooling for %.2fs); failing over to next key for %s",
            key_id,
            cd,
            current_model,
        )
        return "rate_limited", cd

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
        logger.warning(
            "Model %s returned HTTP %s with key ...%s: %s",
            current_model,
            resp.status_code,
            key_id,
            resp.text[:300],
        )
        return "error", None

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
    logger.info(
        "Model %s responded in %.2fs (%s chars) via key ...%s",
        current_model,
        duration,
        len(raw_text),
        key_id,
    )
    return ("ok", raw_text) if raw_text else ("error", None)


def _call_openai_compatible_with_keys(
    *,
    provider: str,
    llm_base_url: str,
    current_model: str,
    api_keys: list[str],
    messages: list,
    max_tokens: int,
    temperature: float,
    frequency_penalty: float,
    presence_penalty: float,
) -> str | None:
    """Try rotated keys for an OpenAI/Groq model, retrying once if shortest cooldown is <= 2.5s."""
    rotated_keys = _rotate_api_keys(api_keys) if provider == "groq" else list(api_keys)
    waited_seconds = 0.0

    for pass_idx in range(2):
        shortest_cooldown = None
        hit_rate_limit = False

        for api_key_attempt in rotated_keys:
            key_id = api_key_attempt[-8:] if len(api_key_attempt) >= 8 else api_key_attempt
            cooldown_key = f"{current_model}:{key_id}"
            key_cooldown = get_model_rate_limit_cooldown(llm_base_url, cooldown_key)

            # Skip keys still in cooldown (allowing pass 2 retry if we already slept past it)
            if key_cooldown > 0 and (pass_idx == 0 or key_cooldown > waited_seconds):
                logger.info("Groq key ...%s in cooldown for %.2fs; trying next key", key_id, key_cooldown)
                hit_rate_limit = True
                shortest_cooldown = key_cooldown if shortest_cooldown is None else min(shortest_cooldown, key_cooldown)
                continue

            outcome, result = _post_openai_compatible_completion(
                provider=provider,
                llm_base_url=llm_base_url,
                current_model=current_model,
                api_key_attempt=api_key_attempt,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
            )
            if outcome == "ok" and isinstance(result, str):
                with _COOLDOWN_LOCK:
                    _RATE_LIMIT_COOLDOWNS.pop(f"{llm_base_url}:{cooldown_key}", None)
                return result
            if outcome == "rate_limited" and isinstance(result, float):
                hit_rate_limit = True
                shortest_cooldown = result if shortest_cooldown is None else min(shortest_cooldown, result)

        if (
            pass_idx == 0
            and hit_rate_limit
            and shortest_cooldown is not None
            and 0 < shortest_cooldown <= SHORT_RATE_LIMIT_RETRY_MAX_SECONDS
        ):
            waited_seconds = shortest_cooldown + 0.05
            logger.info("All %s keys briefly rate-limited; waiting %.2fs before retry", current_model, waited_seconds)
            time.sleep(waited_seconds)
            continue
        break

    return None


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
                # OpenAI / Groq compatible completions with round-robin multi-key 429 failover
                api_keys_to_try = get_groq_api_keys() if provider == "groq" else [llm_api_key]
                if not api_keys_to_try and llm_api_key:
                    api_keys_to_try = [llm_api_key]

                raw_text = _call_openai_compatible_with_keys(
                    provider=provider,
                    llm_base_url=llm_base_url,
                    current_model=current_model,
                    api_keys=api_keys_to_try,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    frequency_penalty=frequency_penalty,
                    presence_penalty=presence_penalty,
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
