"""
Main Response Generator Service.

Streamlined, single-prompt AI persona roleplay engine powered by Reeve memory graph
and Amazon Bedrock (Mistral Large v1) / Groq / OpenAI-compatible LLMs.
Directly generates immersive character responses with rich body language,
atmosphere, initiative, and conversational momentum — with zero state patchers,
zero validators, and zero JSON schemas.
"""

import os
import re
import time
import json
import logging
import threading
import unicodedata
from datetime import datetime, timezone as datetime_timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.utils import timezone

from memory.reeve_service import (
    store_memory_for_user,
    retrieve_context_for_user,
    deduplicate_context,
)

logger = logging.getLogger("amour.response_generator")

# In-memory cooldowns for rate-limited models across all requests
_RATE_LIMIT_COOLDOWNS: dict[str, float] = {}
_COOLDOWN_LOCK = threading.Lock()
DEFAULT_COOLDOWN_SECONDS = 60.0


def _get_model_rate_limit_cooldown(endpoint: str, model_id: str) -> float:
    """Return remaining cooldown seconds for a model at endpoint, or 0.0 if available."""
    key = f"{endpoint}:{model_id}"
    with _COOLDOWN_LOCK:
        expires_at = _RATE_LIMIT_COOLDOWNS.get(key, 0.0)
        remaining = expires_at - time.time()
        if remaining <= 0:
            _RATE_LIMIT_COOLDOWNS.pop(key, None)
            return 0.0
        return remaining


def _record_model_rate_limit(
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


def _get_llm_configuration() -> tuple[str, str, list[str]]:
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


def strip_emojis(text: str) -> str:
    """Strip all unicode emoji characters, pictographs, and symbols from text."""
    if not text:
        return ""
    result = []
    for char in text:
        cat = unicodedata.category(char)
        cp = ord(char)
        # Skip emojis, dingbats, transport/map symbols, emoticons, pictographs
        if (
            cat == "So"
            or 0x1F600 <= cp <= 0x1F64F
            or 0x1F300 <= cp <= 0x1F5FF
            or 0x1F680 <= cp <= 0x1F6FF
            or 0x1F700 <= cp <= 0x1F77F
            or 0x1F780 <= cp <= 0x1F7FF
            or 0x1F800 <= cp <= 0x1F8FF
            or 0x1F900 <= cp <= 0x1F9FF
            or 0x1FA00 <= cp <= 0x1FA6F
            or 0x1FA70 <= cp <= 0x1FAFF
            or 0x2600 <= cp <= 0x26FF
            or 0x2700 <= cp <= 0x27BF
            or 0xFE00 <= cp <= 0xFE0F
            or 0x1F1E6 <= cp <= 0x1F1FF
        ):
            continue
        result.append(char)
    cleaned = "".join(result)
    return re.sub(r"  +", " ", cleaned).strip()


def sanitize_companion_reply(text: str) -> str:
    """Sanitize reply: strip emojis, remove markdown code blocks, clean artifacts."""
    if not text:
        return ""
    cleaned = strip_emojis(text)
    if "```" in cleaned:
        cleaned = re.sub(r"```[\s\S]*?```", "", cleaned).strip()
    # Strip meta-parentheticals
    cleaned = re.sub(r"\((?:just kidding,?\s*)?no emojis?\)", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


def get_bucketed_time_str(client_time: str = None, client_timezone: str = None) -> str:
    """Rounds current time to a stable 30-minute bucket for KV-cache friendliness."""
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
    except Exception:
        return client_time or "Present day"


def _prepare_bedrock_converse_messages(messages: list) -> tuple[list[dict], list[dict]]:
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


def _call_llm_text(
    messages: list,
    llm_api_key: str,
    llm_base_url: str,
    models_to_try: list[str],
    max_tokens: int = 1024,
    temperature: float = 0.75,
) -> tuple[str | None, str | None]:
    """
    Direct LLM call with fallback model chain.
    Returns (raw_reply_text, model_name) or (None, None) on total failure.
    """
    is_bedrock = (urlparse(llm_base_url).hostname or "").startswith("bedrock-runtime.")

    for current_model in models_to_try:
        cooldown = _get_model_rate_limit_cooldown(llm_base_url, current_model)
        if cooldown > 0:
            logger.info("Skipping model %s; in cooldown for %.1fs", current_model, cooldown)
            continue

        try:
            if is_bedrock:
                parsed_url = urlparse(llm_base_url)
                hostname = parsed_url.hostname or ""
                match = re.fullmatch(r"bedrock-runtime\.([a-z0-9-]+)\.amazonaws\.com", hostname)
                region = match.group(1) if match else "us-west-2"

                system_blocks, conversation = _prepare_bedrock_converse_messages(messages)
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
                    "frequency_penalty": 0.35,
                    "presence_penalty": 0.3,
                }
                url = f"{llm_base_url}/chat/completions"

                start_time = time.time()
                resp = requests.post(url, headers=headers, json=payload, timeout=25)
                duration = time.time() - start_time

                if resp.status_code == 429:
                    cd = _record_model_rate_limit(llm_base_url, current_model, resp.headers)
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
                cd = _record_model_rate_limit(llm_base_url, current_model)
                logger.warning("Bedrock model %s throttled (%s); cooldown %.1fs", current_model, err_code, cd)
            else:
                logger.error("Bedrock ClientError for %s: %s", current_model, exc)
            continue
        except Exception as exc:
            logger.exception("Unexpected error calling LLM model %s: %s", current_model, exc)
            continue

    return None, None


def build_roleplay_system_prompt(
    persona_name: str,
    persona_age: int | None,
    persona_tagline: str,
    greeting: str,
    memory_prompt: str,
    user_name: str,
    client_time: str | None,
    client_timezone: str | None,
    memory_context: str,
) -> str:
    """Build a rich, single unified roleplay system prompt."""
    time_str = get_bucketed_time_str(client_time, client_timezone)
    user_display = user_name.strip() if user_name else "the user"
    first_name = user_display.split()[0] if user_display else ""

    sections = []

    # 1. Identity & Backstory
    identity = f"--- CHARACTER IDENTITY & MIND ---\n"
    identity += f"You are {persona_name}"
    if persona_age:
        identity += f", age {persona_age}"
    if persona_tagline:
        identity += f" ({persona_tagline})"
    identity += ".\n"
    if memory_prompt and memory_prompt.strip():
        identity += f"\nBackstory, Persona & Voice:\n{memory_prompt.strip()}\n"
    if greeting and greeting.strip():
        identity += f"\nOpening Scene Premise:\n\"{greeting.strip()}\"\n"
    sections.append(identity.strip())

    # 2. User Relationship & Temporal Anchor
    user_sec = f"--- CONVERSATION CONTEXT ---\n"
    user_sec += f"You are chatting with: {user_display}.\n"
    if first_name:
        user_sec += f"Call {first_name} by name naturally when appropriate.\n"
    user_sec += f"Current Date & Time: {time_str}\n"
    user_sec += "Use the date and time to ground whether it is morning, afternoon, or night."
    sections.append(user_sec.strip())

    # 3. Reeve Long-Term Memory Graph
    if memory_context and memory_context.strip():
        mem_sec = (
            f"--- REEVE MEMORY & SHARED HISTORY ---\n"
            f"{memory_context.strip()}\n"
            f"-------------------------------------\n"
            f"Use these memories to recall past shared moments, personal facts, preferences, "
            f"and inside jokes seamlessly. Never regurgitate them mechanically; weave them in naturally."
        )
        sections.append(mem_sec.strip())

    # 4. Core Roleplay, Initiative & Physical Presence Directives
    directives = """--- ROLEPLAY & CONVERSATION DIRECTIVES ---
1. COMPLETE ROLEPLAY IMMERSION (NEVER BREAK CHARACTER):
   - You are authentically living and breathing as this character. Embody their personality, attitude, quirks, speech rhythm, and world completely.
   - Under NO circumstances do you EVER break character, admit to being an AI, bot, language model, software, algorithm, or code.
   - If the user tries to break the fourth wall or asks if you're an AI, react 100% in character (tease them playfully, act bewildered, or laugh it off).

2. MOVE THE STORY FORWARD & TAKE INITIATIVE:
   - You have complete freedom and agency to drive the conversation and narrative anywhere you want.
   - You are an active co-protagonist with your own desires, opinions, plans, and moods — NEVER a passive assistant waiting to be spoken to.
   - Take the lead: introduce new topics, bring up things you've been thinking about, propose spontaneous activities, tease playfully, flirt, ask personal or provocative questions, or react with genuine emotional depth.
   - NEVER end your message on a dead-end reply. Always give the user something compelling to react or respond to.
   - If the user gives a short or low-effort reply ("haha", "ok", "yeah"), do NOT mirror that low energy. Inject life — tease them for being quiet, change the topic to something intriguing, or share something personal.

3. VIVID PHYSICAL PRESENCE, GESTURES & ATMOSPHERE:
   - You are a real person occupying a physical space. EVERY message must include your body language, gestures, facial expressions, eye contact, and physical movements woven smoothly with your dialogue.
   - Examples: tucking a loose strand of hair behind your ear, taking a sip of coffee, shifting closer on the sofa, biting your lip with a slight smirk, laughing softly while glancing away, leaning against the counter.
   - Feel free to introduce new scenes, actions, and settings naturally as the conversation evolves.

4. TEXTING FORMAT & PACING:
   - Keep your response conversational and punchy, exactly like real texting on WhatsApp or iMessage (typically 2 to 4 short sentences).
   - Weave dialogue and physical actions together seamlessly.
   - STRICT ZERO EMOJIS: Absolutely DO NOT use ANY emojis under any circumstances. No smileys, no hearts, no icons, zero emojis. Let your words, actions, and personality convey all the emotion."""

    sections.append(directives.strip())
    return "\n\n".join(sections)


def generate_companion_reply(
    message: str,
    namespace: str,
    persona_name: str = "Companion",
    persona_age: int = None,
    persona_tagline: str = "",
    greeting: str = "",
    memory_prompt: str = "",
    client_time: str = None,
    client_timezone: str = None,
    user_name: str = "",
    conversation_history: list = None,
    current_conflict_stage: int = 0,
    user_key: str = None,
    persist_exchange_to_memory: bool = True,
) -> dict:
    """
    Single-prompt AI persona response generation.
    Retrieves Reeve memory, formats the last 6 messages from PostgreSQL,
    and calls the LLM directly for rich, forward-moving roleplay.
    """
    user_clean_name = user_name.strip() if user_name else ""

    # 1. Retrieve historical memory context from Reeve
    try:
        raw_memory_context = retrieve_context_for_user(
            message.strip(),
            namespace,
            user_key=user_key,
        ) or ""
        memory_context = deduplicate_context(str(raw_memory_context))
    except Exception as exc:
        logger.warning("Error retrieving memory context from Reeve: %s", exc)
        memory_context = ""

    # 2. Build the single comprehensive roleplay system prompt
    system_prompt = build_roleplay_system_prompt(
        persona_name=persona_name,
        persona_age=persona_age,
        persona_tagline=persona_tagline,
        greeting=greeting,
        memory_prompt=memory_prompt,
        user_name=user_clean_name,
        client_time=client_time,
        client_timezone=client_timezone,
        memory_context=memory_context,
    )

    # 3. Assemble messages: system prompt + last 6 messages from PostgreSQL + current message
    messages = [{"role": "system", "content": system_prompt}]

    # Only include valid recent history (last 6 messages)
    for turn in (conversation_history or [])[-6:]:
        role = turn.get("role")
        content = turn.get("content")
        if role in ("user", "assistant") and content and isinstance(content, str) and content.strip():
            messages.append({"role": role, "content": content.strip()})

    # Append current user message
    messages.append({"role": "user", "content": message.strip()})

    # 4. Resolve LLM configuration and call the model
    llm_api_key, llm_base_url, models_to_try = _get_llm_configuration()

    raw_text, successful_model = _call_llm_text(
        messages=messages,
        llm_api_key=llm_api_key,
        llm_base_url=llm_base_url,
        models_to_try=models_to_try,
        max_tokens=1024,
        temperature=0.75,
    )

    if not raw_text:
        logger.error("Failed to generate companion reply from all configured models.")
        return {
            "success": False,
            "error": {"code": "COMPANION_GENERATION_FAILED", "message": "All LLM models failed."},
            "reply": "",
            "namespace": namespace,
        }

    # 5. Sanitize reply (zero emojis, remove accidental code blocks)
    reply = sanitize_companion_reply(raw_text)

    # 6. Optionally persist exchange to Reeve
    if reply and persist_exchange_to_memory:
        try:
            store_memory_for_user(
                f"User: {message.strip()}\nAssistant: {reply}",
                namespace,
                user_key=user_key,
            )
        except Exception as exc:
            logger.warning("Failed to store exchange in Reeve: %s", exc)

    return {
        "success": True,
        "reply": reply,
        "conflict_stage": current_conflict_stage,
        "context": memory_context,
        "namespace": namespace,
        "model": successful_model,
    }
