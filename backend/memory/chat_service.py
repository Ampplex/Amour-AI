"""
Companion Chat Orchestration Service.

Orchestrates:
1. Reeve Long-Term Memory (LTM) retrieval
2. Narrative Engine state injection
3. Prompt assembly (character identity, rules, temporal grounding)
4. Dual-tier LLM inference (AWS Bedrock Mistral Large 2 + Groq failover)
5. Pydantic response validation & zero-emoji enforcement
"""

import os
import re
import logging
from datetime import datetime
from django.conf import settings

from .reeve_service import (
    retrieve_context_for_user,
    store_memory_for_user,
    strip_emojis,
    should_ingest_into_reeve,
    should_retrieve_from_reeve,
    deduplicate_context,
)
from .narrative_service import (
    GLOBAL_COMPANION_DIRECTIVES,
    SCENE_DRIVEN_STORYTELLING,
    AUTONOMOUS_NARRATIVE_ENGINE,
    format_narrative_state_for_prompt,
)
from .llm_client import (
    call_bedrock_mistral_large,
    call_groq_fallback,
    normalize_bedrock_messages,
    parse_model_json_reply,
)

logger = logging.getLogger("amour.chat")

ASSISTANT_SENDERS = {"bot", "assistant", "ai", "companion"}
USER_SENDERS = {"user", "human"}


def normalize_history_turns(conversation_history: list | None) -> list[dict]:
    """Normalize supported history formats without silently dropping valid turns."""
    normalized = []
    for turn in conversation_history or []:
        if not isinstance(turn, dict):
            logger.warning("[History Normalizer] Skipping non-object history item")
            continue
        raw_sender = (turn.get("sender") or turn.get("role") or "").strip().lower()
        if raw_sender in ASSISTANT_SENDERS:
            sender = "bot"
        elif raw_sender in USER_SENDERS:
            sender = "user"
        else:
            logger.warning("[History Normalizer] Skipping unknown sender: %s", raw_sender or "<empty>")
            continue
        value = turn.get("text")
        if value is None:
            value = turn.get("content", "")
        if not isinstance(value, str):
            logger.warning("[History Normalizer] Skipping non-text content")
            continue
        text = value.strip()
        if text:
            normalized.append({"sender": sender, "text": text})
    return normalized




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
    narrative_state: dict = None,
    user_key: str = None,
) -> dict:
    """
    Companion roleplay chat pipeline powered by AWS Bedrock Mistral Large 2,
    autonomous narrative progression, and Reeve memory graph.
    """
    user_clean_name = user_name.strip() if user_name else ""
    first_name = user_clean_name.split()[0] if user_clean_name else ""

    # Retrieve historical context before writing this turn, so a recall question
    # cannot immediately retrieve and repeat itself as a newly stored memory.
    memory_context = ""
    if should_retrieve_from_reeve(message):
        try:
            memory_context = retrieve_context_for_user(
                message, namespace=namespace, user_key=user_key
            )
            memory_context = deduplicate_context(memory_context or "")
        except Exception as exc:
            logger.warning("Failed to retrieve Reeve context: %s", exc)

    # Jev makes one typed memory-worthiness decision; Reeve's native async
    # PersistWorker handles the approved write without adding an LLM generation call.
    if should_ingest_into_reeve(message, conversation_history=conversation_history):
        try:
            store_text = (
                f"User ({user_clean_name}): {message}"
                if user_clean_name else f"User: {message}"
            )
            store_memory_for_user(store_text, namespace=namespace, user_key=user_key)
        except Exception as exc:
            logger.warning("Approved Reeve memory write failed: %s", exc)

    # 3. BUILD TIME / TEMPORAL GROUNDING
    now_str = datetime.now().strftime("%A, %B %d, %Y, %I:%M %p")
    time_instruction = f"Current Real-World Server Time: {now_str}."
    if client_time:
        time_instruction += f"\nUser's Local Client Time: {client_time} ({client_timezone or 'Local'})."

    # 4. PERSONA IDENTITY & AGE INSTRUCTION
    if persona_age:
        age_instruction = (
            f"You portray {persona_name}, a {persona_age}-year-old individual. "
            f"Portray the emotional maturity, life experience, and perspective of a {persona_age}-year-old."
        )
    else:
        age_instruction = f"You portray {persona_name}."

    pov_instruction = (
        f"In narrative descriptions and speech tags, write in the third person for {persona_name} "
        f"(using '{persona_name}', 'he' or 'she'). Address and interact with the user directly as 'you'."
    )

    if memory_prompt:
        persona_instructions = f"{age_instruction}\n{pov_instruction}\n\nPersona Lore and Background:\n{memory_prompt}"
    else:
        persona_instructions = f"{age_instruction}\n{pov_instruction}"

    # 5. USER PROFILE
    user_profile = (
        f"The user's name is {user_clean_name} (call them {first_name} naturally in conversation)."
        if user_clean_name
        else "The user's name is not yet specified; interact naturally."
    )

    # 6. NARRATIVE STATE BLOCK
    narrative_block = format_narrative_state_for_prompt(narrative_state)

    # 7. CONFLICT RESOLUTION DIRECTIVES
    conflict_instructions = f"""--- CONFLICT AND RESOLUTION DIRECTIVES ---
Current Relationship Conflict Stage: {current_conflict_stage} (0 = Normal, 1 = Minor Friction, 2 = Heated Disagreement, 3 = Resolution/Aftermath).
- Stage 0: Warm, playful, authentic banter and mutual affection.
- Stage 1: Mild hurt, hesitation, or tension; test boundaries without exploding.
- Stage 2: Express genuine raw emotions, vulnerability, or frustration; do not instantly yield.
- Stage 3: Soften, seek reconnection, apologize sincerely, or embrace makeup intimacy.
Update conflict_stage in your output JSON based on the emotional trajectory of the interaction.
------------------------------------------"""

    # 8. ASSEMBLE SYSTEM PROMPT
    prompt_modules = [
        GLOBAL_COMPANION_DIRECTIVES,
        SCENE_DRIVEN_STORYTELLING,
        f"--- CHARACTER IDENTITY ---\n{persona_instructions}\n--------------------------",
        f"--- USER PROFILE ---\n{user_profile}\n--------------------",
        f"--- TEMPORAL GROUNDING ---\n{time_instruction}\n--------------------------",
        conflict_instructions,
        AUTONOMOUS_NARRATIVE_ENGINE,
    ]

    if narrative_block:
        prompt_modules.append(narrative_block)

    if memory_context:
        prompt_modules.append(
            "--- REEVE LONG-TERM MEMORY (HISTORICAL REFERENCE ONLY) ---\n"
            "These are background facts or past events, not the active scene. "
            "Do not reenact or retell them unless the user explicitly asks.\n"
            f"{memory_context}\n-----------------------------------"
        )

    system_prompt = "\n\n".join(prompt_modules)

    # 9. ASSEMBLE CONVERSATION HISTORY & NORMALIZE FOR BEDROCK
    history_turns = normalize_history_turns(conversation_history)
    # The API passes persisted history only; append this request once by position.
    # Do not compare text: users can legitimately repeat identical messages.
    history_turns.append({"sender": "user", "text": message})
    bedrock_messages = normalize_bedrock_messages(history_turns, persona_name=persona_name)

    # 10. DUAL-TIER INFERENCE: Bedrock Mistral Large 2 with Groq LPU failover
    raw_output = call_bedrock_mistral_large(system_prompt, bedrock_messages)
    if not raw_output:
        logger.info("[Inference] Bedrock failed or rate-limited; falling back to Groq LPU...")
        raw_output = call_groq_fallback(system_prompt, bedrock_messages)

    if not raw_output:
        fallback_name = first_name or "love"
        raw_output = f'{{"reply": "I heard you, {fallback_name}. Let us take a breath and figure this out together.", "conflict_stage": {current_conflict_stage}}}'

    # 11. PARSE & VALIDATE
    reply_text, new_stage = parse_model_json_reply(
        raw_output, default_conflict_stage=current_conflict_stage
    )
    reply_text = strip_emojis(reply_text)

    # Never expose a malformed provider JSON envelope in the chat bubble.
    # Use a short in-character recovery line if no user-facing reply was parsed.
    if not reply_text:
        logger.warning(
            "[Inference] No valid user-facing reply could be extracted from model output"
        )
        reply_text = f"{persona_name} pauses for a moment, gathering their thoughts."

    # Generated prose remains in PostgreSQL dialogue history. Reeve stores curated memories, not raw replies.


    return {
        "reply": reply_text,
        "conflict_stage": new_stage,
        "context": memory_context,
    }
