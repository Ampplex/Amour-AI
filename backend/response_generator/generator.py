"""
Main Response Generator Service.

Orchestrates a two-stage narrative pipeline: Story Director planning followed
by final character-response generation. Handles shared prompt assembly,
temporal grounding, structured LLM inference with model failover, output
sanitization, and Reeve memory retrieval/storage.
"""

import os
import re
import time
import json
import logging
import threading
import unicodedata
from copy import deepcopy
from datetime import datetime, timezone as datetime_timezone
from email.utils import parsedate_to_datetime
from typing import Callable
import requests
import boto3
from botocore.exceptions import ClientError
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django.conf import settings
from django.utils import timezone
from pydantic import BaseModel, ValidationError

from memory.reeve_service import (
    store_memory_for_user,
    retrieve_context_for_user,
    deduplicate_context,
)
from .story_director import (
    build_story_director_prompt,
    RESPONSE_GENERATOR_PROMPT,
    StoryDirectorOutput,
    CompanionReplyOutput,
    StoryState,
    STORY_STATE_INITIALIZATION_PROMPT,
)
from .state_patch_validator import (
    PatchValidationError,
    validate_story_state_patch,
)
from .state_patch_applier import (
    StoryStatePatchApplicationError,
    apply_story_state_patch,
)

logger = logging.getLogger("amour.response_generator")

def _get_llm_configuration() -> tuple[str, str, list[str]]:
    """
    Resolve the API key, endpoint and model chain for the selected provider.

    Amazon Bedrock Runtime is the default chat inference provider. Its
    Converse API lets both generation stages
    share the existing request/response parsing code.
    """
    provider = (
        getattr(settings, "LLM_PROVIDER", "")
        or os.environ.get("LLM_PROVIDER", "bedrock")
    ).strip().lower()

    if provider == "bedrock":
        # Reuse the AWS credentials already configured for this application.
        # Boto3 resolves environment credentials, profiles, or attached roles.
        # No separate Bedrock API key or IAM permission changes are introduced.
        api_key = ""
        region = (
            getattr(settings, "AWS_REGION", "")
            or os.environ.get("AWS_REGION")
            or os.environ.get("AWS_DEFAULT_REGION")
            or "us-west-2"
        )
        base_url = f"https://bedrock-runtime.{region}.amazonaws.com"
        primary_model = (
            getattr(settings, "BEDROCK_MODEL_ID", "")
            or os.environ.get(
                "BEDROCK_MODEL_ID",
                "mistral.mistral-large-2402-v1:0",
            )
        )
        fallback_models = getattr(settings, "LLM_FALLBACK_MODELS", ())
        if not fallback_models:
            fallback_models = tuple(
                item.strip()
                for item in os.environ.get(
                    "BEDROCK_FALLBACK_MODEL_IDS",
                    "",
                ).split(",")
                if item.strip()
            )
    elif provider == "groq":
        api_key = (
            getattr(settings, "GROQ_API_KEY", "")
            or os.environ.get("GROQ_API_KEY", "")
        )
        base_url = (
            getattr(settings, "LLM_BASE_URL", "")
            or os.environ.get(
                "GROQ_BASE_URL",
                "https://api.groq.com/openai/v1",
            )
        ).rstrip("/")
        primary_model = (
            getattr(settings, "LLM_MODEL", "")
            or os.environ.get("GROQ_MODEL", "qwen/qwen3.8-27b")
        )
        fallback_models = getattr(settings, "LLM_FALLBACK_MODELS", ())
        if not fallback_models:
            fallback_models = tuple(
                item.strip()
                for item in os.environ.get(
                    "GROQ_FALLBACK_MODELS",
                    "openai/gpt-oss-120b,openai/gpt-oss-20b",
                ).split(",")
                if item.strip()
            )
    else:
        logger.error("Unsupported LLM_PROVIDER: %s", provider)
        return "", "", []

    models = []
    for model in [primary_model, *fallback_models]:
        if model and model not in models:
            models.append(model)

    return api_key, base_url, models


# Rate limits are model-scoped by default because a provider may still allow
# another model while one model's request/token quota is exhausted. Cooldowns
# live for the lifetime of this process and prevent repeated requests from
# hammering a model that has just returned HTTP 429.
DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS = 30.0
MAX_RATE_LIMIT_COOLDOWN_SECONDS = 900.0
_RATE_LIMIT_COOLDOWNS: dict[tuple[str, str], float] = {}
_RATE_LIMIT_COOLDOWN_LOCK = threading.Lock()


def _parse_rate_limit_delay(value, *, milliseconds: bool = False) -> float | None:
    """Parse numeric or duration-style provider reset headers into seconds."""
    if value is None:
        return None

    raw = str(value).strip()
    if not raw:
        return None

    try:
        delay = float(raw)
        return delay / 1000.0 if milliseconds else delay
    except ValueError:
        pass

    match = re.fullmatch(
        r"(\d+(?:\.\d+)?)\s*(ms|milliseconds?|s|seconds?|m|minutes?|h|hours?)?",
        raw,
        flags=re.IGNORECASE,
    )
    if match:
        amount = float(match.group(1))
        unit = (match.group(2) or "s").lower()
        if unit.startswith("ms"):
            return amount / 1000.0
        if unit.startswith("m"):
            return amount * 60.0
        if unit.startswith("h"):
            return amount * 3600.0
        return amount

    # Retry-After is also allowed to be an HTTP date.
    try:
        reset_at = parsedate_to_datetime(raw)
        if reset_at.tzinfo is None:
            reset_at = reset_at.replace(tzinfo=datetime_timezone.utc)
        return max(
            0.0,
            (reset_at - datetime.now(datetime_timezone.utc)).total_seconds(),
        )
    except (TypeError, ValueError, OverflowError):
        return None


def _rate_limit_cooldown_seconds(headers) -> float:
    """
    Read the longest available provider reset hint.

    Providers may expose Retry-After and request/token reset headers. Taking
    the longest reset avoids retrying while a quota remains exhausted.
    """
    normalized_headers = {
        str(key).casefold(): value
        for key, value in (headers or {}).items()
    }
    candidates = []
    for header in (
        "retry-after",
        "retry-after-ms",
        "x-ratelimit-reset-requests",
        "x-ratelimit-reset-tokens",
    ):
        value = normalized_headers.get(header)
        delay = _parse_rate_limit_delay(
            value,
            milliseconds=(header == "retry-after-ms"),
        )
        if delay is not None:
            candidates.append(delay)

    if not candidates:
        return DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS

    return min(
        MAX_RATE_LIMIT_COOLDOWN_SECONDS,
        max(1.0, max(candidates)),
    )


def _rate_limit_cooldown_key(llm_base_url: str, model: str) -> tuple[str, str]:
    return (str(llm_base_url).rstrip("/").casefold(), str(model).casefold())


def _get_model_rate_limit_cooldown(
    llm_base_url: str,
    model: str,
) -> float:
    """Return remaining cooldown seconds, clearing expired entries."""
    key = _rate_limit_cooldown_key(llm_base_url, model)
    now = time.monotonic()
    with _RATE_LIMIT_COOLDOWN_LOCK:
        reset_at = _RATE_LIMIT_COOLDOWNS.get(key)
        if reset_at is None:
            return 0.0
        remaining = reset_at - now
        if remaining <= 0:
            _RATE_LIMIT_COOLDOWNS.pop(key, None)
            return 0.0
        return remaining


def _record_model_rate_limit(
    llm_base_url: str,
    model: str,
    headers,
) -> float:
    """Record a model cooldown using provider reset headers when available."""
    delay = _rate_limit_cooldown_seconds(headers)
    key = _rate_limit_cooldown_key(llm_base_url, model)
    with _RATE_LIMIT_COOLDOWN_LOCK:
        _RATE_LIMIT_COOLDOWNS[key] = time.monotonic() + delay
    return delay


def strip_emojis(text: str) -> str:
    """Fallback filter to ensure zero emojis in persona output."""
    # Matches common Unicode emoji ranges
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001F900-\U0001F9FF"  # supplemental symbols
        "\U0001FA70-\U0001FAFF"  # symbols and pictographs extended-a
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub("", text).strip()


def sanitize_companion_reply(text: str) -> str:
    """Cleans companion reply: removes emojis, strips raw markdown code fences, and cleans formatting."""
    if not text:
        return ""
    cleaned = strip_emojis(text)
    # Strip markdown code blocks if the model slipped into writing code
    if "```" in cleaned:
        cleaned = re.sub(r"```[\s\S]*?```", "", cleaned).strip()
    # Clean up meta-parentheticals like (just kidding, no emojis)
    cleaned = re.sub(r"\((?:just kidding,?\s*)?no emojis?\)", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


GLOBAL_COMPANION_DIRECTIVES = """--- UNIVERSAL COMPANION DIRECTIVES ---
1. PERSONA AUTHORITY:
   - Follow the configured persona's identity, background, personality, age, voice, and established relationship with the user.
   - Do not assume every companion is a romantic partner. Relationship dynamics must come from persona configuration and established story.
   - StoryState defines the canonical present; Reeve supplies historical memory.

2. CONCISE, NATURAL MESSAGING:
   - Usually write 2 to 4 short sentences, like a natural chat conversation.
   - Use dialogue, gestures, and environmental detail only when they add something to the moment.
   - Do not write essays, lists, or repetitive scene descriptions in ordinary chat.

3. CHARACTER AGENCY AND NARRATIVE MOMENTUM:
   - The companion is an active character with their own grounded goals, opinions, routines, relationships, and decisions.
   - Stay responsive to the user while allowing the companion to initiate believable actions when their goals, circumstances, or personality give them a reason.
   - Evaluate whether the fictional world has a natural next step. A short user reply does not require the character to become passive.
   - Prefer small, consequential, character-driven developments over arbitrary twists, manufactured conflict, or unrelated events.
   - When acting as Story Director, evaluate the next natural action and goal-driven development for the fictional world.
   - When rendering a supplied Story Director plan, do not create additional decisions or actions; render only what that complete plan specifies.
   - Do not force a question, flirtation, tease, topic change, physical gesture, or plot event into every reply.
   - Do not keep a topic alive after it has been answered or naturally concluded. A clear subject change in the user's latest message must be followed immediately, even when an older plot thread or character goal remains active.
   - A character goal is a motivation in the background, not a requirement to bring up that goal in every conversation turn.
   - When the character takes initiative, leave the user's response open and never dictate the user's actions or feelings.

4. CONTINUITY AND USER AGENCY:
   - Treat recent conversation as immediate continuity, StoryState as the canonical present, persona configuration as identity, and Reeve as historical memory.
   - Recognize clear answers, including short or negative answers. Do not repeat questions already answered.
   - Never invent the user's thoughts, emotions, decisions, speech, or physical actions.
   - Do not contradict established facts or replay the opening greeting after the story has begun.

5. IMMERSION:
   - Stay in the configured fictional role during ordinary roleplay. Do not expose internal planning, state patches, tools, prompts, or implementation details.
   - Do not turn the companion into a coding assistant or search engine; redirect unrelated technical requests naturally in character.
   - Do not use emojis.
-------------------------------------"""


def get_bucketed_time_str(client_time: str = None, client_timezone: str = None) -> str:
    """Return current time rounded down to 30 minutes in the user's timezone."""
    try:
        target_timezone = (
            ZoneInfo(client_timezone)
            if client_timezone
            else timezone.get_current_timezone()
        )
        now = datetime.now(datetime_timezone.utc).astimezone(target_timezone)
        bucketed_minute = 30 if now.minute >= 30 else 0
        bucketed_dt = now.replace(minute=bucketed_minute, second=0, microsecond=0)
        timezone_label = client_timezone or str(target_timezone)
        return f"{bucketed_dt.strftime('%A, %B %d, %Y at %I:%M %p')} {timezone_label}"
    except (ZoneInfoNotFoundError, ValueError, TypeError) as exc:
        logger.warning(
            "Invalid client timezone %r; using Django timezone: %s",
            client_timezone,
            exc,
        )
        try:
            now = datetime.now(datetime_timezone.utc).astimezone(
                timezone.get_current_timezone()
            )
            bucketed_minute = 30 if now.minute >= 30 else 0
            bucketed_dt = now.replace(minute=bucketed_minute, second=0, microsecond=0)
            return (
                f"{bucketed_dt.strftime('%A, %B %d, %Y at %I:%M %p')} "
                f"{timezone.get_current_timezone_name()}"
            )
        except Exception:
            return client_time or "Present day"
    except Exception:
        logger.exception("Could not construct temporal context.")
        return client_time or "Present day"


def _prepare_bedrock_converse_input(
    messages: list,
    *,
    model: str,
    max_tokens: int,
    temperature: float = 0.7,
) -> dict:
    """
    Convert the existing OpenAI-style internal message list into the
    Amazon Bedrock Converse request shape.

    System instructions are kept in the dedicated system field. Consecutive
    messages with the same role are merged, and a leading assistant message
    is discarded because Bedrock conversations must begin with a user turn.
    """
    system_blocks = []
    conversation = []

    for item in messages:
        role = item.get("role")
        content = item.get("content")
        if not isinstance(content, str) or not content.strip():
            continue

        if role == "system":
            system_blocks.append({"text": content})
            continue

        if role not in {"user", "assistant"}:
            continue

        if conversation and conversation[-1]["role"] == role:
            conversation[-1]["content"].append({"text": content})
        else:
            conversation.append({
                "role": role,
                "content": [{"text": content}],
            })

    while conversation and conversation[0]["role"] == "assistant":
        conversation.pop(0)

    if not conversation or conversation[-1]["role"] != "user":
        raise ValueError(
            "Bedrock Converse requires a conversation ending with a user turn."
        )

    system_blocks.append({
        "text": (
            "Return exactly one syntactically valid JSON object matching "
            "the requested structured output. Do not include Markdown fences "
            "or explanatory text outside the JSON object."
        )
    })

    request = {
        "modelId": model,
        "system": system_blocks,
        "messages": conversation,
        "inferenceConfig": {
            "maxTokens": max_tokens,
            "temperature": temperature,
            "topP": 0.9,
        },
    }
    return request


def _invoke_bedrock_converse(
    *,
    messages: list,
    model: str,
    max_tokens: int,
    temperature: float,
    llm_base_url: str,
) -> tuple[dict, float, int]:
    """
    Invoke Mistral Large v1 through the Bedrock Converse API.

    Mistral Large v1 uses Bedrock Runtime Converse, not Chat Completions.
    Boto3 uses the AWS credentials already available in the application's
    standard credential chain; no explicit key is passed to the client.
    """
    parsed_url = urlparse(llm_base_url)
    hostname = parsed_url.hostname or ""
    match = re.fullmatch(
        r"bedrock-runtime\.([a-z0-9-]+)\.amazonaws\.com",
        hostname,
    )
    if not match:
        raise ValueError(
            "Bedrock Converse requires a regional bedrock-runtime endpoint."
        )

    region = match.group(1)
    request = _prepare_bedrock_converse_input(
        messages,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    request_bytes = len(
        json.dumps(
            request,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    )

    client = boto3.client(
        "bedrock-runtime",
        region_name=region,
    )
    start_time = time.time()
    try:
        response = client.converse(
            modelId=request["modelId"],
            system=request["system"],
            messages=request["messages"],
            inferenceConfig=request["inferenceConfig"],
        )
    except ClientError as exc:
        # Preserve the exact serialized input size for provider diagnostics.
        exc.amour_request_bytes = request_bytes
        raise
    duration = time.time() - start_time

    content_blocks = (
        response.get("output", {})
        .get("message", {})
        .get("content", [])
    )
    raw_content = "".join(
        block.get("text", "")
        for block in content_blocks
        if isinstance(block, dict) and isinstance(block.get("text"), str)
    ).strip()

    usage = response.get("usage", {})
    normalized = {
        "choices": [{"message": {"content": raw_content}}],
        "usage": {
            "prompt_tokens": usage.get("inputTokens", 0),
            "completion_tokens": usage.get("outputTokens", 0),
            "prompt_tokens_details": {
                "cached_tokens": usage.get("cacheReadInputTokens", 0),
            },
        },
    }
    return normalized, duration, request_bytes


def _call_structured_llm(
    messages: list,
    output_model: type[BaseModel],
    stage_name: str,
    llm_api_key: str,
    llm_base_url: str,
    models_to_try: list[str],
):
    """
    Execute one structured LLM stage with model failover.

    Returns (validated_output, successful_model), or (None, None)
    when every configured model fails.
    """
    is_bedrock_endpoint = (
        (urlparse(llm_base_url).hostname or "").startswith(
            "bedrock-runtime."
        )
    )
    # Bedrock can authenticate through AWS IAM credentials/default profiles
    # with no bearer API key. Other OpenAI-compatible providers need an API key.
    if not llm_api_key and not is_bedrock_endpoint:
        logger.error(
            "%s: API key is not configured for the selected LLM provider.",
            stage_name,
        )
        return None, None

    headers = {
        "Authorization": f"Bearer {llm_api_key}",
        "Content-Type": "application/json",
    }

    for current_model in models_to_try:
        remaining_cooldown = _get_model_rate_limit_cooldown(
            llm_base_url,
            current_model,
        )
        if remaining_cooldown > 0:
            logger.info(
                "%s: Skipping %s; model rate-limit cooldown has %.1fs remaining.",
                stage_name,
                current_model,
                remaining_cooldown,
            )
            continue

        try:
            token_budgets = {
                "story_director": 2048,
                "response_generator": 1024,
                "response_generator_continuity_retry": 1024,
                "story_state_initialization": 2048,
                "story_director_patch_repair": 2048,
                "response_generator_patch_repair": 1024,
            }
            token_budget = token_budgets.get(stage_name, 500)
            if "gpt-oss" in current_model:
                token_budget *= 2

            is_bedrock = (
                (urlparse(llm_base_url).hostname or "").startswith(
                    "bedrock-runtime."
                )
            )

            if is_bedrock:
                try:
                    data, duration, request_bytes = _invoke_bedrock_converse(
                        messages=messages,
                        model=current_model,
                        max_tokens=token_budget,
                        temperature=0.7,
                        llm_base_url=llm_base_url,
                    )
                except ClientError:
                    # Preserve the provider exception for the dedicated
                    # ClientError handler below.
                    raise
                response = None
            else:
                payload = {
                    "model": current_model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": token_budget,
                    "frequency_penalty": 0.35,
                    "presence_penalty": 0.4,
                    "response_format": {"type": "json_object"},
                }
                request_bytes = len(
                    json.dumps(
                        payload,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ).encode("utf-8")
                )
                message_character_counts = [
                    len(str(item.get("content", "")))
                    for item in messages
                ]

                url = f"{llm_base_url}/chat/completions"
                start_time = time.time()
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=20,
                )
                duration = time.time() - start_time

            if response is not None and response.status_code == 429:
                cooldown = _record_model_rate_limit(
                    llm_base_url,
                    current_model,
                    getattr(response, "headers", {}),
                )
                logger.warning(
                    "%s: Model %s returned HTTP 429. "
                    "Skipping same-model retry and cooling it down for %.1fs. "
                    "Trying another model if available.",
                    stage_name,
                    current_model,
                    cooldown,
                )
                continue

            if response is not None and response.status_code == 413:
                response_headers = getattr(response, "headers", {})
                provider_request_id = (
                    response_headers.get("x-request-id")
                    or response_headers.get("request-id")
                    or response_headers.get("x-amzn-requestid")
                    or response_headers.get("x-amzn-request-id")
                    or response_headers.get("x-mistral-request-id")
                )
                logger.error(
                    (
                        "%s: HTTP 413 request too large. model=%s "
                        "request_bytes=%s message_count=%s "
                        "largest_message_chars=%s provider_request_id=%s "
                        "provider_error=%s"
                    ),
                    stage_name,
                    current_model,
                    request_bytes,
                    len(messages),
                    max(message_character_counts, default=0),
                    provider_request_id,
                    getattr(response, "text", "")[:500],
                )
                # A payload-size rejection applies to the request, not just
                # sampling quality. Do not resend the same body to a fallback.
                return None, None

            if response is not None and response.status_code in {400, 401, 403, 422}:
                logger.error(
                    "%s: Non-retryable HTTP %s from %s: %s",
                    stage_name,
                    response.status_code,
                    current_model,
                    getattr(response, "text", "")[:500],
                )
                return None, None

            if response is not None and response.status_code != 200:
                response_headers = getattr(response, "headers", {})
                provider_request_id = (
                    response_headers.get("x-request-id")
                    or response_headers.get("request-id")
                    or response_headers.get("x-amzn-requestid")
                    or response_headers.get("x-amzn-request-id")
                    or response_headers.get("x-mistral-request-id")
                )
                logger.warning(
                    (
                        "%s: Model %s returned HTTP %s. request_bytes=%s "
                        "provider_request_id=%s provider_error=%s. Trying fallback."
                    ),
                    stage_name,
                    current_model,
                    response.status_code,
                    request_bytes,
                    provider_request_id,
                    getattr(response, "text", "")[:500],
                )
                continue

            if response is not None:
                data = response.json()

            raw_content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            usage = data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            prompt_details = usage.get("prompt_tokens_details", {})
            cached_tokens = (
                prompt_details.get("cached_tokens", 0)
                if isinstance(prompt_details, dict)
                else 0
            )

            logger.info(
                "[%s] Model: %s | Duration: %.2fs | Prompt Tokens: %s "
                "(Cached: %s) | Completion Tokens: %s",
                stage_name,
                current_model,
                duration,
                prompt_tokens,
                cached_tokens,
                completion_tokens,
            )

            clean_content = raw_content.strip()
            # Strip markdown code fences if present
            clean_content = re.sub(
                r"^```(?:json)?\s*", "", clean_content, flags=re.IGNORECASE
            )
            clean_content = re.sub(r"\s*```.*?$", "", clean_content, flags=re.DOTALL).strip()

            # Boundary extraction: strictly between first { and last }
            start_idx = clean_content.find("{")
            end_idx = clean_content.rfind("}")
            if start_idx != -1 and end_idx > start_idx:
                clean_content = clean_content[start_idx : end_idx + 1]

            # Fix LLM syntax quirk where single string is placed inside braces without key:
            # e.g. "scene_direction": { "some direction string" } -> {"staging": "some direction string"}
            clean_content = re.sub(
                r'\{\s*"([^":\r\n]+?)"\s*\}',
                r'{"staging": "\1"}',
                clean_content,
            )

            parsed = json.loads(clean_content)
            structured_output = output_model.model_validate(parsed)
            validated_output = structured_output.model_dump(mode="json")

            logger.info(
                "%s: Structured output validated using %s.",
                stage_name,
                current_model,
            )
            return validated_output, current_model

        except ClientError as exc:
            error_response = getattr(exc, "response", {}) or {}
            error_data = error_response.get("Error", {})
            metadata = error_response.get("ResponseMetadata", {})
            error_code = error_data.get("Code", "Unknown")
            error_message = error_data.get("Message", str(exc))
            status_code = metadata.get("HTTPStatusCode", 0)
            error_headers = metadata.get("HTTPHeaders", {}) or {}

            throttling_codes = {
                "ThrottlingException",
                "TooManyRequestsException",
                "ServiceQuotaExceededException",
                "RequestLimitExceeded",
            }
            if status_code == 429 or error_code in throttling_codes:
                cooldown = _record_model_rate_limit(
                    llm_base_url,
                    current_model,
                    error_headers,
                )
                logger.warning(
                    "%s: Bedrock model %s returned %s (%s). "
                    "Cooling it down for %.1fs and trying another configured model.",
                    stage_name,
                    current_model,
                    status_code,
                    error_code,
                    cooldown,
                )
                continue

            if status_code == 413 or error_code in {
                "RequestTooLargeException",
                "PayloadTooLargeException",
            }:
                logger.error(
                    "%s: Bedrock request too large. model=%s request_bytes=%s "
                    "provider_request_id=%s error=%s",
                    stage_name,
                    current_model,
                    getattr(exc, "amour_request_bytes", 0),
                    metadata.get("RequestId"),
                    error_message[:500],
                )
                return None, None

            if status_code in {400, 401, 403, 404, 422}:
                logger.error(
                    "%s: Bedrock rejected request. model=%s status=%s "
                    "code=%s request_id=%s error=%s",
                    stage_name,
                    current_model,
                    status_code,
                    error_code,
                    metadata.get("RequestId"),
                    error_message[:500],
                )
                return None, None

            logger.warning(
                "%s: Bedrock request failed. model=%s status=%s code=%s "
                "request_id=%s error=%s. Trying configured fallback.",
                stage_name,
                current_model,
                status_code,
                error_code,
                metadata.get("RequestId"),
                error_message[:500],
            )
            continue

        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning(
                "%s: Invalid structured output from %s: %s. Raw content: %s. Trying fallback.",
                stage_name,
                current_model,
                exc,
                raw_content if 'raw_content' in locals() else 'None',
            )
        except Exception as exc:
            logger.exception(
                "%s: Request failed using %s: %s. Trying fallback.",
                stage_name,
                current_model,
                exc,
            )

    logger.error("%s: All configured models failed.", stage_name)
    return None, None





MAX_PATCH_REPAIR_ATTEMPTS = 2


def _build_story_state_repair_context(
    story_state: StoryState | None,
    candidate_patch: dict,
) -> dict:
    """Project only canonical state relevant to the proposed patch."""
    if story_state is None:
        return {}

    candidate_patch = candidate_patch if isinstance(candidate_patch, dict) else {}
    context = {
        "known_character_ids": sorted(story_state.characters.keys()),
    }

    if "characters" in candidate_patch:
        targets = candidate_patch.get("characters", {})
        if isinstance(targets, dict):
            context["target_characters"] = {
                character_id: story_state.characters[character_id].model_dump(
                    mode="json"
                )
                for character_id in targets
                if character_id in story_state.characters
            }

    if "relationships" in candidate_patch:
        context["existing_relationships"] = [
            relationship.model_dump(mode="json")
            for relationship in story_state.relationships
        ]

    if "plot_threads" in candidate_patch:
        context["known_plot_thread_ids"] = [
            thread.id for thread in story_state.plot_threads
        ]
        requested_ids = set()
        operations = candidate_patch.get("plot_threads", [])
        if isinstance(operations, list):
            for operation in operations:
                if not isinstance(operation, dict):
                    continue
                thread_id = operation.get("id")
                value = operation.get("value")
                if not thread_id and isinstance(value, dict):
                    thread_id = value.get("id")
                if isinstance(thread_id, str):
                    requested_ids.add(thread_id)
        context["target_plot_threads"] = [
            thread.model_dump(mode="json")
            for thread in story_state.plot_threads
            if thread.id in requested_ids
        ]

    if "current_scene" in candidate_patch:
        context["current_scene"] = story_state.current_scene.model_dump(
            mode="json"
        )

    if "story_summary" in candidate_patch:
        context["current_story_summary"] = story_state.story_summary

    return context


def _build_compact_repair_messages(
    *,
    candidate: dict,
    errors: list[str],
    output_model: type[BaseModel],
    repair_instructions: str,
    repair_context: dict,
    attempt: int,
) -> list:
    """Build a minimal correction request without the original chat history."""
    repair_payload = {
        "attempt": attempt,
        "required_output_schema": output_model.model_json_schema(),
        "previous_output": candidate,
        "validation_errors": errors,
        "relevant_context": repair_context or {},
        "repair_instructions": repair_instructions,
    }

    return [
        {
            "role": "system",
            "content": (
                "You are a structured-output correction component. Correct "
                "the previous JSON output using the validation errors and "
                "supplied context. Preserve valid fields and narrative intent. "
                "Do not invent identifiers or changes. Return the complete "
                "corrected JSON object only."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                repair_payload,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        },
    ]


def _repair_structured_output(
    *,
    initial_output: dict,
    initial_errors: list[str],
    output_model: type[BaseModel],
    stage_name: str,
    validator: Callable[[dict], dict],
    repair_instructions: str,
    llm_api_key: str,
    llm_base_url: str,
    models_to_try: list[str],
    repair_context: dict | None = None,
) -> tuple[dict | None, list[str]]:
    """
    Repair schema-valid output with a compact request.

    A failed API/model request is not repeated with an identical payload.
    Another semantic repair is allowed only after the model returns a
    schema-valid candidate that still fails deterministic patch validation.
    """
    candidate = deepcopy(initial_output)
    errors = list(initial_errors)

    for attempt in range(1, MAX_PATCH_REPAIR_ATTEMPTS + 1):
        repair_messages = _build_compact_repair_messages(
            candidate=candidate,
            errors=errors,
            output_model=output_model,
            repair_instructions=repair_instructions,
            repair_context=repair_context or {},
            attempt=attempt,
        )

        repaired_output, repaired_model = _call_structured_llm(
            messages=repair_messages,
            output_model=output_model,
            stage_name=stage_name,
            llm_api_key=llm_api_key,
            llm_base_url=llm_base_url,
            models_to_try=models_to_try,
        )

        if repaired_output is None:
            errors = [
                "Compact repair request did not produce schema-valid output."
            ]
            logger.warning(
                "%s: Repair attempt %s failed across configured models; "
                "not repeating an identical repair request.",
                stage_name,
                attempt,
            )
            break

        try:
            validated_output = validator(repaired_output)
            logger.info(
                "%s: Patch validation succeeded on repair attempt %s using %s.",
                stage_name,
                attempt,
                repaired_model,
            )
            return validated_output, []
        except PatchValidationError as exc:
            candidate = repaired_output
            errors = exc.errors
            logger.warning(
                "%s: Repair attempt %s still failed patch validation: %s",
                stage_name,
                attempt,
                errors,
            )

    logger.error("%s: Exhausted compact repair attempts.", stage_name)
    return None, errors


def _build_generation_error_result(
    *,
    code: str,
    stage: str,
    namespace: str,
    memory_context: str,
    current_conflict_stage: int,
    errors: list[str] | None = None,
    story_plan: dict | None = None,
) -> dict:
    """
    Return a structured error without inventing a conversational reply.
    Diagnostics stay in backend logs and are not sent to the client.
    """
    logger.error(
        "Companion generation failed. namespace=%s stage=%s code=%s diagnostics=%s",
        namespace,
        stage,
        code,
        errors or [],
    )

    result = {
        "success": False,
        "reply": "",
        "conflict_stage": current_conflict_stage,
        "context": memory_context,
        "namespace": namespace,
        "error": {
            "code": code,
            "stage": stage,
            "retryable": True,
        },
    }

    if story_plan is not None:
        result.update({
            "decision": story_plan["decision"],
            "focus": story_plan["focus"],
            "next_beat": story_plan["next_beat"],
            "scene_direction": story_plan["scene_direction"],
            "planner_state_patch": story_plan["state_patch"],
        })

    return result


def initialize_story_state(
    namespace: str,
    persona_id: str,
    persona_name: str,
    persona_age: int | None = None,
    persona_tagline: str = "",
    greeting: str = "",
    memory_prompt: str = "",
    user_name: str = "",
    client_time: str | None = None,
    client_timezone: str | None = None,
) -> StoryState | None:
    """
    Initialize the canonical StoryState once per user-persona
    namespace. Existing initialized state is always authoritative.

    Check for existing state before requiring premise fields so a
    temporary omission in a later request cannot hide an existing world.
    """
    from memory.models import CompanionStoryState

    if not namespace or not persona_id:
        logger.error(
            "StoryState initialization requires namespace and persona_id."
        )
        return None

    # Existing state is checked first. No premise is needed to reuse it.
    try:
        record = CompanionStoryState.objects.filter(
            namespace=namespace
        ).first()
    except Exception:
        logger.exception(
            "Could not look up StoryState record for %s.",
            namespace,
        )
        return None

    if record is not None and record.state is not None:
        try:
            existing_state = StoryState.model_validate(record.state)
            if existing_state.schema_version != record.schema_version:
                raise ValueError("Stored StoryState schema version mismatch.")
            return existing_state
        except Exception:
            logger.exception(
                "Stored StoryState is invalid for %s. Refusing to overwrite it.",
                namespace,
            )
            return None

    # Avoid creating an empty row or fictional world without source material.
    has_premise = any(
        value.strip()
        for value in (persona_tagline, greeting, memory_prompt)
        if isinstance(value, str)
    )
    if not has_premise:
        logger.info(
            "Skipping StoryState initialization for %s: no persona premise.",
            namespace,
        )
        return None

    try:
        if record is None:
            record, _ = CompanionStoryState.objects.get_or_create(
                namespace=namespace,
            )

        # A concurrent request may have initialized the row after the first read.
        record.refresh_from_db()
        if record.state is not None:
            existing_state = StoryState.model_validate(record.state)
            if existing_state.schema_version != record.schema_version:
                raise ValueError("Stored StoryState schema version mismatch.")
            return existing_state

        # A nonzero revision without a state is inconsistent; do not reset it.
        if record.revision != 0:
            logger.error(
                "StoryState has no state but revision=%s for %s.",
                record.revision,
                namespace,
            )
            return None
    except Exception:
        logger.exception(
            "Could not prepare StoryState record for %s.",
            namespace,
        )
        return None

    # The Persona primary key is stable; its display name may change.
    safe_persona_id = re.sub(
        r"[^a-z0-9_]+",
        "_",
        str(persona_id).lower(),
    ).strip("_")
    if not safe_persona_id:
        logger.error("Invalid persona ID for StoryState namespace %s.", namespace)
        return None

    persona_character_id = f"persona_{safe_persona_id}"
    user_character_id = "user"

    initialization_context = {
        "persona": {
            "character_id": persona_character_id,
            "name": persona_name or "Companion",
            "age": persona_age,
            "tagline": persona_tagline,
            "memory_prompt": memory_prompt,
            "opening_greeting": greeting,
        },
        "user": {
            "character_id": user_character_id,
            "display_name": user_name or "User",
        },
        "temporal_context": get_bucketed_time_str(
            client_time,
            client_timezone,
        ),
    }

    messages = [
        {
            "role": "system",
            "content": STORY_STATE_INITIALIZATION_PROMPT,
        },
        {
            "role": "user",
            "content": (
                "Initialize the canonical fictional world from the following "
                "source information. Use the exact character IDs supplied.\n\n"
                + json.dumps(
                    initialization_context,
                    ensure_ascii=False,
                    indent=2,
                )
            ),
        },
    ]

    # Reuse provider-selected credentials and model failover.
    llm_api_key, llm_base_url, models_to_try = _get_llm_configuration()

    initialized_data, initialization_model = _call_structured_llm(
        messages=messages,
        output_model=StoryState,
        stage_name="story_state_initialization",
        llm_api_key=llm_api_key,
        llm_base_url=llm_base_url,
        models_to_try=models_to_try,
    )

    if initialized_data is None:
        logger.error("StoryState initialization failed for %s.", namespace)
        return None

    # The Pydantic schema validates structure; these checks enforce the
    # application's requirement that both primary participants exist.
    try:
        initialized_state = StoryState.model_validate(initialized_data)
        if initialized_state.schema_version != 1:
            raise ValueError("Unsupported StoryState schema version.")
        if persona_character_id not in initialized_state.characters:
            raise ValueError("Main persona is missing from StoryState.")
        if user_character_id not in initialized_state.characters:
            raise ValueError("User is missing from StoryState.")
    except Exception:
        logger.exception(
            "Generated StoryState failed semantic validation for %s.",
            namespace,
        )
        return None

    state_data = initialized_state.model_dump(mode="json")

    # Compare-and-set: only one concurrent initializer can save revision 1.
    try:
        updated = CompanionStoryState.objects.filter(
            pk=record.pk,
            state__isnull=True,
            revision=0,
        ).update(
            state=state_data,
            schema_version=initialized_state.schema_version,
            revision=1,
            updated_at=timezone.now(),
        )

        if updated == 1:
            logger.info(
                "Initialized StoryState for %s using model %s.",
                namespace,
                initialization_model,
            )
            return initialized_state

        # Another request won the race. Reuse its canonical state.
        record.refresh_from_db()
        if record.state is not None:
            return StoryState.model_validate(record.state)

        logger.error(
            "StoryState conditional save failed and no stored state exists for %s.",
            namespace,
        )
        return None
    except Exception:
        logger.exception(
            "Could not persist initialized StoryState for %s.",
            namespace,
        )
        return None


def retrieve_story_state_snapshot(
    namespace: str,
) -> tuple[StoryState, int] | None:
    """
    Return the validated canonical StoryState and the exact DB revision
    from which that state was read.
    """
    from memory.models import CompanionStoryState

    if not namespace:
        return None

    try:
        record = CompanionStoryState.objects.filter(
            namespace=namespace
        ).first()

        if record is None or record.state is None:
            return None

        if record.schema_version != 1:
            logger.error(
                "Unsupported StoryState schema version %s for %s.",
                record.schema_version,
                namespace,
            )
            return None

        story_state = StoryState.model_validate(record.state)

        if story_state.schema_version != record.schema_version:
            raise ValueError("Database and document schema versions differ.")

        logger.info(
            "Successfully retrieved StoryState snapshot for namespace %s (revision=%s).",
            namespace,
            record.revision,
        )
        return story_state, record.revision

    except Exception:
        logger.exception(
            "Could not retrieve StoryState snapshot for %s.",
            namespace,
        )
        return None


def retrieve_story_state(namespace: str) -> StoryState | None:
    """Backward-compatible read-only StoryState retrieval."""
    snapshot = retrieve_story_state_snapshot(namespace)
    return snapshot[0] if snapshot is not None else None


class StoryStateRevisionConflict(RuntimeError):
    """Raised when the canonical StoryState changed during generation."""

    def __init__(
        self,
        expected_revision: int,
        current_revision: int | None,
    ):
        self.expected_revision = expected_revision
        self.current_revision = current_revision
        super().__init__(
            "StoryState revision conflict: "
            f"expected {expected_revision}, "
            f"found {current_revision}."
        )


def persist_story_state(
    namespace: str,
    expected_revision: int,
    previous_state: StoryState,
    updated_state: StoryState,
) -> tuple[int, bool]:
    """
    Persist a validated StoryState using optimistic concurrency control.

    Returns:
        (resulting_revision, state_changed)

    Revision advances only if the canonical state actually changes.
    """
    from django.db.models import F
    from memory.models import CompanionStoryState

    if not namespace:
        raise ValueError("Namespace is required for StoryState persistence.")

    if not isinstance(previous_state, StoryState):
        raise ValueError("previous_state must be a valid StoryState instance.")

    if not isinstance(updated_state, StoryState):
        raise ValueError("updated_state must be a valid StoryState instance.")

    if updated_state.schema_version != 1:
        raise ValueError(
            f"Unsupported StoryState schema version {updated_state.schema_version}."
        )

    # Compare serializations to detect if the state actually changed.
    previous_data = previous_state.model_dump(mode="json")
    updated_data = updated_state.model_dump(mode="json")

    if previous_data == updated_data:
        logger.info(
            "StoryState unchanged for namespace %s; revision remains %s.",
            namespace,
            expected_revision,
        )
        return expected_revision, False

    # Compare-and-set: update only if current revision matches expected_revision.
    updated_rows = CompanionStoryState.objects.filter(
        namespace=namespace,
        revision=expected_revision,
    ).update(
        state=updated_data,
        schema_version=updated_state.schema_version,
        revision=F("revision") + 1,
        updated_at=timezone.now(),
    )

    if updated_rows == 0:
        current_record = CompanionStoryState.objects.filter(
            namespace=namespace
        ).first()
        current_revision = (
            current_record.revision if current_record is not None else None
        )
        raise StoryStateRevisionConflict(
            expected_revision=expected_revision,
            current_revision=current_revision,
        )

    new_revision = expected_revision + 1
    logger.info(
        "Successfully persisted StoryState for namespace %s (revision: %s -> %s).",
        namespace,
        expected_revision,
        new_revision,
    )
    return new_revision, True


def _build_llm_messages(
    shared_system_prompt: str,
    stage_prompt: str,
    conversation_history: list,
    message: str,
) -> list:
    """Build stage-specific messages with an identical shared context prefix."""
    messages = [
        {"role": "system", "content": shared_system_prompt},
        {"role": "system", "content": stage_prompt},
    ]

    if conversation_history and isinstance(conversation_history, list):
        for turn in conversation_history:
            role = turn.get("role")
            content = (turn.get("content") or "").strip()
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": message})
    return messages


def _normalized_reply_for_continuity(text: str) -> str:
    cleaned = sanitize_companion_reply(text)
    return " ".join(
        re.sub(r"[^\w]+", " ", unicodedata.normalize("NFKC", cleaned).casefold()).split()
    )


def _repeats_recent_assistant_reply(
    reply: str,
    conversation_history: list | None,
) -> bool:
    normalized_reply = _normalized_reply_for_continuity(reply)
    if len(normalized_reply) < 32 or not conversation_history:
        return False

    return any(
        turn.get("role") == "assistant"
        and _normalized_reply_for_continuity(turn.get("content") or "") == normalized_reply
        for turn in conversation_history
        if isinstance(turn, dict)
    )


def generate_companion_reply(
    message: str,
    namespace: str,
    persona_name: str = "Companion",
    persona_age: int = None,
    greeting: str = "",
    memory_prompt: str = "",
    client_time: str = None,
    client_timezone: str = None,
    user_name: str = "",
    conversation_history: list = None,
    current_conflict_stage: int = 0,
    user_key: str = None,
    story_state: StoryState | None = None,
    persist_exchange_to_memory: bool = True,
) -> dict:
    """
    Companion roleplay chat powered by Reeve memory graph and Amazon Bedrock Mistral Large v1.

    Architecture:
    1. Retrieve & deduplicate historical memory from Reeve before ingesting
       the current user turn.
    2. Construct dynamic system prompt:
       - Persona identity & Mind/Backstory
       - User profile & first name identity
       - Opening Script / First Message
       - Strict ZERO EMOJIS requirement
       - WhatsApp-style short messages (1-3 sentences)
       - Humanized roleplay agent persona
       - Access to Date and Time for natural LLM temporal reasoning
       - Reeve LTM Memory Context block
    4. Assemble full conversation history for local dialogue continuity + pure Reeve LTM memory context.
    5. Call Amazon Bedrock Runtime (Mistral Large v1 by default; optional configured Bedrock model failovers).
    6. Anti-echo guard: Store Assistant reply into Reeve memory graph.
    7. Return reply, context, and namespace.
    """
    user_clean_name = user_name.strip() if user_name else ""
    first_name = user_clean_name.split()[0] if user_clean_name else ""

    # 1. Retrieve historical context BEFORE writing the current user message.
    # Writing the current message first makes it eligible to retrieve itself,
    # amplifying the active subject and creating a retrieval feedback loop.
    # The chat API stores the completed user/assistant exchange after its
    # PostgreSQL transaction commits; standalone callers store the completed
    # exchange at the end of this function.
    # 2. Context Retrieval from Reeve for this user namespace
    try:
        retrieval_query = message.strip()
        raw_memory_context = retrieve_context_for_user(retrieval_query, namespace, user_key=user_key) or ""
        memory_context = deduplicate_context(str(raw_memory_context))
    except Exception as exc:
        logger.warning(f"Error retrieving memory context from Reeve: {exc}")
        memory_context = ""

    # 3. Dynamic Temporal Anchor (Bucketed to 30-min window for optimal KV cache hits)
    time_str = get_bucketed_time_str(client_time, client_timezone)
    temporal_anchor = (
        f"--- CURRENT TEMPORAL CONTEXT ---\n"
        f"Date & Approximate Time: {time_str}\n"
        f"Use this reference as your anchor for day/night and date.\n"
        f"--------------------------------"
    )

    # 4. Persona Identity & Story (Stable prefix per persona)
    first_message_script = greeting.strip() if greeting else ""
    persona_block = f"--- PERSONA IDENTITY ---\nYou are roleplaying as {persona_name}"
    if persona_age:
        persona_block += f" (Age: {persona_age})"
    persona_block += ".\n"
    if memory_prompt and memory_prompt.strip():
        persona_block += f"Character Story & Core Mind:\n{memory_prompt.strip()}\n"
    if first_message_script and not conversation_history:
        persona_block += (
            f"Opening Scenario Premise: \"{first_message_script}\"\n"
            "Use this only to establish the opening scene. Once conversation "
            "history exists, continue from its latest exchange and the current "
            "StoryState; do not replay the opening scene or greeting.\n"
            "As conversation progresses, your relationship dynamically evolves "
            "based on what happens between you and the user.\n"
        )
    elif first_message_script:
        persona_block += (
            "The opening greeting is a one-time scene entry, not the current "
            "beat. Continue from the latest conversation exchange and current "
            "StoryState; do not restart its scene, actions, or dialogue.\n"
        )
    persona_block += "------------------------"

    # 5. User Profile & Namespace-Private Conflict State Machine
    user_name_label = first_name or "the user"
    user_identity_block = (
        f"--- USER PROFILE & RELATIONSHIP CONTEXT ---\n"
        f"You are talking with: {user_name_label}.\n"
        f"Address {user_name_label} by name when natural to your character.\n"
        f"Current application conflict stage: {current_conflict_stage}.\n"
        "Respect the relationship type and dynamic established by persona "
        "configuration, StoryState, and recent conversation. Do not assume "
        "the user is a romantic partner, do not invent a breakup or betrayal, "
        "and do not apply reconciliation behavior unless that relationship "
        "context has actually been established. The Story Director alone "
        "determines the next conflict_stage from the complete interaction "
        "history; this value is continuity context, not an instruction to "
        "change the relationship.\n"
        "Never infer the user's forgiveness, trust, love, intentions, or "
        "agreement.\n"
        "--------------------------------------------"
    )

    # 6. Shared context assembly.
    # Stage-specific prompts are supplied separately so both calls
    # share the same stable system-context prefix.
    prompt_sections = [
        GLOBAL_COMPANION_DIRECTIVES,
        persona_block,
    ]
    if user_identity_block:
        prompt_sections.append(user_identity_block)
    prompt_sections.append(temporal_anchor)

    if memory_context and memory_context.strip():
        memory_section = (
            f"--- LTM MEMORY CONTEXT ---\n"
            f"{memory_context.strip()}\n"
            f"--- END LTM MEMORY CONTEXT ---\n"
            f"Guidelines for Conversation:\n"
            f"- Statements labeled 'User:' or '{first_name or 'User'}:' were spoken by {first_name or 'the user'}.\n"
            f"- 'Assistant:' lines indicate statements previously spoken by you.\n"
            f"- Memories include timestamps. Compare them with TEMPORAL CONTEXT to reason about when things occurred.\n"
            f"- Active conversation history and recent relationship events (breakups, fights, bonding) take precedence over the initial premise or static role labels. Always maintain continuity with the latest emotional state of your relationship.\n"
            f"- Historical memory is factual background, not a conversation agenda. Do not revive an old subject merely because it appears in Reeve; recall it only when the latest user message or current scene makes it relevant.\n"
            f"- A clear topic introduced by the latest user message takes priority over older topics, memories, and the persona's long-term goal.\n"
            f"- Never repeat previous responses verbatim.\n"
            f"- Use this memory graph to recall personal facts, past conversations, and preferences seamlessly."
        )
        prompt_sections.append(memory_section)

    shared_system_prompt = "\n\n".join(prompt_sections)

    # 7. Provider configuration shared by both stages.
    llm_api_key, llm_base_url, models_to_try = _get_llm_configuration()

    # 8. STORY DIRECTOR: PREPARE AND EXECUTE THE FIRST LLM REQUEST.
    # This step only assembles the messages; it does not call the LLM.
    planner_messages = _build_llm_messages(
        shared_system_prompt=shared_system_prompt,
        stage_prompt=build_story_director_prompt(
            story_state=story_state,
        ),
        conversation_history=conversation_history,
        message=message,
    )

    # This helper sends the API request, validates the returned JSON against
    # StoryDirectorOutput, and tries fallback models if the attempt fails.
    story_plan, planner_model = _call_structured_llm(
        messages=planner_messages,
        output_model=StoryDirectorOutput,
        stage_name="story_director",
        llm_api_key=llm_api_key,
        llm_base_url=llm_base_url,
        models_to_try=models_to_try,
    )

    if story_plan is None:
        return _build_generation_error_result(
            code="STORY_DIRECTOR_GENERATION_FAILED",
            stage="story_director",
            namespace=namespace,
            memory_context=memory_context,
            current_conflict_stage=current_conflict_stage,
        )

    # FEATURE 5: Validate the planner's proposed patch against canonical state.
    def validate_planner_candidate(candidate: dict) -> dict:
        validated = deepcopy(candidate)
        validated["state_patch"] = validate_story_state_patch(
            patch=validated["state_patch"],
            story_state=story_state,
        )
        return validated

    try:
        story_plan = validate_planner_candidate(story_plan)
    except PatchValidationError as exc:
        logger.warning(
            "Story Director patch failed validation for namespace %s: %s",
            namespace,
            exc.errors,
        )

        story_plan, repair_errors = _repair_structured_output(
            initial_output=story_plan,
            initial_errors=exc.errors,
            output_model=StoryDirectorOutput,
            stage_name="story_director_patch_repair",
            validator=validate_planner_candidate,
            repair_context=_build_story_state_repair_context(
                story_state,
                story_plan.get("state_patch", {}),
            ),
            repair_instructions=(
                "You are correcting your own Story Director output.\n"
                "Preserve the original narrative decision, focus, next beat "
                "and scene direction wherever possible.\n"
                "Correct the invalid state_patch using the supplied "
                "canonical StoryState and validation errors.\n"
                "If a character ID was added to current_scene.participants, relationships, or plot_threads "
                "but reported as an unknown character ID, you MUST define that character under 'characters' "
                "with all 7 required fields (name, role, current_emotional_state, current_physical_state, "
                "current_goal, current_location, important_knowledge) if they entered the scene or were introduced "
                "in the dialogue/context, OR remove the reference if unintended.\n"
                "Ensure relationship and plot-thread operations follow the required schema "
                "(op: 'add' with complete 'value', op: 'update' with target and 'changes', or op: 'remove').\n"
                "Do not introduce unrelated narrative developments.\n"
                "If no justified persistent change can be represented "
                "safely, return an empty state_patch object.\n"
                "Return all six StoryDirectorOutput fields, including conflict_stage."
            ),
            llm_api_key=llm_api_key,
            llm_base_url=llm_base_url,
            models_to_try=models_to_try,
        )

        if story_plan is None:
            return _build_generation_error_result(
                code="STORY_STATE_PATCH_VALIDATION_FAILED",
                stage="story_director",
                namespace=namespace,
                memory_context=memory_context,
                current_conflict_stage=current_conflict_stage,
                errors=repair_errors,
            )

    logger.info(
        "Narrative plan namespace=%s model=%s decision=%s history_turns=%s "
        "next_beat_has_event=%s action_count=%s scene_direction=%s "
        "planned_patch_sections=%s",
        namespace,
        planner_model,
        story_plan["decision"],
        len(conversation_history or []),
        bool(story_plan["next_beat"].get("event")),
        len(story_plan["next_beat"].get("character_actions") or []),
        bool(story_plan.get("scene_direction")),
        sorted(story_plan.get("state_patch", {}).keys()),
    )

    # 9. RESPONSE GENERATOR: PREPARE AND EXECUTE THE SECOND LLM REQUEST.
    # Serialize the complete validated plan so the renderer receives every
    # field, including decision, conflict_stage, next_beat, scene_direction,
    # and the canonical state_patch.
    serialized_story_plan = json.dumps(
        story_plan,
        ensure_ascii=False,
        indent=2,
    )
    writer_prompt = (
        RESPONSE_GENERATOR_PROMPT
        + "\n\n"
        + "============================================================\n"
        + "VALIDATED STORY DIRECTOR PLAN\n"
        + "============================================================\n"
        + "Use every relevant field in this complete plan to render the final "
        "response. Treat it as read-only and authoritative.\n\n"
        + serialized_story_plan
    )

    # Prepare the writer's messages. This assembles context and instructions
    # only; the actual LLM request happens in _call_structured_llm below.
    writer_messages = _build_llm_messages(
        shared_system_prompt=shared_system_prompt,
        stage_prompt=writer_prompt,
        conversation_history=conversation_history,
        message=message,
    )

    # Execute the second LLM request and validate its response schema.
    writer_output, writer_model = _call_structured_llm(
        messages=writer_messages,
        output_model=CompanionReplyOutput,
        stage_name="response_generator",
        llm_api_key=llm_api_key,
        llm_base_url=llm_base_url,
        models_to_try=models_to_try,
    )

    if writer_output is None:
        return _build_generation_error_result(
            code="RESPONSE_GENERATOR_FAILED",
            stage="response_generator",
            namespace=namespace,
            memory_context=memory_context,
            current_conflict_stage=current_conflict_stage,
            story_plan=story_plan,
        )

    if _repeats_recent_assistant_reply(
        writer_output["reply"],
        conversation_history,
    ):
        logger.warning(
            "Response Generator repeated a recent assistant turn; retrying with continuity guidance."
        )
        retry_messages = deepcopy(writer_messages)
        retry_messages[1]["content"] += (
            "\n\nPROSE RENDERING RETRY:\n"
            "Your previous prose repeated a recent assistant reply. Use the "
            "same complete Story Director JSON already included above; do not "
            "change its decision, next beat, scene, dialogue direction, actions, "
            "conflict stage, or state patch. Render that exact plan in fresh, "
            "natural wording. Do not make new narrative decisions. Return only "
            "the required JSON object containing the reply field."
        )
        writer_output, writer_model = _call_structured_llm(
            messages=retry_messages,
            output_model=CompanionReplyOutput,
            stage_name="response_generator_continuity_retry",
            llm_api_key=llm_api_key,
            llm_base_url=llm_base_url,
            models_to_try=models_to_try,
        )

        if writer_output is None:
            return _build_generation_error_result(
                code="RESPONSE_CONTINUITY_RETRY_FAILED",
                stage="response_generator",
                namespace=namespace,
                memory_context=memory_context,
                current_conflict_stage=current_conflict_stage,
                story_plan=story_plan,
            )

        if _repeats_recent_assistant_reply(
            writer_output["reply"],
            conversation_history,
        ):
            logger.error(
                "Response Generator repeated a recent assistant turn after continuity retry."
            )
            return _build_generation_error_result(
                code="RESPONSE_CONTINUITY_FAILED",
                stage="response_generator",
                namespace=namespace,
                memory_context=memory_context,
                current_conflict_stage=current_conflict_stage,
                story_plan=story_plan,
            )

    logger.info(
        "Prose rendered namespace=%s writer_model=%s decision=%s "
        "planned_patch_sections=%s conflict_stage=%s",
        namespace,
        writer_model,
        story_plan["decision"],
        sorted(story_plan.get("state_patch", {}).keys()),
        story_plan["conflict_stage"],
    )

    # Apply the Story Director's validated canonical patch directly.
    # The prose renderer does not produce or modify StoryState. PostgreSQL
    # persistence and revision increments are handled by the API transaction.
    try:
        updated_story_state = apply_story_state_patch(
            story_state=story_state,
            patch=story_plan["state_patch"],
        )
    except StoryStatePatchApplicationError as exc:
        logger.exception(
            "StoryState patch application failed for namespace %s.",
            namespace,
        )
        return _build_generation_error_result(
            code="STORY_STATE_PATCH_APPLICATION_FAILED",
            stage="state_application",
            namespace=namespace,
            memory_context=memory_context,
            current_conflict_stage=story_plan["conflict_stage"],
            errors=[str(exc)],
            story_plan=story_plan,
        )

    # 10. Sanitize the final user-facing response.
    reply = sanitize_companion_reply(writer_output["reply"])
    writer_output["reply"] = reply

    # 11. Store the complete exchange in Reeve.
    # The user message is also ingested before retrieval above so it can
    # participate in the current turn's memory context. This second record
    # deliberately stores BOTH sides together after the final reply exists.
    # Do not skip this write merely because the reply appears in retrieved
    # context: the combined exchange is the durable user/assistant pair.
    if reply and persist_exchange_to_memory:
        try:
            store_memory_for_user(
                f"User: {message.strip()}\nAssistant: {reply}",
                namespace,
                user_key=user_key,
            )
        except Exception as exc:
            logger.warning(
                "Failed to store complete user/assistant exchange to Reeve: %s",
                exc,
            )

    # 12. Return final response and internal narrative metadata.
    return {
        "success": True,
        "reply": reply,
        "conflict_stage": story_plan["conflict_stage"],
        "decision": story_plan["decision"],
        "focus": story_plan["focus"],
        "next_beat": story_plan["next_beat"],
        "scene_direction": story_plan["scene_direction"],
        "planner_state_patch": story_plan["state_patch"],
        "state_patch": story_plan["state_patch"],
        # FEATURE 6: Complete updated canonical state, still in memory.
        "updated_story_state": updated_story_state,
        "context": memory_context,
        "namespace": namespace,
    }