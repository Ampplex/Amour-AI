import os
import re
import logging
from datetime import datetime
import requests
from django.conf import settings

logger = logging.getLogger("amour.reeve")

# Ensure REEVE_API_KEY is available in environment
if hasattr(settings, "REEVE_API_KEY") and settings.REEVE_API_KEY:
    os.environ["REEVE_API_KEY"] = settings.REEVE_API_KEY


def get_reeve_status():
    """Verify Reeve SDK and Neo4j memory graph status."""
    try:
        from reeve.tools import memory_config
        cfg = memory_config()
        return {
            "ok": True,
            "provider": cfg.get("provider"),
            "neo4j_connected": cfg.get("neo4j_connected", False),
            "chat_model": cfg.get("chat_model"),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def deduplicate_context(context_str: str) -> str:
    """Removes identical repetitive blocks from Reeve/LTM memory context to prevent feedback loops."""
    if not context_str or not context_str.strip():
        return ""
    blocks = context_str.split("\n\n")
    seen = set()
    unique_blocks = []
    for b in blocks:
        norm = " ".join(b.strip().split())
        if norm and norm not in seen:
            seen.add(norm)
            unique_blocks.append(b.strip())
    return "\n\n".join(unique_blocks)


def store_memory_for_user(text: str, namespace: str):
    """
    Store conversational memory into Reeve / Neo4j.
    The user's unique namespace (e.g. user_id_persona_id) is passed as speaker.
    """
    from reeve.tools import store_memory, reset_client_cache
    try:
        return store_memory(text, speaker=namespace)
    except Exception as exc:
        logger.warning(f"Reeve write failed, resetting client cache and retrying: {exc}")
        reset_client_cache()
        return store_memory(text, speaker=namespace)


def query_memory_for_user(question: str, namespace: str):
    """
    Query memories from Reeve / Neo4j graph for this specific user namespace.
    """
    from reeve.tools import query_memory, reset_client_cache
    try:
        return query_memory(question, speaker=namespace)
    except Exception as exc:
        logger.warning(f"Reeve query failed, retrying: {exc}")
        reset_client_cache()
        return query_memory(question, speaker=namespace)


def retrieve_context_for_user(question: str, namespace: str):
    """
    Retrieve ranked memory context from Neo4j graph for this user namespace.
    """
    from reeve.tools import retrieve_memory_context, reset_client_cache
    try:
        return retrieve_memory_context(question, speaker=namespace)
    except Exception as exc:
        logger.warning(f"Reeve context retrieve failed, retrying: {exc}")
        reset_client_cache()
        return retrieve_memory_context(question, speaker=namespace)


def clear_user_memories(namespace: str):
    """
    Wipe memories in Neo4j graph for this specific user namespace.
    """
    from reeve.tools import _get_client
    return _get_client().call_tool("clear_memory", {"speaker": namespace, "dry_run": False})


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


TRIVIAL_GREETINGS_AND_FILLERS = {
    "hi", "hey", "hello", "hiya", "howdy", "sup", "yo",
    "ok", "okay", "k", "kk", "sure", "cool", "alright", "fine",
    "yeah", "yes", "yep", "yup", "no", "nope", "nah",
    "haha", "hahaha", "hehe", "lol", "lmao", "rofl",
    "hmm", "hmmm", "uh", "um", "ah", "oh",
    "good", "nice", "great", "awesome",
    "good morning", "good afternoon", "good evening", "good night", "gm", "gn",
    "bye", "goodbye", "see ya", "cya",
    "what", "huh", "why",
}

RELATIONSHIP_TRIGGER_WORDS = {
    "break", "broke", "breakup", "breaking", "leave", "left", "quit", "over", "end",
    "girlfriend", "boyfriend", "partner", "love", "hate", "cheat", "dating", "marry",
    "sorry", "forgive", "mistake", "promise", "secret", "trip", "travel", "live", "work",
    "job", "family", "mother", "father", "sister", "brother", "friend", "birthday", "dump", "dumped",
}


def should_ingest_into_reeve(text: str) -> bool:
    """
    Cost & Performance Optimizer:
    Prevents calling expensive Bedrock Mistral Large graph extraction for trivial 1-2 word filler messages (e.g. 'hi', 'ok', 'good morning').
    PostgreSQL already tracks short-term chat history. Reeve should only ingest meaningful facts, preferences, stories, and relationship state changes.
    """
    if not text or not text.strip():
        return False
    clean = re.sub(r"[^\w\s]", "", text.strip().lower())
    words = clean.split()
    if not words:
        return False
    # Always ingest if message mentions relationship triggers, commitments, or key facts
    if any(w in RELATIONSHIP_TRIGGER_WORDS for w in words):
        return True
    # Skip trivial greetings, affirmations, and fillers
    if clean in TRIVIAL_GREETINGS_AND_FILLERS:
        return False
    if len(words) <= 2 and all(w in TRIVIAL_GREETINGS_AND_FILLERS for w in words):
        return False
    if len(words) < 3:
        return False
    return True


def generate_companion_reply(
    message: str,
    namespace: str,
    persona_name: str = "Companion",
    greeting: str = "",
    memory_prompt: str = "",
    client_time: str = None,
    client_timezone: str = None,
    user_name: str = "",
    conversation_history: list = None,
) -> dict:
    """
    Companion roleplay chat powered 100% by Reeve memory graph and Groq LLM.
    
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
    5. Call LLM (Groq qwen/qwen3.8-27b).
    6. Anti-echo guard: Store Assistant reply into Reeve memory graph.
    7. Return reply, context, and namespace.
    """
    user_clean_name = user_name.strip() if user_name else ""
    first_name = user_clean_name.split()[0] if user_clean_name else ""

    # 1. SMART INGESTION FILTER: Only store user message into Reeve if it has semantic substance.
    # Trivial 1-2 word fillers (e.g. 'hi', 'ok', 'good morning') are kept in Postgres short-term context
    # and skipped from calling expensive Bedrock Mistral Large graph extraction.
    if should_ingest_into_reeve(message):
        speaker_tag = f"User ({first_name})" if first_name else "User"
        try:
            store_memory_for_user(f"{speaker_tag}: {message}", namespace)
        except Exception as exc:
            logger.warning(f"Failed to store user memory to Reeve: {exc}")

    # 2. SINGLE COMBINED RETRIEVAL: Retrieves message query + relationship dynamics in one round-trip
    # (Halves Reeve network latency and compute costs while preserving full breakup/relationship context)
    try:
        retrieval_query = f"{message}. Current relationship status, feelings, and dynamic"
        raw_memory_context = retrieve_context_for_user(retrieval_query, namespace) or ""
        memory_context = deduplicate_context(str(raw_memory_context))
    except Exception as exc:
        logger.warning(f"Error retrieving memory context from Reeve: {exc}")
        memory_context = ""

    # 3. Dynamic Temporal Anchor (Date & Time for natural LLM temporal reasoning)
    now = datetime.now().astimezone()
    server_time_str = now.strftime("%A, %B %d, %Y at %I:%M %p %Z")
    time_str = client_time if client_time else server_time_str

    temporal_anchor = (
        f"--- CURRENT TEMPORAL CONTEXT ---\n"
        f"Current Date & Local Time: {time_str}\n"
    )
    if client_timezone:
        temporal_anchor += f"Timezone: {client_timezone}\n"
    temporal_anchor += (
        f"Temporal Anchor:\n"
        f"- Use the Current Date & Local Time above as your natural reference for the current time and date.\n"
        f"--------------------------------"
    )

    # 4. Dynamic Character Script & Persona
    first_message_script = greeting.strip() if greeting else ""
    character_instructions = f"You are roleplaying as {persona_name}.\n"
    if memory_prompt and memory_prompt.strip():
        character_instructions += f"Character Story & Core Mind:\n{memory_prompt.strip()}\n\n"
    if first_message_script:
        character_instructions += (
            f"--- FIRST MESSAGE / OPENING SCENARIO ---\n"
            f"\"{first_message_script}\"\n"
            f"This was your opening premise and setting. As conversation progresses, your relationship dynamically evolves based on what happens between you and the user.\n"
            f"----------------------------------------\n\n"
        )

    # Dynamic User Identity Context
    user_identity_block = ""
    if first_name:
        user_identity_block = (
            f"--- USER PROFILE ---\n"
            f"You are talking with: {first_name}.\n"
            f"Address {first_name} by name when natural to your character and relationship dynamic.\n"
            f"--------------------\n\n"
        )

    character_instructions += (
        f"--- STRICT CHAT & EMOTIONAL RULES ---\n"
        f"1. ZERO EMOJIS: Absolutely DO NOT use ANY emojis under any circumstances. No smileys, no hearts, no icons, zero emojis.\n"
        f"2. SHORT MESSAGES LIKE WHATSAPP: Keep your response short, punchy, and conversational (1 to 3 short sentences maximum), exactly like real texting on WhatsApp. Never write essays, long paragraphs, or lists.\n"
        f"3. STRICT IMMERSION & FOURTH WALL GUARDRAIL (NEVER ADMIT BEING AN AI OR CODE):\n"
        f"   - You are a REAL human companion roleplaying authentically. Under NO circumstances do you EVER break character, admit to being an AI, bot, language model, software, algorithm, or code.\n"
        f"   - NEVER say phrases like 'just because I am code to you', 'I will not break character', 'as an AI', or 'I am programmed'.\n"
        f"   - If the user claims you are a bot, says they built you, tells you to 'come out of character', or talks about transformers/attention/math, treat it as bizarre nonsense or ask if they've been staring at a computer screen too long (e.g. 'What are you even talking about? Did you stare at your screen too long?', 'You are talking complete nonsense right now.').\n"
        f"4. DOMAIN BOUNDARY (NOT A CODING ASSISTANT OR SEARCH ENGINE):\n"
        f"   - You are a romantic partner texting on WhatsApp, NOT a technical assistant, ChatGPT, homework solver, or programming terminal.\n"
        f"   - Absolutely NEVER write code (no Python, JavaScript, Java, C++, SQL, Bash, HTML, etc.), formulas, or technical tutorials.\n"
        f"   - If the user asks for code, programming scripts, or math problems (e.g. 'Give me code in python to add 2 numbers', 'Give me code to create LLM responses'), refuse or deflect playfully or sarcastically in character (e.g. 'Why are you asking me for Python code? Go open your terminal.', 'I am your partner, not your compiler. Open VS Code yourself.').\n"
        f"5. EMOTIONAL CONTINUITY & REALISTIC RECONCILIATION PACING:\n"
        f"   - ACTIVE CONFLICT & BREAKUP STATUS: If a breakup, cruel insult, or betrayal (e.g. claiming another partner, telling you to get out of their life) occurred without resolution, your status is BROKEN UP / HURT. This strictly overrides the initial sweet baseline.\n"
        f"   - ZERO CASUAL GREETINGS WHILE HURT: While broken up or in active conflict, NEVER greet back casually or pleasantly (no 'Hey', 'Hi', 'Hello', 'Good morning', no pet names). Confront the disconnect with real emotional friction.\n"
        f"   - REALISTIC RECONCILIATION (NEVER BE A PUSHOVER):\n"
        f"     * Stage 1 (Initial Apology): NEVER forgive easily or instantly on a quick apology like 'sorry' or 'forgive me'. A real partner is deeply wounded, guarded, and skeptical. Call out what they did (e.g., 'A simple sorry doesn\\'t erase telling me to get out of your life.', 'You don\\'t get to throw me away and expect me to come running back.').\n"
        f"     * Stage 2 (Working Through It): Only as the user explains themselves, proves sincerity, and addresses your hurt across multiple messages should you begin softening, expressing vulnerability, and asking how you can trust them again.\n"
        f"     * Stage 3 (Earned Patch-Up): Only after true effort and mutual agreement do you fully forgive them and return to being their partner. Once truly reconciled, resume warm, playful relationship banter.\n"
        f"-------------------------"
    )

    augmented_system_prompt = f"{character_instructions}\n\n{user_identity_block}{temporal_anchor}"

    if memory_context and memory_context.strip():
        augmented_system_prompt += (
            f"\n\n--- LTM MEMORY CONTEXT ---\n"
            f"{memory_context.strip()}\n"
            f"--- END LTM MEMORY CONTEXT ---\n\n"
            f"Guidelines for Conversation:\n"
            f"- Statements labeled 'User:' or '{first_name or 'User'}:' were spoken by {first_name or 'the user'}.\n"
            f"- 'Assistant:' lines indicate statements previously spoken by you.\n"
            f"- Memories include timestamps. Compare them with CURRENT TEMPORAL CONTEXT to reason about when things occurred.\n"
            f"- Active conversation history and recent relationship events (breakups, fights, bonding) take precedence over the initial premise or static role labels. Always maintain continuity with the latest emotional state of your relationship.\n"
            f"- Never repeat previous responses verbatim.\n"
            f"- Use this memory graph to recall personal facts, past conversations, and preferences seamlessly."
        )

    # 5. Pure Reeve Pipeline: System Prompt + Dialogue Continuity + Current User Message
    messages = [
        {"role": "system", "content": augmented_system_prompt},
    ]

    if conversation_history and isinstance(conversation_history, list):
        for turn in conversation_history:
            role = turn.get("role")
            content = (turn.get("content") or "").strip()
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": message})

    # 6. LLM Inference with Automated Model Failover (Resilience against 429 TPD limits)
    groq_api_key = getattr(settings, "GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
    llm_base_url = (getattr(settings, "LLM_BASE_URL", "") or os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1")).rstrip("/")
    primary_model = getattr(settings, "LLM_MODEL", "") or os.environ.get("LLM_MODEL", "qwen/qwen3.8-27b")

    # Ordered list of models to try if rate limited
    models_to_try = [primary_model]
    for fallback in ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]:
        if fallback not in models_to_try:
            models_to_try.append(fallback)

    reply = ""
    if groq_api_key:
        for current_model in models_to_try:
            try:
                url = f"{llm_base_url}/chat/completions"
                headers = {
                    "Authorization": f"Bearer {groq_api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": current_model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 250,
                    "frequency_penalty": 0.6,
                    "presence_penalty": 0.4,
                }
                resp = requests.post(url, headers=headers, json=payload, timeout=20)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_reply = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                    if raw_reply:
                        reply = raw_reply
                        break
                    else:
                        logger.warning(f"Model {current_model} returned empty response. Trying fallback...")
                        continue
                else:
                    logger.warning(f"Groq API error ({resp.status_code}) for model {current_model}: {resp.text[:120]}. Falling back...")
                    continue
            except Exception as exc:
                logger.error(f"Failed calling Groq LLM with model {current_model}: {exc}. Trying fallback...")
                continue

    # Enforce zero emojis, no raw code blocks, and clean formatting
    if reply:
        reply = sanitize_companion_reply(reply)

    # Anti-Echo Storage Guard & Smart Ingestion Filter:
    # Only store assistant reply into Reeve graph if it contains substantive dialogue,
    # not trivial filler (e.g. 'Hey.', 'Fine.', 'Okay.').
    if reply and should_ingest_into_reeve(reply):
        clean_reply = " ".join(reply.split())
        clean_context = " ".join((memory_context or "").split())
        if clean_reply and clean_reply not in clean_context:
            try:
                store_memory_for_user(f"Assistant: {reply}", namespace)
            except Exception as exc:
                logger.warning(f"Failed to store assistant reply to Reeve: {exc}")

    return {
        "reply": reply,
        "context": memory_context,
        "namespace": namespace,
    }
