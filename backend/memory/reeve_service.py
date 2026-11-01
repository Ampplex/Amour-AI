"""
Reeve Long-Term Memory (LTM) Integration Service.

========================================================================================
ZERO-KNOWLEDGE CLIENT-MANAGED ENCRYPTION ARCHITECTURE (REEVE SDK >= 0.1.42)
========================================================================================
This backend integrates with Reeve 0.1.42, which supports Option 2 (Client-Managed
Zero-Knowledge Encryption) for end-to-end memory confidentiality:

1. CLIENT-MANAGED KEY GENERATION & STORAGE:
   - The user's device generates a cryptographically secure 256-bit AES key.
   - Stored in hardware-backed secure storage (iOS Keychain / Android Keystore via expo-secure-store).
   - Transmitted per-request in the 'X-Memory-User-Key' header or request payload.
   - The server only holds the key transiently in volatile RAM for the duration of the request.
   - The server NEVER persists the plaintext key to disk or database logs.

2. ENCRYPTION AT REST (NEO4J & BACKUPS):
   - Reeve encrypts sensitive payload fields before writing to Neo4j:
     * Episode raw_text: AES-256-GCM with a unique 12-byte nonce (enc:v2:<nonce+ciphertext>)
     * Episode summary & searchable_text: AES-256-GCM
     * State property values: AES-256-GCM
   - Neo4j database files and automated backups hold ONLY AES-GCM ciphertext.

3. ACCURACY & QUALITY PRESERVATION:
   - High-dimensional semantic embeddings (1024-dim Bedrock Titan) are generated in volatile
     RAM from the plaintext before storage.
   - Knowledge graph structure (entities, relationship edges, and state attribute names)
     remains unencrypted for Cypher graph traversals and semantic similarity scoring.
   - Retrieval quality, context ranking, and emotional continuity are 100% byte-identical
     to unencrypted operation.

4. DUAL-MODE & PREFIX GUARD (ZERO MIGRATION NEEDED):
   - Historical memories created prior to v0.1.42 remain plaintext in Neo4j.
   - The Prefix Guard inspects all retrieved records:
     * Strings starting with 'enc:v2:' are authenticated and decrypted with user_key.
     * Legacy strings without the prefix pass through untouched without errors.
   - If user_key is omitted or None, Reeve runs in unencrypted mode seamlessly.
========================================================================================
"""

import os
import re
import time
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


def store_memory_for_user(text: str, namespace: str, user_key: str = None):
    """
    Store conversational memory into Reeve / Neo4j.
    The user's unique namespace (e.g. user_id_persona_id) is passed as speaker.
    Optionally encrypts content using client-managed AES-256-GCM user_key.
    """
    from reeve.tools import store_memory, reset_client_cache
    try:
        kwargs = {"speaker": namespace}
        if user_key:
            kwargs["user_key"] = user_key
        return store_memory(text, **kwargs)
    except Exception as exc:
        logger.warning(f"Reeve write failed, resetting client cache and retrying: {exc}")
        reset_client_cache()
        kwargs = {"speaker": namespace}
        if user_key:
            kwargs["user_key"] = user_key
        return store_memory(text, **kwargs)


def query_memory_for_user(question: str, namespace: str, user_key: str = None):
    """
    Query memories from Reeve / Neo4j graph for this specific user namespace.
    """
    from reeve.tools import query_memory, reset_client_cache
    try:
        kwargs = {"speaker": namespace}
        if user_key:
            kwargs["user_key"] = user_key
        return query_memory(question, **kwargs)
    except Exception as exc:
        logger.warning(f"Reeve query failed, retrying: {exc}")
        reset_client_cache()
        kwargs = {"speaker": namespace}
        if user_key:
            kwargs["user_key"] = user_key
        return query_memory(question, **kwargs)


def retrieve_context_for_user(question: str, namespace: str, user_key: str = None):
    """
    Retrieve ranked memory context from Neo4j graph for this user namespace.
    Optionally decrypts content using client-managed AES-256-GCM user_key.
    """
    from reeve.tools import retrieve_memory_context, reset_client_cache
    try:
        kwargs = {"speaker": namespace}
        if user_key:
            kwargs["user_key"] = user_key
        return retrieve_memory_context(question, **kwargs)
    except Exception as exc:
        logger.warning(f"Reeve context retrieve failed, retrying: {exc}")
        reset_client_cache()
        kwargs = {"speaker": namespace}
        if user_key:
            kwargs["user_key"] = user_key
        return retrieve_memory_context(question, **kwargs)


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
5. OUTPUT JSON FORMAT: You must output a single valid JSON object containing exactly two keys:
   {
     "reply": "<your short WhatsApp-style reply text, zero emojis>",
     "conflict_stage": <integer 0, 1, 2, or 3>
   }
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

    # 6. KV-Cache Optimized System Prompt Assembly
    # Prefix Order:
    # [1] GLOBAL_COMPANION_DIRECTIVES (100% invariant across all requests - cache hit anchor)
    # [2] PERSONA IDENTITY & STORY (100% invariant per persona)
    # [3] USER PROFILE (stable per user)
    # [4] TEMPORAL ANCHOR (bucketed to prevent 60-second invalidation)
    # [5] DYNAMIC REEVE MEMORIES (placed at the tail to prevent busting prefix cache)
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

    augmented_system_prompt = "\n\n".join(prompt_sections)

    # 7. Pure Reeve Pipeline: System Prompt + Dialogue Continuity + Current User Message
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

    # 8. LLM Inference with Automated Model Failover & KV Cache Tracking
    groq_api_key = getattr(settings, "GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
    llm_base_url = (getattr(settings, "LLM_BASE_URL", "") or os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1")).rstrip("/")
    primary_model = getattr(settings, "LLM_MODEL", "") or os.environ.get("LLM_MODEL", "qwen/qwen3.8-27b")

    models_to_try = [primary_model]
    for fallback in ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]:
        if fallback not in models_to_try:
            models_to_try.append(fallback)

    reply = ""
    new_conflict_stage = current_conflict_stage
    if groq_api_key:
        for current_model in models_to_try:
            try:
                url = f"{llm_base_url}/chat/completions"
                headers = {
                    "Authorization": f"Bearer {groq_api_key}",
                    "Content-Type": "application/json",
                }
                # Reasoning models (like gpt-oss-120b and 20b) generate internal reasoning tokens
                # before emitting JSON, requiring higher max_tokens to prevent JSON truncation
                token_budget = 650 if "gpt-oss" in current_model else 350
                payload = {
                    "model": current_model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": token_budget,
                    "frequency_penalty": 0.6,
                    "presence_penalty": 0.4,
                    "response_format": {"type": "json_object"},
                }
                t0 = time.time()
                resp = requests.post(url, headers=headers, json=payload, timeout=20)

                # Handle transient 429 rate limits (token bucket resets in ~1.5s on Groq)
                if resp.status_code == 429:
                    logger.info(f"Model {current_model} returned 429. Backing off 1.6s for token bucket reset...")
                    time.sleep(1.6)
                    resp = requests.post(url, headers=headers, json=payload, timeout=20)

                duration = time.time() - t0

                if resp.status_code == 200:
                    data = resp.json()
                    raw_content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                    usage = data.get("usage", {})
                    prompt_tokens = usage.get("prompt_tokens", 0)
                    completion_tokens = usage.get("completion_tokens", 0)
                    cached_tokens = (
                        usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
                        if isinstance(usage.get("prompt_tokens_details"), dict)
                        else 0
                    )
                    prompt_time = usage.get("prompt_time", 0)
                    completion_time = usage.get("completion_time", 0)

                    logger.info(
                        f"[KV Cache & Latency] Model: {current_model} | Duration: {duration:.2f}s "
                        f"| Prompt Tokens: {prompt_tokens} (Cached: {cached_tokens}) "
                        f"| Prompt Time: {prompt_time}s | Completion Tokens: {completion_tokens} ({completion_time}s)"
                    )

                    try:
                        import json
                        parsed = json.loads(raw_content)
                        raw_reply = parsed.get("reply", "")
                        if "conflict_stage" in parsed:
                            try:
                                new_conflict_stage = int(parsed["conflict_stage"])
                            except (ValueError, TypeError):
                                new_conflict_stage = current_conflict_stage
                    except Exception:
                        raw_reply = raw_content

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
                store_memory_for_user(f"Assistant: {reply}", namespace, user_key=user_key)
            except Exception as exc:
                logger.warning(f"Failed to store assistant reply to Reeve: {exc}")

    return {
        "reply": reply,
        "conflict_stage": new_conflict_stage,
        "context": memory_context,
        "namespace": namespace,
    }
