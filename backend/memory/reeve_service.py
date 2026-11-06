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
import threading
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

# --------------------------------------------------------------------------------------
# Jev-powered memory write gate
# --------------------------------------------------------------------------------------

# Jev evaluates typed decisions; application code applies the policy and performs writes.
# Reuse a pooled client per request thread rather than opening a new TLS connection each turn.
_JEV_THREAD_LOCAL = threading.local()

_STOREABLE_MEMORY_TYPES = {
    "profile_fact",
    "preference",
    "relationship",
    "goal_or_plan",
    "significant_event",
}


def _get_jev_client():
    """Reuse one pooled TypeSafe client per worker thread."""
    api_key = getattr(settings, "TYPESAFE_API_KEY", "") or os.getenv("TYPESAFE_API_KEY", "")
    if not api_key:
        raise RuntimeError("TYPESAFE_API_KEY is not configured")

    client = getattr(_JEV_THREAD_LOCAL, "client", None)
    if client is None:
        from typesafe_sdk import RetryPolicy, TypeSafeClient

        client = TypeSafeClient(
            api_key=api_key,
            model=getattr(settings, "JEV_MODEL", "jev-latest"),
            timeout=float(getattr(settings, "JEV_TIMEOUT_SECONDS", 3.0)),
            retry=RetryPolicy(max_retries=0),
        )
        _JEV_THREAD_LOCAL.client = client
    return client


def _build_jev_context(conversation_history: list | None) -> list[dict]:
    """Keep only a small recent window for roleplay-vs-real-life disambiguation."""
    context = []
    for turn in (conversation_history or [])[-6:]:
        if not isinstance(turn, dict):
            continue
        sender = (turn.get("sender") or turn.get("role") or "").strip().lower()
        if sender in {"assistant", "ai", "companion"}:
            sender = "companion"
        elif sender in {"human"}:
            sender = "user"
        if sender not in {"user", "bot", "companion"}:
            continue
        value = turn.get("text")
        if value is None:
            value = turn.get("content", "")
        if isinstance(value, str) and value.strip():
            context.append({"speaker": sender, "text": value.strip()[:600]})
    return context


def should_ingest_into_reeve(
    text: str,
    conversation_history: list | None = None,
) -> bool:
    """
    Ask Jev whether this user message is worth retaining as long-term memory.

    No keyword or message-length heuristic decides the write. Jev returns typed
    decisions; deterministic code enforces confidence, category, and sensitivity
    thresholds. On missing configuration or model failure, this fails closed.
    """
    if not text or not text.strip():
        return False

    if not (getattr(settings, "TYPESAFE_API_KEY", "") or os.getenv("TYPESAFE_API_KEY", "")):
        logger.warning("[Jev Memory Gate] TYPESAFE_API_KEY missing; skipping memory write")
        return False

    state = {
        "candidate_user_message": text.strip()[:4000],
        "recent_conversation_for_disambiguation_only": _build_jev_context(conversation_history),
        "interaction_mode": "fictional companion roleplay chat",
        "decision_goal": (
            "Decide whether this exact user message contains a durable, useful, "
            "real-world fact about the user for future personalization."
        ),
    }

    try:
        from typesafe_sdk import Choice, Noul

        response = _get_jev_client().system_one(
            state=state,
            questions={
                "memory_action": Choice(
                    instructions=(
                        "Should this exact candidate user message be saved to long-term "
                        "personal memory? Choose STORE only when the candidate clearly "
                        "communicates a durable or reusable real-world fact about the user, "
                        "such as a stable profile fact, preference, real relationship, ongoing "
                        "goal or plan, or significant real-life event. The candidate message "
                        "itself must support the fact. Use recent conversation only to "
                        "disambiguate whether the user is speaking in-character or about real "
                        "life; never infer a new fact from context. Choose DISCARD for small "
                        "talk, jokes, generic observations, temporary moods or conditions, "
                        "one-off details without future value, hypothetical examples, "
                        "roleplay dialogue or fictional-world facts, recall questions, "
                        "requests to retrieve something already remembered, or ambiguity."
                    ),
                    criteria={
                        "store": "A supported, useful real-world user memory should be retained.",
                        "discard": "No supported durable real-world user memory should be retained.",
                    },
                ),
                "memory_type": Choice(
                    instructions=(
                        "Classify the candidate message by its primary memory type. "
                        "Classify only what the user explicitly states; use the recent "
                        "conversation only to distinguish real life from fictional roleplay."
                    ),
                    criteria={
                        "profile_fact": "A durable real-world fact about the user.",
                        "preference": "A stable user preference, taste, or recurring personal choice.",
                        "relationship": "A real-world relationship or durable fact about someone close to the user.",
                        "goal_or_plan": "An ongoing real-world goal, commitment, or future plan.",
                        "significant_event": "A meaningful real-world life event worth recalling later.",
                        "fictional_roleplay": "An in-character statement, fictional person, or event in the roleplay world.",
                        "temporary_state": "A temporary mood, location, condition, or one-off status.",
                        "small_talk": "A greeting, joke, reaction, or casual conversation without durable information.",
                        "recall_query": "A request to remember, retrieve, or repeat information already stored.",
                        "hypothetical": "A hypothetical, example, speculation, or unconfirmed possibility.",
                        "other": "Anything that does not fit the categories above.",
                    },
                ),
                "sensitive_data": Noul(
                    instructions=(
                        "Does the candidate contain highly sensitive personal data or secrets "
                        "that should not be placed in general-purpose companion memory? Treat "
                        "credentials, passwords, authentication tokens, payment or bank details, "
                        "government identifiers, precise home addresses, and highly sensitive "
                        "medical or intimate details as sensitive. Ordinary hobbies, preferences, "
                        "and non-sensitive relationship facts are not sensitive."
                    ),
                ),
            },
        )

        action = response.choices["memory_action"]
        memory_type = response.choices["memory_type"]
        sensitive_probability = float(response.nouls["sensitive_data"].noul)
        store_probability = float(action.probabilities.get("store", 0.0))
        action_confidence = float(action.confidence or 0.0)
        type_confidence = float(memory_type.confidence or 0.0)
        category = memory_type.choice

        approved = (
            action.choice == "store"
            and store_probability >= 0.80
            and action_confidence >= 0.65
            and category in _STOREABLE_MEMORY_TYPES
            and type_confidence >= 0.60
            and sensitive_probability < 0.50
        )
        logger.info(
            "[Jev Memory Gate] decision=%s category=%s store_probability=%.3f "
            "action_confidence=%.3f type_confidence=%.3f sensitive_probability=%.3f",
            "store" if approved else "discard",
            category,
            store_probability,
            action_confidence,
            type_confidence,
            sensitive_probability,
        )
        return approved
    except Exception as exc:
        # No hardcoded fallback: if Jev cannot make the decision, do not write.
        logger.warning("[Jev Memory Gate] Decision failed; skipping memory write: %s", exc)
        return False





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
