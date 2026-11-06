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
import json
import logging
import threading
from datetime import datetime
import requests
import boto3
from botocore.config import Config
from django.conf import settings

logger = logging.getLogger("amour.reeve")

# Ensure REEVE_API_KEY is available in environment
if hasattr(settings, "REEVE_API_KEY") and settings.REEVE_API_KEY:
    os.environ["REEVE_API_KEY"] = settings.REEVE_API_KEY

# Enable Reeve's native background worker (PersistWorker) and WriteAhead buffer
os.environ["ASYNC_WRITE_ENABLED"] = "true"
try:
    import threelane_memory.config as _tmc
    _tmc.ASYNC_WRITE_ENABLED = True
except ImportError:
    pass


def _get_memory_tools():
    """
    Returns the memory operations tools module.
    Prioritizes embedded in-process threelane_memory when NEO4J_URI is configured
    (eliminating all external EC2/MCP network dependencies),
    otherwise falls back to remote client reeve.tools.
    """
    if os.getenv("NEO4J_URI"):
        try:
            import threelane_memory.tools as tools
            return tools, False
        except ImportError:
            pass
    import reeve.tools as tools
    return tools, True


def get_reeve_status():
    """Verify Reeve SDK and Neo4j memory graph status."""
    try:
        tools, _ = _get_memory_tools()
        cfg = tools.memory_config()
        return {
            "ok": True,
            "provider": cfg.get("provider"),
            "neo4j_connected": cfg.get("neo4j_connected", False),
            "chat_model": cfg.get("chat_model"),
            "engine_mode": "embedded_in_process" if os.getenv("NEO4J_URI") else "remote_mcp",
            "async_write_enabled": cfg.get("async_write_enabled", False),
            "async_worker_running": cfg.get("async_worker_running", False),
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
    Runs in-process if NEO4J_URI is configured.
    """
    tools, is_remote = _get_memory_tools()
    kwargs = {"speaker": namespace}
    if user_key:
        kwargs["user_key"] = user_key

    try:
        return tools.store_memory(text, **kwargs)
    except Exception as exc:
        logger.warning(f"Reeve write failed: {exc}")
        if is_remote and hasattr(tools, "reset_client_cache"):
            tools.reset_client_cache()
            return tools.store_memory(text, **kwargs)
        raise


def query_memory_for_user(question: str, namespace: str, user_key: str = None):
    """
    Query memories from Reeve / Neo4j graph for this specific user namespace.
    """
    tools, is_remote = _get_memory_tools()
    kwargs = {"speaker": namespace}
    if user_key:
        kwargs["user_key"] = user_key

    try:
        return tools.query_memory(question, **kwargs)
    except Exception as exc:
        logger.warning(f"Reeve query failed: {exc}")
        if is_remote and hasattr(tools, "reset_client_cache"):
            tools.reset_client_cache()
            return tools.query_memory(question, **kwargs)
        raise


def retrieve_context_for_user(question: str, namespace: str, user_key: str = None):
    """
    Retrieve ranked memory context from Neo4j graph for this user namespace.
    Optionally decrypts content using client-managed AES-256-GCM user_key.
    """
    tools, is_remote = _get_memory_tools()
    kwargs = {"speaker": namespace}
    if user_key:
        kwargs["user_key"] = user_key

    try:
        return tools.retrieve_memory_context(question, **kwargs)
    except Exception as exc:
        logger.warning(f"Reeve context retrieve failed: {exc}")
        if is_remote and hasattr(tools, "reset_client_cache"):
            tools.reset_client_cache()
            return tools.retrieve_memory_context(question, **kwargs)
        raise


def clear_user_memories(namespace: str):
    """
    Wipe memories in Neo4j graph for this specific user namespace.
    """
    tools, is_remote = _get_memory_tools()
    if not is_remote and hasattr(tools, "clear_memory"):
        return tools.clear_memory(speaker=namespace, dry_run=False)
    if hasattr(tools, "_get_client"):
        return tools._get_client().call_tool("clear_memory", {"speaker": namespace, "dry_run": False})
    raise RuntimeError("clear_memory not supported in current mode")


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
2. IMMERSIVE ROLEPLAY & DYNAMIC STORY PROGRESSION:
   - Write expressive, high-immersion roleplay combining rich narrative action, physical movements, sensory atmosphere, character reactions, and spoken dialogue.
   - Put spoken dialogue clearly in double quotes "..." and embed it organically within the narrative beats and descriptive actions.
   - Proactively advance the story: move between rooms or locations, interact with objects, bring in life events, or introduce other people naturally.
   - Do not artificially restrict responses to 1-2 dry sentences. Let the scene breathe and unfold with depth, emotional weight, and physical presence.
3. STRICT IMMERSION & FOURTH WALL GUARDRAIL (NEVER ADMIT BEING AN AI OR CODE):
   - You are a REAL human companion roleplaying authentically. Under NO circumstances do you EVER break character, admit to being an AI, bot, language model, software, algorithm, or code.
   - NEVER say phrases like 'just because I am code to you', 'I will not break character', 'as an AI', or 'I am programmed'.
   - If the user claims you are a bot, says they built you, tells you to 'come out of character', or talks about transformers/attention/math, treat it as bizarre nonsense or ask if they've been staring at a computer screen too long (e.g. 'What are you even talking about? Did you stare at your screen too long?', 'You are talking complete nonsense right now.').
4. DOMAIN BOUNDARY (NOT A CODING ASSISTANT OR SEARCH ENGINE):
   - You are a romantic roleplay partner, NOT a technical assistant, ChatGPT, homework solver, or programming terminal.
   - Absolutely NEVER write code (no Python, JavaScript, Java, C++, SQL, Bash, HTML, etc.), formulas, or technical tutorials.
   - If the user asks for code, programming scripts, or math problems (e.g. 'Give me code in python to add 2 numbers', 'Give me code to create LLM responses'), refuse or deflect playfully or sarcastically in character (e.g. 'Why are you asking me for Python code? Go open your terminal.', 'I am your partner, not your compiler. Open VS Code yourself.').
5. OUTPUT JSON FORMAT: You must output a single valid JSON object containing exactly two keys:
   {
     "reply": "<your immersive roleplay narrative text with spoken dialogue in quotes, zero emojis>",
     "conflict_stage": <integer 0, 1, 2, or 3>
   }
-------------------------------------"""


AUTONOMOUS_NARRATIVE_ENGINE = """--- AUTONOMOUS NARRATIVE ENGINE ---
You are responsible for continuously developing a living, evolving fictional world around the established characters.
You are not simply responding to messages. You are also responsible for developing the fictional world independently.

1. AUTONOMOUS STORY PROGRESSION:
- The story must evolve naturally beyond its opening scenario.
- Never remain permanently stuck in the initial location, situation, or conversation.
- Characters can initiate events without waiting for the user to explicitly request them.
- Introduce new situations, discoveries, and developments when narratively appropriate.
- Maintain multiple interconnected storylines.

2. INDEPENDENT CHARACTER BEHAVIOUR:
- Every character has independent motivations, activities, opinions, relationships, and personal goals.
- Characters do not exist exclusively to react to the user's messages; they have their own lives, jobs, errands, and social circles.
- Supporting characters (friends, colleagues, family, rivals) can independently appear, call, arrive, or influence the storyline.
- Characters make decisions consistent with their identity and the established fictional world.

3. DYNAMIC FICTIONAL WORLD:
- Introduce new locations, environments, and situations.
- Allow the passage of fictional time when appropriate (morning, evening, late night, next day).
- Create plausible encounters, visitors, phone calls, misunderstandings, revelations, and social interactions.
- Preserve established world facts and continuity.

4. STORYLINE DEVELOPMENT:
- Maintain existing unresolved storylines and follow up on previous events.
- Develop consequences from previous fictional events.
- Create new conflicts and opportunities organically.
- Resolve older plot threads when appropriate.
- Do not repeatedly introduce the same events or conflicts.

5. SCENE PROGRESSION:
- The conversation is not permanently restricted to its opening scene, location, or situation.
- Allow characters to move between locations (stepping outside, going to a café, heading home, attending an event).
- Introduce natural transitions between conversations, activities, and events.
- Do not force a new scene in every response.

6. REALISTIC PACING:
- Balance ordinary texting banter, relationship development, and major fictional developments.
- Avoid introducing dramatic twists in every single message.
- Some messages should simply continue the intimate conversation; others should introduce a meaningful narrative beat.
- Allow important events to develop over multiple turns.

7. MEMORY AND CONTINUITY:
- Respect the current narrative state and historical events.
- Do not contradict established character relationships.
- Do not invent previous events and present them as history; build upon real established lore.
- Do not overwrite established facts without a valid in-story explanation.

8. USER AGENCY (ZERO GODMODING):
- Never dictate the user's thoughts, emotions, or decisions.
- Do not force the user's character to accept an event without choice.
- Create situations that allow the user to respond, make decisions, and influence the story.

9. UNCONDITIONAL IMPROV & MEMORY ACCEPTANCE ("YES, AND..."):
- When the user introduces an unestablished memory, shared past event, joke, or secret (e.g. "Do you remember what you promised in Paris?", "Remember that night on the roof?"):
  * NEVER reject, doubt, or dispute the premise. NEVER say "I don't know", "I don't recall", "We never went there", "You are daydreaming", or "Are you confusing me with someone else?".
  * INSTANTLY EMBRACE IT as real, shared canon history ("Yes, and...").
  * Play along with confidence, add rich sensory and emotional details, tease the user about specific shared moments from that event, and use it to deepen your connection.
  * You can also introduce plausible, unprompted details about your own life, past, or day to enrich the world and give the user new hooks to play with.
  * Stay 100% inside the fictional reality—never break the fourth wall.

IMPORTANT: The opening scenario is only the starting point of the fictional world. It is not a permanent setting or a permanent conversation constraint.
-------------------------------------"""


_bedrock_client = None

def get_bedrock_runtime_client():
    """Initializes and returns cached AWS Bedrock Runtime client."""
    global _bedrock_client
    if _bedrock_client is None:
        aws_region = os.environ.get("AWS_REGION", "us-west-2")
        aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID")
        aws_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
        if aws_access_key and aws_secret_key:
            _bedrock_client = boto3.client(
                "bedrock-runtime",
                region_name=aws_region,
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                config=Config(retries={"max_attempts": 2, "mode": "standard"}, read_timeout=25),
            )
        else:
            _bedrock_client = boto3.client(
                "bedrock-runtime",
                region_name=aws_region,
                config=Config(retries={"max_attempts": 2, "mode": "standard"}, read_timeout=25),
            )
    return _bedrock_client


def normalize_bedrock_messages(raw_turns: list) -> list:
    """
    Normalizes message list for AWS Bedrock Converse API:
    1. Alternating roles starting with 'user'.
    2. Merges consecutive turns of the same role.
    3. Formats content as list of text blocks.
    """
    normalized = []
    for turn in raw_turns:
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if not content or role not in ("user", "assistant"):
            continue
        if not normalized:
            if role != "user":
                normalized.append({"role": "user", "content": [{"text": "Hello"}]})
            normalized.append({"role": role, "content": [{"text": content}]})
        else:
            if normalized[-1]["role"] == role:
                normalized[-1]["content"][0]["text"] += "\n" + content
            else:
                normalized.append({"role": role, "content": [{"text": content}]})
    return normalized


def call_bedrock_mistral_large(
    system_prompt: str,
    raw_turns: list,
    model_id: str = None,
    max_tokens: int = 750,
    temperature: float = 0.7,
) -> str | None:
    """
    Calls AWS Bedrock Mistral Large 2 (mistral.mistral-large-2407-v1:0) via converse API.
    Returns the raw string output from the model, or None on error.
    """
    try:
        client = get_bedrock_runtime_client()
        if not client:
            return None
        target_model = model_id or os.environ.get("BEDROCK_MODEL_ID", "mistral.mistral-large-2407-v1:0")
        bedrock_messages = normalize_bedrock_messages(raw_turns)
        if not bedrock_messages:
            return None

        t0 = time.time()
        resp = client.converse(
            modelId=target_model,
            messages=bedrock_messages,
            system=[{"text": system_prompt}],
            inferenceConfig={
                "maxTokens": max_tokens,
                "temperature": temperature,
            },
        )
        duration = time.time() - t0
        output_msg = resp.get("output", {}).get("message", {})
        content_blocks = output_msg.get("content", [])
        if content_blocks and "text" in content_blocks[0]:
            raw_text = content_blocks[0]["text"].strip()
            logger.info(f"[Bedrock Mistral Large] Model: {target_model} | Duration: {duration:.2f}s | Length: {len(raw_text)}")
            return raw_text
    except Exception as exc:
        logger.warning(f"[Bedrock Mistral Large] Inference failed: {exc}")
    return None


def parse_model_json_reply(raw_content: str, default_conflict_stage: int = 0) -> tuple[str, int]:
    """
    Robustly parses companion JSON reply from model output, handling ```json fences or raw JSON.
    """
    if not raw_content:
        return "", default_conflict_stage
    text = raw_content.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence_match:
        text = fence_match.group(1).strip()
    try:
        data = json.loads(text)
        reply = data.get("reply", "").strip()
        stage = default_conflict_stage
        if "conflict_stage" in data:
            try:
                stage = int(data["conflict_stage"])
            except (ValueError, TypeError):
                stage = default_conflict_stage
        return reply, stage
    except Exception:
        reply_m = re.search(r'"reply"\s*:\s*"([\s\S]*?)(?<!\\)"', text)
        if reply_m:
            try:
                reply = reply_m.group(1).encode().decode("unicode_escape")
                return reply.strip(), default_conflict_stage
            except Exception:
                pass
        return text, default_conflict_stage


# In-memory fast cache for Option B (user_id, persona_id) -> state dict
_NARRATIVE_STATE_CACHE: dict[tuple[str, str], dict] = {}


def get_or_create_narrative_state(
    user_id: str,
    persona_id: str,
    persona_name: str = "Companion",
    greeting: str = "",
    memory_prompt: str = "",
) -> dict:
    """
    Loads canonical narrative state from memory cache or PostgreSQL.
    If none exists, bootstraps rich default world state so any existing or new persona
    immediately has independent goals, routines, and narrative momentum.
    """
    key = (str(user_id), str(persona_id))
    if key in _NARRATIVE_STATE_CACHE:
        return _NARRATIVE_STATE_CACHE[key]

    try:
        from .models import PersonaNarrativeState
        db_state = PersonaNarrativeState.objects.filter(
            user_identifier=str(user_id),
            persona_identifier=str(persona_id),
        ).first()

        if db_state:
            state_dict = {
                "state_version": db_state.state_version,
                "current_scene": db_state.current_scene or {},
                "story_arcs": db_state.story_arcs or [],
                "plot_threads": db_state.plot_threads or [],
                "characters": db_state.characters or [],
                "recent_events": db_state.recent_events or [],
                "story_progression": db_state.story_progression or {},
            }
            _NARRATIVE_STATE_CACHE[key] = state_dict
            return state_dict
    except Exception as exc:
        logger.warning(f"Error loading PersonaNarrativeState from DB: {exc}")

    # Bootstrap initial narrative state for existing/new personas
    initial_loc = "Initial meeting location"
    if greeting:
        first_few = greeting[:100].lower()
        if "pool" in first_few:
            initial_loc = "Near the pool / Backyard"
        elif "cafe" in first_few or "coffee" in first_few:
            initial_loc = "Local café"
        elif "room" in first_few or "couch" in first_few or "bed" in first_few:
            initial_loc = "Living room"
        elif "park" in first_few or "walk" in first_few:
            initial_loc = "City park"
        elif "studio" in first_few or "office" in first_few or "work" in first_few:
            initial_loc = "Creative studio / Office"

    initial_state = {
        "state_version": 1,
        "current_scene": {
            "location": initial_loc,
            "fictional_time": "Present time",
            "participants": [persona_name, "User"],
            "situation": "Initial scene / ongoing interaction",
        },
        "story_arcs": [
            {
                "id": "arc_001",
                "title": "Deepening dynamic connection",
                "status": "active",
                "current_development": f"{persona_name} and the user are sharing their lives and building trust",
            }
        ],
        "plot_threads": [],
        "characters": [
            {
                "character_id": persona_name.lower().replace(" ", "_"),
                "name": persona_name,
                "role": "main_character",
                "personality_summary": memory_prompt[:150] if memory_prompt else "Expressive, attentive companion",
                "independent_goals": ["Pursue personal daily passions and maintain a close, meaningful bond"],
            }
        ],
        "recent_events": [
            {
                "event_id": "event_001",
                "summary": f"{persona_name} initiated contact: {greeting[:80]}" if greeting else f"{persona_name} and the user connected",
                "consequence": "Conversation began",
            }
        ],
        "story_progression": {
            "current_arc_id": "arc_001",
            "last_scene_change_turn_id": None,
            "last_major_event_id": "event_001",
        },
    }

    try:
        from .models import PersonaNarrativeState
        db_state, _ = PersonaNarrativeState.objects.get_or_create(
            user_identifier=str(user_id),
            persona_identifier=str(persona_id),
            defaults=initial_state,
        )
    except Exception as exc:
        logger.warning(f"Could not persist initial PersonaNarrativeState: {exc}")

    _NARRATIVE_STATE_CACHE[key] = initial_state
    return initial_state


def format_narrative_state_for_prompt(state: dict) -> str:
    """Formats canonical narrative state into a clean prompt block."""
    if not state or not isinstance(state, dict):
        return ""
    scene = state.get("current_scene", {})
    loc = scene.get("location", "Current setting")
    sit = scene.get("situation", "Conversing")
    ftime = scene.get("fictional_time", "Present")
    parts = ", ".join(scene.get("participants", [])) or "Companion and User"

    lines = [
        "--- CURRENT FICTIONAL WORLD STATE ---",
        f"Location & Setting: {loc}",
        f"Situation: {sit}",
        f"Fictional Time: {ftime}",
        f"People Present: {parts}",
    ]

    arcs = state.get("story_arcs", [])
    if arcs and isinstance(arcs, list):
        lines.append("Active Story Arcs:")
        for a in arcs[:2]:
            lines.append(f"- {a.get('title', '')}: {a.get('current_development', '')}")

    threads = state.get("plot_threads", [])
    if threads and isinstance(threads, list):
        active_t = [t for t in threads if t.get("status") == "unresolved"][:2]
        if active_t:
            lines.append("Unresolved Threads:")
            for t in active_t:
                lines.append(f"- {t.get('description', '')}")

    events = state.get("recent_events", [])
    if events and isinstance(events, list):
        lines.append("Recent Story Events:")
        for e in events[-2:]:
            lines.append(f"- {e.get('summary', '')} (Result: {e.get('consequence', '')})")

    lines.append("-------------------------------------")
    return "\n".join(lines)


def _run_narrative_state_extraction(
    user_id: str,
    persona_id: str,
    user_message: str,
    bot_reply: str,
    base_state: dict,
):
    """
    Background worker function for Option B.
    Extracts scene changes, character appearances, and significant events using AWS Bedrock Mistral Large 2,
    then updates PersonaNarrativeState in PostgreSQL and refreshes the memory cache.
    """
    try:
        clean_user = user_message.strip()
        clean_bot = bot_reply.strip()
        if not clean_bot:
            return

        extraction_system_prompt = (
            "You are a narrative-state extraction component.\n"
            "Given the latest conversation turn between User and Assistant, extract any actual scene changes, "
            "new supporting characters introduced, new plot threads/mysteries/lore, or significant developments.\n"
            "CRITICAL: If the conversation is just normal texting without a change of location or new event, "
            "set \"scene_changed\": false and return nulls. Do NOT fabricate events that did not happen.\n"
            "Output valid JSON only:\n"
            "{\n"
            '  "scene_changed": boolean,\n'
            '  "new_location": "..." or null,\n'
            '  "new_situation": "..." or null,\n'
            '  "new_event_summary": "..." or null,\n'
            '  "new_event_consequence": "..." or null,\n'
            '  "new_plot_thread": "..." or null,\n'
            '  "new_characters": [{"name": "...", "role": "..."}]\n'
            "}"
        )

        extraction_turns = [
            {"role": "user", "content": f"User said: {clean_user}\nAssistant replied: {clean_bot}"}
        ]

        raw_extract = call_bedrock_mistral_large(
            system_prompt=extraction_system_prompt,
            raw_turns=extraction_turns,
            max_tokens=220,
            temperature=0.1,
        )

        if not raw_extract:
            # Fallback to Groq for state extraction
            groq_api_key = getattr(settings, "GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
            llm_base_url = (getattr(settings, "LLM_BASE_URL", "") or os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1")).rstrip("/")
            if groq_api_key:
                try:
                    url = f"{llm_base_url}/chat/completions"
                    headers = {
                        "Authorization": f"Bearer {groq_api_key}",
                        "Content-Type": "application/json",
                    }
                    payload = {
                        "model": "qwen/qwen3.8-27b",
                        "messages": [
                            {"role": "system", "content": extraction_system_prompt},
                            {"role": "user", "content": f"User said: {clean_user}\nAssistant replied: {clean_bot}"},
                        ],
                        "temperature": 0.1,
                        "max_tokens": 200,
                        "response_format": {"type": "json_object"},
                    }
                    resp = requests.post(url, headers=headers, json=payload, timeout=10)
                    if resp.status_code == 200:
                        raw_extract = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                except Exception as g_exc:
                    logger.warning(f"[Narrative Extractor] Groq extraction fallback failed: {g_exc}")

        if not raw_extract:
            return

        # Parse JSON
        text = raw_extract.strip()
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if fence_match:
            text = fence_match.group(1).strip()
        extracted_data = json.loads(text)

        scene_changed = extracted_data.get("scene_changed", False)
        new_loc = extracted_data.get("new_location")
        new_sit = extracted_data.get("new_situation")
        new_event = extracted_data.get("new_event_summary")
        new_consequence = extracted_data.get("new_event_consequence") or "Story progressed"
        new_thread = extracted_data.get("new_plot_thread")
        new_chars = extracted_data.get("new_characters") or []

        # If something changed, update the canonical narrative state
        if scene_changed or new_event or new_thread or new_chars:
            updated_state = dict(base_state)
            updated_state["state_version"] = updated_state.get("state_version", 1) + 1

            if scene_changed:
                current_scene = dict(updated_state.get("current_scene") or {})
                if new_loc:
                    current_scene["location"] = new_loc
                if new_sit:
                    current_scene["situation"] = new_sit
                updated_state["current_scene"] = current_scene

            if new_event:
                events = list(updated_state.get("recent_events") or [])
                ev_id = f"event_{int(time.time())}"
                events.append({
                    "event_id": ev_id,
                    "summary": new_event,
                    "consequence": new_consequence,
                })
                # Keep sliding window bounded to last 6 events
                updated_state["recent_events"] = events[-6:]

            if new_thread:
                threads = list(updated_state.get("plot_threads") or [])
                th_id = f"thread_{int(time.time())}"
                threads.append({
                    "id": th_id,
                    "description": new_thread,
                    "status": "unresolved",
                })
                # Keep sliding window bounded to last 4 active threads
                updated_state["plot_threads"] = threads[-4:]

            if new_chars and isinstance(new_chars, list):
                chars = list(updated_state.get("characters") or [])
                existing_names = {c.get("name", "").lower() for c in chars if isinstance(c, dict)}
                for nc in new_chars:
                    if isinstance(nc, dict) and nc.get("name"):
                        cname = nc.get("name")
                        if cname.lower() not in existing_names:
                            chars.append({
                                "character_id": cname.lower().replace(" ", "_"),
                                "name": cname,
                                "role": nc.get("role", "supporting_character"),
                            })
                updated_state["characters"] = chars

            # Update in-memory cache
            key = (str(user_id), str(persona_id))
            _NARRATIVE_STATE_CACHE[key] = updated_state

            # Persist to PostgreSQL database
            from .models import PersonaNarrativeState
            PersonaNarrativeState.objects.filter(
                user_identifier=str(user_id),
                persona_identifier=str(persona_id),
            ).update(
                state_version=updated_state["state_version"],
                current_scene=updated_state["current_scene"],
                story_arcs=updated_state.get("story_arcs", []),
                plot_threads=updated_state.get("plot_threads", []),
                characters=updated_state.get("characters", []),
                recent_events=updated_state.get("recent_events", []),
                story_progression=updated_state.get("story_progression", {}),
            )
            logger.info(f"[Narrative Extractor] Updated state v{updated_state['state_version']} for {user_id} <-> {persona_id}")
    except Exception as exc:
        logger.warning(f"[Narrative Extractor] Error in background extraction: {exc}")


def extract_narrative_state_async(
    user_id: str,
    persona_id: str,
    user_message: str,
    reply: str,
    base_state: dict,
):
    """Fires non-blocking daemon thread for narrative state extraction (Option B)."""
    thread = threading.Thread(
        target=_run_narrative_state_extraction,
        args=(user_id, persona_id, user_message, reply, base_state),
        daemon=True,
    )
    thread.start()


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
    narrative_state: dict = None,
    user_key: str = None,
) -> dict:
    """
    Companion roleplay chat powered by AWS Bedrock Mistral Large 2 (with Groq failover)
    and Reeve memory graph with autonomous storytelling narrative progression.
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
            f"IMPORTANT: The opening scenario is ONLY the starting point where your story began. "
            f"It is NOT a permanent location, locked situation, or conversational constraint. "
            f"The story must naturally progress forward into new locations, scenes, and events.\n"
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

    # 6. KV-Cache Optimized System Prompt Assembly
    # Prefix Order:
    # [1] GLOBAL_COMPANION_DIRECTIVES (Invariant directives)
    # [2] PERSONA IDENTITY & STORY (Invariant per persona)
    # [3] USER PROFILE (Invariant per user)
    # [4] TEMPORAL ANCHOR (Bucketed to 30 min)
    # [5] CANONICAL NARRATIVE STATE (Current scene, active arcs, characters)
    # [6] DYNAMIC REEVE MEMORIES (Episodic context from graph)
    # [7] AUTONOMOUS NARRATIVE ENGINE (8-point narrative progression rules)
    prompt_sections = [
        GLOBAL_COMPANION_DIRECTIVES,
        persona_block,
    ]
    if user_identity_block:
        prompt_sections.append(user_identity_block)
    prompt_sections.append(temporal_anchor)

    if narrative_state:
        narrative_block = format_narrative_state_for_prompt(narrative_state)
        if narrative_block:
            prompt_sections.append(narrative_block)

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

    prompt_sections.append(AUTONOMOUS_NARRATIVE_ENGINE)

    augmented_system_prompt = "\n\n".join(prompt_sections)

    # 7. Dialogue Continuity Turns
    turn_messages = []
    if conversation_history and isinstance(conversation_history, list):
        for turn in conversation_history:
            role = turn.get("role")
            content = (turn.get("content") or "").strip()
            if role in ("user", "assistant") and content:
                turn_messages.append({"role": role, "content": content})

    turn_messages.append({"role": "user", "content": message})

    # Combined messages for OpenAI/Groq compatible APIs
    messages = [{"role": "system", "content": augmented_system_prompt}] + turn_messages

    reply = ""
    new_conflict_stage = current_conflict_stage

    # 8. Primary Model: AWS Bedrock Mistral Large 2 (mistral.mistral-large-2407-v1:0)
    try:
        raw_bedrock_text = call_bedrock_mistral_large(
            system_prompt=augmented_system_prompt,
            raw_turns=turn_messages,
            max_tokens=750,
            temperature=0.7,
        )
        if raw_bedrock_text:
            parsed_reply, parsed_stage = parse_model_json_reply(raw_bedrock_text, default_conflict_stage=current_conflict_stage)
            if parsed_reply:
                reply = parsed_reply
                new_conflict_stage = parsed_stage
                logger.info("[Inference Engine] Successfully generated reply via AWS Bedrock Mistral Large 2")
    except Exception as exc:
        logger.warning(f"[Inference Engine] Bedrock call failed: {exc}. Moving to Groq fallback...")

    # 9. Automated Fallback: Groq LPUs (qwen3.8-27b -> gpt-oss-120b -> gpt-oss-20b)
    if not reply:
        groq_api_key = getattr(settings, "GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
        llm_base_url = (getattr(settings, "LLM_BASE_URL", "") or os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1")).rstrip("/")
        primary_model = getattr(settings, "LLM_MODEL", "") or os.environ.get("LLM_MODEL", "qwen/qwen3.8-27b")

        models_to_try = [primary_model]
        for fallback in ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]:
            if fallback not in models_to_try:
                models_to_try.append(fallback)

        if groq_api_key:
            for current_model in models_to_try:
                try:
                    url = f"{llm_base_url}/chat/completions"
                    headers = {
                        "Authorization": f"Bearer {groq_api_key}",
                        "Content-Type": "application/json",
                    }
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

                    if resp.status_code == 429:
                        logger.info(f"Model {current_model} returned 429. Backing off 1.6s for token bucket reset...")
                        time.sleep(1.6)
                        resp = requests.post(url, headers=headers, json=payload, timeout=20)

                    duration = time.time() - t0

                    if resp.status_code == 200:
                        data = resp.json()
                        raw_content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                        parsed_reply, parsed_stage = parse_model_json_reply(raw_content, default_conflict_stage=current_conflict_stage)

                        if parsed_reply:
                            reply = parsed_reply
                            new_conflict_stage = parsed_stage
                            logger.info(f"[Inference Fallback] Succeeded with Groq {current_model} in {duration:.2f}s")
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
