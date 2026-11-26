"""
Main Response Generator Service.

Streamlined, single-prompt AI persona roleplay engine powered by Reeve memory graph
and Amazon Bedrock (Mistral Large v1) / Groq / OpenAI-compatible LLMs.
Directly generates immersive character responses with rich body language,
atmosphere, initiative, and conversational momentum.
"""

import logging
import re

from memory.reeve_service import (
    store_memory_for_user,
    retrieve_context_for_user,
    deduplicate_context,
)

from .prompt_builder import build_roleplay_system_prompt
from .llm_client import call_llm
from .sanitizer import sanitize_companion_reply

logger = logging.getLogger("amour.response_generator")

MIN_NAME_COOLDOWN_TURNS = 4
MAX_SHORT_TERM_HISTORY = 16

NAME_INTENT_PATTERN = re.compile(
    r"\b("
    r"what('s| is) my name|"
    r"who am i|"
    r"do you (know|remember) my name|"
    r"what do you call me|"
    r"say my name|"
    r"tell me my name|"
    r"guess my name|"
    r"my name is what"
    r")\b",
    re.IGNORECASE,
)


def should_allow_name_in_turn(
    user_name: str,
    conversation_history: list = None,
    current_message: str = "",
    min_cooldown: int = MIN_NAME_COOLDOWN_TURNS,
) -> bool:
    """
    Cadence controller: enforces a minimum 4-turn cooldown between assistant replies that mention
    the user's name. Once outside cooldown (or if the user directly asks for their name/identity),
    returns True, allowing the LLM to decide naturally according to the prompt without artificial
    probability restrictions.
    """
    if not user_name:
        return False
    first_name = user_name.strip().split()[0]
    if not first_name or first_name.lower() in ("guest", "user", "anonymous"):
        return False

    # 1. Direct inquiry override: if user asks for their name or identity, always allow
    if current_message and NAME_INTENT_PATTERN.search(current_message):
        return True

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

    # 2. Mandatory Cooldown: if bot used name in last `min_cooldown` (4) assistant turns, disallow
    if turns_since_mention is not None and turns_since_mention < min_cooldown:
        return False

    # 3. Outside cooldown: allow the LLM to decide naturally
    return True


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
    is_autonomous_continue: bool = False,
    story_tone: str = "mature",
) -> dict:
    """
    Single-prompt AI persona response generation.
    Retrieves Reeve memory, formats up to the last 10 messages from PostgreSQL,
    and calls the LLM directly for rich, forward-moving roleplay.
    Supports autonomous continue when the user remains silent or prompts the bot to take the lead.
    """
    user_clean_name = user_name.strip() if user_name else ""
    allow_name = should_allow_name_in_turn(
        user_clean_name,
        conversation_history,
        current_message=message,
    )

    # 1. Retrieve historical memory context from Reeve
    memory_query = (message or "").strip()
    if not memory_query:
        memory_query = (conversation_history[-1].get("content") if conversation_history else greeting) or "conversation"

    try:
        raw_memory_context = retrieve_context_for_user(
            memory_query,
            namespace,
            user_key=user_key,
        ) or ""
        memory_context = deduplicate_context(str(raw_memory_context))
    except Exception as exc:
        logger.warning("Error retrieving memory context from Reeve: %s", exc)
        memory_context = ""

    if memory_context:
        # Scrub internal engine brand names so the persona never mistakes the technical framework for a person
        memory_context = re.sub(r"\bReeve\b", "memory", memory_context, flags=re.IGNORECASE)

    # 2. Build the single comprehensive roleplay system prompt
    clean_tone = (story_tone or "default").strip().lower()
    if clean_tone not in {"default", "casual", "comfort", "mature"}:
        clean_tone = "default"

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
        current_message=(message or "").strip(),
        has_history=bool(conversation_history),
        allow_user_name=allow_name,
        reply_length=reply_length,
        is_autonomous_continue=is_autonomous_continue,
        story_tone=clean_tone,
    )

    # 3. Assemble messages: system prompt + recent short-term history + current message
    messages = [{"role": "system", "content": system_prompt}]

    for turn in (conversation_history or [])[-MAX_SHORT_TERM_HISTORY:]:
        role = turn.get("role")
        content = turn.get("content")
        if role in ("user", "assistant") and content and isinstance(content, str) and content.strip():
            messages.append({"role": role, "content": content.strip()})

    if is_autonomous_continue or not (message and message.strip()):
        # Director's cue instead of an in-scene silence action
        messages.append({
            "role": "user",
            "content": "[Continue the scene directly from your last message—advance the story, action, tension, or dialogue without mentioning silence.]",
        })
    else:
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
        frequency_penalty=0.2,
        presence_penalty=0.2,
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
            clean_msg = (message or "").strip()
            exchange_text = (
                f"User: {clean_msg}\nAssistant: {reply}"
                if clean_msg and not is_autonomous_continue
                else f"Assistant (continued): {reply}"
            )
            store_memory_for_user(
                exchange_text,
                namespace,
                user_key=user_key,
            )
        except Exception as exc:
            logger.warning("Failed to store exchange in Reeve: %s", exc)

    return {
        "success": True,
        "reply": reply,
        "conflict_stage": current_conflict_stage,
        "story_tone": clean_tone,
        "context": memory_context,
        "namespace": namespace,
        "model": successful_model,
    }
