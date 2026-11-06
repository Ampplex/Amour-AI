"""
Reeve Long-Term Memory (LTM) Integration Service.

========================================================================================
ZERO-KNOWLEDGE CLIENT-MANAGED ENCRYPTION ARCHITECTURE (REEVE SDK >= 0.1.42)
========================================================================================
This module is strictly dedicated to Reeve LTM operations and Neo4j graph storage:
- Storing memories into Reeve / Neo4j with client-managed AES-256-GCM encryption
- Querying and retrieving ranked memory context
- Memory health checks and status reporting
- Memory wiping for account deletion compliance

For LLM inference, see `backend/memory/llm_client.py`.
For narrative state tracking, see `backend/memory/narrative_service.py`.
For chat pipeline orchestration, see `backend/memory/chat_service.py`.
========================================================================================
"""

import os
import re
import logging
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
    (eliminating external EC2/MCP network dependencies),
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
    if "```" in cleaned:
        cleaned = re.sub(r"```[\s\S]*?```", "", cleaned).strip()
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



def should_retrieve_from_reeve(text: str) -> bool:
    """
    Decide whether the current message benefits from long-term recall.

    This is intentionally separate from should_ingest_into_reeve(): a message
    worth remembering is not necessarily a query that needs historical context.
    """
    if not text or not text.strip():
        return False

    clean = re.sub(r"[^\w\s]", "", text.strip().lower())
    words = clean.split()
    if not words or clean in TRIVIAL_GREETINGS_AND_FILLERS:
        return False
    if len(words) <= 2 and all(word in TRIVIAL_GREETINGS_AND_FILLERS for word in words):
        return False

    recall_patterns = (
        r"\bremember\b",
        r"\brecall\b",
        r"\bwhat happened\b",
        r"\bwhat did .{1,80} (?:say|do|tell)\b",
        r"\bwho (?:is|was)\b",
        r"\btell me about\b",
        r"\blast time\b",
        r"\bprevious(?:ly)?\b",
        r"\bearlier\b",
        r"\bour (?:trip|visit|promise|plan|anniversary)\b",
        r"\byour (?:sister|brother|mother|father|friend)\b",
        r"\bmy (?:birthday|preference|favorite)\b",
        r"\bwhat was the name\b",
    )
    return any(re.search(pattern, clean) for pattern in recall_patterns)


def should_ingest_into_reeve(text: str) -> bool:
    """
    Cost & Performance Optimizer:
    Prevents calling expensive Bedrock Mistral Large graph extraction for trivial 1-2 word filler messages.
    PostgreSQL tracks short-term chat history. Reeve only ingests meaningful facts and lore.
    """
    if not text or not text.strip():
        return False
    # Recall prompts are retrieval queries, not new facts to persist.
    if should_retrieve_from_reeve(text):
        return False
    clean = re.sub(r"[^\w\s]", "", text.strip().lower())
    words = clean.split()
    if not words:
        return False
    if any(w in RELATIONSHIP_TRIGGER_WORDS for w in words):
        return True
    if clean in TRIVIAL_GREETINGS_AND_FILLERS:
        return False
    if len(words) <= 2 and all(w in TRIVIAL_GREETINGS_AND_FILLERS for w in words):
        return False
    if len(words) < 3:
        return False
    return True


# --------------------------------------------------------------------------------------
# Backward Compatibility Wrappers (Delegated to specialized domain services)
# --------------------------------------------------------------------------------------
def generate_companion_reply(*args, **kwargs):
    """Delegates to chat_service.generate_companion_reply."""
    from .chat_service import generate_companion_reply as _impl
    return _impl(*args, **kwargs)


from .narrative_service import (
    get_or_create_narrative_state,
    extract_narrative_state_async,
    format_narrative_state_for_prompt,
    GLOBAL_COMPANION_DIRECTIVES,
    AUTONOMOUS_NARRATIVE_ENGINE,
)
from .llm_client import (
    call_bedrock_mistral_large,
    call_groq_fallback,
    parse_model_json_reply,
    normalize_bedrock_messages,
)
