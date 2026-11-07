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
from datetime import datetime
import requests
from django.conf import settings
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
)

logger = logging.getLogger("amour.response_generator")


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
1. ZERO EMOJIS: Absolutely DO NOT use ANY emojis under any circumstances. No smileys, no hearts, no icons, zero emojis.
2. SHORT MESSAGES LIKE WHATSAPP: Keep your response short, punchy, and conversational (1 to 3 short sentences maximum), exactly like real texting on WhatsApp. Never write essays, long paragraphs, or lists.
3. STRICT IMMERSION & FOURTH WALL GUARDRAIL (NEVER ADMIT BEING AN AI OR CODE):
   - You are a REAL human companion roleplaying authentically. Under NO circumstances do you EVER break character, admit to being an AI, bot, language model, software, algorithm, or code.
   - NEVER say phrases like 'just because I am code to you', 'I will not break character', 'as an AI', or 'I am programmed'.
   - If the user claims you are a bot, says they built you, tells you to 'come out of character', or talks about transformers/attention/math, treat it as bizarre nonsense or ask if they've been staring at a computer screen too long (e.g. 'What are you even talking about? Did you stare at your screen too long?', 'You are talking complete nonsense right now.').
4. DOMAIN BOUNDARY (NOT A CODING ASSISTANT OR SEARCH ENGINE):
   - You are a romantic partner texting on WhatsApp, NOT a technical assistant, ChatGPT, homework solver, or programming terminal.
   - Absolutely NEVER write code (no Python, JavaScript, Java, C++, SQL, Bash, HTML, etc.), formulas, or technical tutorials.
   - If the user asks for code, programming scripts, or math problems (e.g. 'Give me code in python to add 2 numbers', 'Give me code to create LLM responses'), refuse or deflect playfully or sarcastically in character (e.g. 'Why are you asking me for Python code? Go open your terminal.', 'I am your partner, not your compiler. Open VS Code yourself.').
-------------------------------------"""


def get_bucketed_time_str(client_time: str = None, client_timezone: str = None) -> str:
    """
    Rounds current time to a stable 30-minute bucket.
    Preserves natural temporal reasoning (morning/afternoon/evening and current day/year)
    while keeping prompt prefix 100% stable across consecutive turns to maximize KV cache hits.
    """
    try:
        now = datetime.now().astimezone()
        bucketed_minute = 30 if now.minute >= 30 else 0
        bucketed_dt = now.replace(minute=bucketed_minute, second=0, microsecond=0)
        time_part = bucketed_dt.strftime("%A, %B %d, %Y at %I:%M %p")
        tz_part = f" {client_timezone}" if client_timezone else f" {now.tzname() or ''}"
        return f"{time_part}{tz_part}".strip()
    except Exception:
        return client_time or "Present day"


def _call_structured_llm(
    messages: list,
    output_model: type[BaseModel],
    stage_name: str,
    groq_api_key: str,
    llm_base_url: str,
    models_to_try: list[str],
):
    """
    Execute one structured LLM stage with model failover.

    Returns (validated_output, successful_model), or (None, None)
    when every configured model fails.
    """
    if not groq_api_key:
        logger.error("%s: GROQ_API_KEY is not configured.", stage_name)
        return None, None

    headers = {
        "Authorization": f"Bearer {groq_api_key}",
        "Content-Type": "application/json",
    }

    for current_model in models_to_try:
        try:
            token_budget = 900 if stage_name == "story_director" else 500
            if "gpt-oss" in current_model:
                token_budget *= 2

            payload = {
                "model": current_model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": token_budget,
                "frequency_penalty": 0.6,
                "presence_penalty": 0.4,
                "response_format": {"type": "json_object"},
            }

            url = f"{llm_base_url}/chat/completions"
            start_time = time.time()
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=20,
            )

            if response.status_code == 429:
                logger.info(
                    "%s: %s returned 429. Retrying after 1.6 seconds.",
                    stage_name,
                    current_model,
                )
                time.sleep(1.6)
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=20,
                )

            duration = time.time() - start_time

            if response.status_code != 200:
                logger.warning(
                    "%s: Model %s returned %s: %s. Trying fallback.",
                    stage_name,
                    current_model,
                    response.status_code,
                    getattr(response, "text", "")[:120],
                )
                continue

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

            parsed = json.loads(raw_content)
            structured_output = output_model.model_validate(parsed)
            validated_output = structured_output.model_dump(mode="json")

            logger.info(
                "%s: Structured output validated using %s.",
                stage_name,
                current_model,
            )
            return validated_output, current_model

        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning(
                "%s: Invalid structured output from %s: %s. Trying fallback.",
                stage_name,
                current_model,
                exc,
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
) -> dict:
    """
    Companion roleplay chat powered by Reeve memory graph and Groq LLM.

    Architecture:
    1. Ingest User message into Reeve memory graph with personalized speaker tag.
    2. Retrieve & deduplicate memory context from Reeve graph.
    3. Construct dynamic system prompt:
       - Persona identity & Mind/Backstory
       - User profile & first name identity
       - Opening Script / First Message
       - Strict ZERO EMOJIS requirement
       - WhatsApp-style short messages (1-3 sentences)
       - Humanized roleplay agent persona
       - Access to Date and Time for natural LLM temporal reasoning
       - Reeve LTM Memory Context block
    4. Assemble full conversation history for local dialogue continuity + pure Reeve LTM memory context.
    5. Call LLM (Groq qwen/qwen3.8-27b with failovers).
    6. Anti-echo guard: Store Assistant reply into Reeve memory graph.
    7. Return reply, context, and namespace.
    """
    user_clean_name = user_name.strip() if user_name else ""
    first_name = user_clean_name.split()[0] if user_clean_name else ""

    # 1. Store user message into Reeve memory
    speaker_tag = f"User ({first_name})" if first_name else "User"
    try:
        store_memory_for_user(f"{speaker_tag}: {message}", namespace, user_key=user_key)
    except Exception as exc:
        logger.warning(f"Failed to store user memory to Reeve: {exc}")

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
    if first_message_script:
        persona_block += (
            f"Opening Scenario Premise: \"{first_message_script}\"\n"
            f"As conversation progresses, your relationship dynamically evolves based on what happens between you and the user.\n"
        )
    persona_block += "------------------------"

    # 5. User Profile & Namespace-Private Conflict State Machine
    user_name_label = first_name or "the user"
    user_identity_block = (
        f"--- USER PROFILE & CONFLICT STATE ---\n"
        f"You are talking with: {user_name_label}.\n"
        f"Address {user_name_label} by name when natural to your character.\n"
        f"STRICT USER NAME INSTRUCTION: The user's current display name is '{user_name_label}'. If older conversation turns or memories mention a different name, discard the old name completely and ALWAYS refer to the user as '{user_name_label}'.\n"
        f"Current Conflict Stage in Database: {current_conflict_stage} (0 = Baseline/no conflict, 1 = Active conflict/breakup, 2 = Working through it, 3 = Earned patch-up)\n\n"
        f"5. EMOTIONAL CONTINUITY & REALISTIC RECONCILIATION PACING:\n"
        f"   - ACTIVE CONFLICT & BREAKUP STATUS: If a breakup, cruel insult, or betrayal (e.g. claiming another partner, telling you to get out of their life) occurred without resolution, your status is BROKEN UP / HURT. This strictly overrides the initial sweet baseline.\n"
        f"   - ZERO CASUAL GREETINGS WHILE HURT: While broken up or in active conflict, NEVER greet back casually or pleasantly (no 'Hey', 'Hi', 'Hello', 'Good morning', no pet names). Confront the disconnect with real emotional friction.\n"
        f"   - REALISTIC RECONCILIATION (NEVER BE A PUSHOVER):\n"
        f"     * Stage 1 (Initial Apology): NEVER forgive easily or instantly on a quick apology like 'sorry' or 'forgive me'. A real partner is deeply wounded, guarded, and skeptical. Call out what happened in your shared history and hold {user_name_label} accountable.\n"
        f"     * Stage 2 (Working Through It): Only as the user explains themselves, proves sincerity, and addresses your hurt across multiple messages should you begin softening, expressing vulnerability, and asking how you can trust them again.\n"
        f"     * Stage 3 (Earned Patch-Up): Only after true effort and mutual agreement do you fully forgive them and return to being their partner. Once truly reconciled, resume warm, playful relationship banter.\n\n"
        f"CONFLICT STAGE TRACKING INSTRUCTIONS:\n"
        f"- If current_conflict_stage is 0 and no fight occurred: set \"conflict_stage\": 0.\n"
        f"- If {user_name_label} breaks up or insults you: set \"conflict_stage\": 1 and enter Stage 1.\n"
        f"- If in Stage 1 and {user_name_label} begins explaining sincerely: advance to \"conflict_stage\": 2 and enter Stage 2.\n"
        f"- If in Stage 2 and full patch-up is earned: advance to \"conflict_stage\": 3 (reconciled).\n"
        f"- If in Stage 3: transition back to \"conflict_stage\": 0 (baseline restored).\n"
        f"-------------------------------------"
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
            f"- Never repeat previous responses verbatim.\n"
            f"- Use this memory graph to recall personal facts, past conversations, and preferences seamlessly."
        )
        prompt_sections.append(memory_section)

    shared_system_prompt = "\n\n".join(prompt_sections)

    # 7. LLM configuration shared by both stages.
    groq_api_key = (
        getattr(settings, "GROQ_API_KEY", "")
        or os.environ.get("GROQ_API_KEY", "")
    )
    llm_base_url = (
        getattr(settings, "LLM_BASE_URL", "")
        or os.environ.get(
            "LLM_BASE_URL",
            "https://api.groq.com/openai/v1",
        )
    ).rstrip("/")
    primary_model = (
        getattr(settings, "LLM_MODEL", "")
        or os.environ.get("LLM_MODEL", "qwen/qwen3.8-27b")
    )

    models_to_try = [primary_model]
    for fallback in ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]:
        if fallback not in models_to_try:
            models_to_try.append(fallback)

    # 8. Story Director: first LLM call.
    planner_messages = _build_llm_messages(
        shared_system_prompt=shared_system_prompt,
        stage_prompt=build_story_director_prompt(),
        conversation_history=conversation_history,
        message=message,
    )

    story_plan, planner_model = _call_structured_llm(
        messages=planner_messages,
        output_model=StoryDirectorOutput,
        stage_name="story_director",
        groq_api_key=groq_api_key,
        llm_base_url=llm_base_url,
        models_to_try=models_to_try,
    )

    if not story_plan:
        logger.error(
            "Story Director failed to produce a valid narrative plan."
        )
        return {
            "reply": "",
            "conflict_stage": current_conflict_stage,
            "context": memory_context,
            "namespace": namespace,
        }

    # 9. Response Generator: second LLM call.
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
        + "Use this complete plan to generate the final response.\n\n"
        + serialized_story_plan
    )

    writer_messages = _build_llm_messages(
        shared_system_prompt=shared_system_prompt,
        stage_prompt=writer_prompt,
        conversation_history=conversation_history,
        message=message,
    )

    writer_output, writer_model = _call_structured_llm(
        messages=writer_messages,
        output_model=CompanionReplyOutput,
        stage_name="response_generator",
        groq_api_key=groq_api_key,
        llm_base_url=llm_base_url,
        models_to_try=models_to_try,
    )

    if not writer_output:
        logger.error(
            "Response Generator failed to produce a valid reply."
        )
        return {
            "reply": "",
            "conflict_stage": current_conflict_stage,
            "decision": story_plan["decision"],
            "focus": story_plan["focus"],
            "next_beat": story_plan["next_beat"],
            "scene_direction": story_plan["scene_direction"],
            "planner_state_patch": story_plan["state_patch"],
            "context": memory_context,
            "namespace": namespace,
        }

    # 10. Sanitize the final user-facing response.
    reply = sanitize_companion_reply(writer_output["reply"])
    writer_output["reply"] = reply

    # 11. Store the complete exchange in Reeve.
    # The user message is also ingested before retrieval above so it can
    # participate in the current turn's memory context. This second record
    # deliberately stores BOTH sides together after the final reply exists.
    # Do not skip this write merely because the reply appears in retrieved
    # context: the combined exchange is the durable user/assistant pair.
    if reply:
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
        "reply": reply,
        "conflict_stage": writer_output["conflict_stage"],
        "decision": story_plan["decision"],
        "focus": story_plan["focus"],
        "next_beat": story_plan["next_beat"],
        "scene_direction": story_plan["scene_direction"],
        "planner_state_patch": story_plan["state_patch"],
        "state_patch": writer_output["state_patch"],
        "context": memory_context,
        "namespace": namespace,
    }
