"""
Main Response Generator Service.

Streamlined, single-prompt AI persona roleplay engine powered by Reeve memory graph
and Amazon Bedrock (Mistral Large v1) / Groq / OpenAI-compatible LLMs.
Directly generates immersive character responses with rich body language,
atmosphere, initiative, and conversational momentum.
"""

import logging
import random
import re

from memory.reeve_service import (
    store_memory_for_user,
    retrieve_context_for_user,
    deduplicate_context,
)

from .prompt_builder import (
    get_bucketed_time_str,
    build_roleplay_system_prompt,
)
from .llm_client import call_llm
from .sanitizer import (
    strip_emojis,
    sanitize_companion_reply,
)

logger = logging.getLogger("amour.response_generator")

MIN_NAME_COOLDOWN_TURNS = 4
NAME_TRIGGER_PROBABILITY = 0.20
MAX_SILENCE_TURNS = 10


def should_allow_name_in_turn(
    user_name: str,
    conversation_history: list = None,
    min_cooldown: int = MIN_NAME_COOLDOWN_TURNS,
    probability: float = NAME_TRIGGER_PROBABILITY,
    max_silence: int = MAX_SILENCE_TURNS,
) -> bool:
    """
    Cadence controller: ensures the persona uses the user's name only occasionally
    and never in consecutive replies. Enforces a minimum cooldown of 4 assistant messages.
    """
    if not user_name:
        return False
    first_name = user_name.strip().split()[0]
    if not first_name or first_name.lower() in ("guest", "user", "anonymous"):
        return False

    bot_turns = [
        turn.get("content", "")
        for turn in (conversation_history or [])
        if turn.get("role") == "assistant"
    ]
    name_pat = re.compile(rf"\b{re.escape(first_name)}\b", re.IGNORECASE)

    turns_since_mention = None
    for idx, content in enumerate(reversed(bot_turns)):
        if name_pat.search(content):
            turns_since_mention = idx
            break

    # 1. Mandatory Cooldown: if bot used name in last `min_cooldown` assistant turns, strictly disallow
    if turns_since_mention is not None and turns_since_mention < min_cooldown:
        return False

    # 2. Maximum Silence: if 10+ assistant turns passed without name, allow eligibility
    if turns_since_mention is not None and turns_since_mention >= max_silence:
        return True

    # 3. Outside cooldown: roll natural probability (~20% chance)
    return random.random() < probability


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
    reply_length: str = "default",
) -> dict:
    """
    Single-prompt AI persona response generation.
    Retrieves Reeve memory, formats the last 6 messages from PostgreSQL,
    and calls the LLM directly for rich, forward-moving roleplay.
    """
    user_clean_name = user_name.strip() if user_name else ""
    allow_name = should_allow_name_in_turn(user_clean_name, conversation_history)

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
        current_message=message.strip(),
        has_history=bool(conversation_history),
        allow_user_name=allow_name,
        reply_length=reply_length,
    )

    # 3. Assemble messages: system prompt + last 4 messages as context + current message
    messages = [{"role": "system", "content": system_prompt}]

    for turn in (conversation_history or [])[-4:]:
        role = turn.get("role")
        content = turn.get("content")
        if role in ("user", "assistant") and content and isinstance(content, str) and content.strip():
            messages.append({"role": role, "content": content.strip()})

    messages.append({"role": "user", "content": message.strip()})

    # 4. Direct LLM call with fallback model chain & generous token runways to eliminate truncation
    clean_length = (reply_length or "default").strip().lower()
    if clean_length == "short":
        # 768 tokens: prompt strictly mandates 1-2 sentences, generous headroom guarantees zero truncation
        target_max_tokens = 768
    elif clean_length == "long":
        # 3072 tokens: abundant headroom allows full 3-4 rich paragraphs to complete naturally
        target_max_tokens = 3072
    else:
        # 2048 tokens: 2x original headroom so adaptive scenes never get cut off mid-thought
        target_max_tokens = 2048

    raw_text, successful_model = call_llm(
        messages=messages,
        max_tokens=target_max_tokens,
        temperature=0.88,
    )

    if not raw_text:
        logger.error("Failed to generate companion reply from all configured models.")
        return {
            "success": False,
            "error": {"code": "COMPANION_GENERATION_FAILED", "message": "All LLM models failed."},
            "reply": "",
            "namespace": namespace,
        }

    # 5. Sanitize reply (zero emojis, remove accidental code blocks, clean name vocatives)
    reply = sanitize_companion_reply(
        raw_text,
        user_name=user_clean_name,
        allow_name=allow_name,
    )

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
