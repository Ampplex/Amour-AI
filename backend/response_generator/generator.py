"""
Main Response Generator Service.

Streamlined, single-prompt AI persona roleplay engine powered by Reeve memory graph
and Amazon Bedrock (Mistral Large v1) / Groq / OpenAI-compatible LLMs.
Directly generates immersive character responses with rich body language,
atmosphere, initiative, and conversational momentum.
"""

import logging

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
        has_history=bool(conversation_history),
    )

    # 3. Assemble messages: system prompt + last 6 messages from PostgreSQL + current message
    messages = [{"role": "system", "content": system_prompt}]

    for turn in (conversation_history or [])[-6:]:
        role = turn.get("role")
        content = turn.get("content")
        if role in ("user", "assistant") and content and isinstance(content, str) and content.strip():
            messages.append({"role": role, "content": content.strip()})

    messages.append({"role": "user", "content": message.strip()})

    # 4. Direct LLM call with fallback model chain
    raw_text, successful_model = call_llm(
        messages=messages,
        max_tokens=1024,
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
