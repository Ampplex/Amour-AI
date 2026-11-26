import logging

logger = logging.getLogger("amour.llm_observability")


def _read_int(values: dict, *keys: str) -> int | None:
    for key in keys:
        value = values.get(key)
        if value is not None:
            try:
                return max(0, int(value))
            except (TypeError, ValueError):
                continue
    return None


def extract_token_usage(usage: dict | None) -> tuple[int | None, int | None]:
    """Normalize Bedrock and OpenAI-compatible usage metadata."""
    if not isinstance(usage, dict):
        return None, None
    input_tokens = _read_int(usage, "inputTokens", "prompt_tokens", "input_tokens")
    output_tokens = _read_int(usage, "outputTokens", "completion_tokens", "output_tokens")
    return input_tokens, output_tokens


def extract_rate_limit_headers(headers) -> dict:
    """Read common OpenAI-compatible quota headers without storing provider credentials."""
    normalized = {str(key).lower(): value for key, value in (headers or {}).items()}
    return {
        "rate_limit_limit_requests": _read_int(normalized, "x-ratelimit-limit-requests"),
        "rate_limit_remaining_requests": _read_int(normalized, "x-ratelimit-remaining-requests"),
        "rate_limit_reset_requests": str(normalized.get("x-ratelimit-reset-requests", ""))[:64],
        "rate_limit_limit_tokens": _read_int(normalized, "x-ratelimit-limit-tokens"),
        "rate_limit_remaining_tokens": _read_int(normalized, "x-ratelimit-remaining-tokens"),
        "rate_limit_reset_tokens": str(normalized.get("x-ratelimit-reset-tokens", ""))[:64],
    }


def record_llm_request(
    *,
    provider: str,
    model: str,
    purpose: str = "chat",
    status: str,
    duration_ms: int,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    response_status: int | None = None,
    error_type: str = "",
    rate_limit_headers=None,
) -> None:
    """Persist metadata only; prompts, completions, and user identifiers are never recorded."""
    try:
        from .models import LLMRequestMetric

        LLMRequestMetric.objects.create(
            provider=provider[:32],
            model=model[:255],
            purpose=purpose[:32],
            status=status,
            duration_ms=max(0, duration_ms),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            response_status=response_status,
            error_type=error_type[:128],
            **extract_rate_limit_headers(rate_limit_headers),
        )
    except Exception:
        logger.exception("Could not persist LLM request telemetry for provider %s", provider)
