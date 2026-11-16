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
from amour_backend.pii_redactor import redact_pii

logger = logging.getLogger("amour.reeve")

# Keep Reeve extraction requests below Groq's on-demand output-token limits.
REEVE_LLM_MAX_TOKENS = 512
os.environ["LLM_MAX_TOKENS"] = str(REEVE_LLM_MAX_TOKENS)

# Ensure REEVE_API_KEY is available in environment
if hasattr(settings, "REEVE_API_KEY") and settings.REEVE_API_KEY:
    os.environ["REEVE_API_KEY"] = settings.REEVE_API_KEY

# Configure Reeve Chat LLM to use Groq Qwen (decoupling it from Bedrock)
groq_key = getattr(settings, "GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
if groq_key:
    os.environ.setdefault("OPENAI_API_KEY", groq_key)
    os.environ.setdefault("OPENAI_BASE_URL", "https://api.groq.com/openai/v1")
    os.environ.setdefault("OPENAI_API_BASE", "https://api.groq.com/openai/v1")
    os.environ.setdefault("OPENAI_CHAT_MODEL", "qwen/qwen3.8-27b")
    os.environ.setdefault("LLM_PROVIDER", "openai")
    os.environ.setdefault("EMBEDDING_PROVIDER", "bedrock")

# Enable Reeve's native background worker (PersistWorker) and WriteAhead buffer
os.environ["ASYNC_WRITE_ENABLED"] = "true"
try:
    import threelane_memory.config as _tmc
    _tmc.ASYNC_WRITE_ENABLED = True
    _tmc.LLM_MAX_TOKENS = REEVE_LLM_MAX_TOKENS
except ImportError:
    pass


def _get_memory_tools():
    """
    Returns the local in-process memory operations tools module.
    Exclusively uses local in-process threelane_memory against Neo4j Cloud.
    Configures Reeve to use Groq Qwen for graph LLM extraction and Bedrock Titan for embeddings.
    """
    import threelane_memory.config as cfg
    groq_key = getattr(settings, "GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
    if groq_key:
        os.environ["OPENAI_API_KEY"] = groq_key
        os.environ["OPENAI_BASE_URL"] = "https://api.groq.com/openai/v1"
        os.environ["OPENAI_API_BASE"] = "https://api.groq.com/openai/v1"
        os.environ["OPENAI_CHAT_MODEL"] = "qwen/qwen3.8-27b"
        cfg.LLM_PROVIDER = "openai"
        cfg.OPENAI_API_KEY = groq_key
        cfg.OPENAI_CHAT_MODEL = "qwen/qwen3.8-27b"
        cfg.LLM_MAX_TOKENS = REEVE_LLM_MAX_TOKENS
        os.environ["LLM_MAX_TOKENS"] = str(REEVE_LLM_MAX_TOKENS)
    cfg.EMBEDDING_PROVIDER = "bedrock"
    cfg.BEDROCK_EMBED_MODEL = "amazon.titan-embed-text-v2:0"
    import threelane_memory.tools as tools
    return tools, False


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

    # Redact sensitive PII (credit cards, passwords, SSNs) before graph ingestion
    sanitized_text = redact_pii(text)

    try:
        return tools.store_memory(sanitized_text, **kwargs)
    except Exception as exc:
        logger.warning("Reeve write failed: %s", type(exc).__name__)
        if is_remote and hasattr(tools, "reset_client_cache"):
            tools.reset_client_cache()
            return tools.store_memory(sanitized_text, **kwargs)
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
        logger.warning("Reeve query failed: %s", type(exc).__name__)
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
        logger.warning("Reeve context retrieve failed: %s", type(exc).__name__)
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


def _matches_turn_content(clean_text: str, raw_text: str, summary: str, sender: str = "user") -> bool:
    """
    Deterministic turn matcher that avoids false positives on short messages
    while accurately identifying the target episode across encrypted and plaintext payloads.
    """
    if not clean_text or (not raw_text and not summary):
        return False

    raw_clean = raw_text.strip()
    if raw_clean == clean_text:
        return True

    if sender == "user":
        if f"User: {clean_text}" in raw_text:
            return True
        user_segment = raw_text.split("\nAssistant:")[0]
        if user_segment.replace("User:", "").strip() == clean_text:
            return True
    elif sender == "bot":
        if f"Assistant: {clean_text}" in raw_text:
            return True
        if "\nAssistant:" in raw_text:
            bot_segment = raw_text.split("\nAssistant:", 1)[1]
            if bot_segment.strip() == clean_text:
                return True

    # For multi-word / substantial messages, allow substring match in raw_text or summary
    if len(clean_text) >= 8 and (clean_text in raw_text or clean_text in summary):
        return True

    return False


def delete_memory_for_message(text: str, namespace: str, sender: str = "user", user_key: str = None) -> int:
    """
    Level 2 Deletion: Permanently prune Reeve memory graph and write buffer for a deleted chat message.
    1. Evicts matching unpersisted writes from the in-memory write buffer (and drops mid-flight writes).
    2. Queries Neo4j Episode nodes strictly scoped to `speaker = namespace`.
    3. Deterministically matches the target turn content (handling zero-knowledge AES encryption).
    4. Detach-deletes the matching Episode, State, Action, and Relation nodes.
    5. Cleans up orphaned Entity and Location nodes left with no remaining episodes.
    Returns the count of pruned memory entries/episodes.
    """
    if not text or not text.strip() or not namespace:
        return 0

    clean_text = text.strip()
    deleted_count = 0
    from threelane_memory.crypto import decrypt_field, is_encrypted

    # 1. Evict matching pending items from the in-memory WriteBuffer
    try:
        from threelane_memory.write_buffer import get_write_buffer
        wb = get_write_buffer()
        with wb._lock:
            doomed = []
            for pid, entry in list(wb._entries.items()):
                if entry.speaker != namespace:
                    continue
                raw = getattr(entry, "raw_text", "") or ""
                if is_encrypted(raw):
                    raw = decrypt_field(raw, user_key or getattr(entry, "user_key", None)) or raw
                summ = getattr(entry, "summary", "") or ""
                if _matches_turn_content(clean_text, raw, summ, sender=sender):
                    doomed.append((pid, entry))

            for pid, entry in doomed:
                # If entry was already persisted to Neo4j, keep track of its episode_id
                if entry.episode_id:
                    try:
                        tools, _ = _get_memory_tools()
                        tools.run_query(
                            """
                            MATCH (ep:Episode {id: $ep_id})
                            OPTIONAL MATCH (ep)-[:HAS_STATE]->(s:State)
                            OPTIONAL MATCH (ep)-[:HAS_ACTION]->(a:Action)
                            OPTIONAL MATCH (ep)-[:HAS_RELATION]->(rel:Relation)
                            DETACH DELETE s, a, rel, ep
                            """,
                            {"ep_id": entry.episode_id},
                        )
                    except Exception:
                        pass
                del wb._entries[pid]
                deleted_count += 1

        if doomed:
            logger.info("WriteBuffer: dropped %d queued write(s) for deleted message in namespace %s", len(doomed), namespace)
    except Exception as exc:
        logger.warning("Could not evict from Reeve write buffer: %s", exc)

    # 2. Prune from Neo4j Graph
    try:
        tools, _ = _get_memory_tools()

        episodes = tools.run_query(
            "MATCH (ep:Episode {speaker: $speaker}) RETURN ep.id AS id, ep.raw_text AS raw_text, ep.summary AS summary",
            {"speaker": namespace},
        )

        for ep in episodes:
            ep_id = ep.get("id")
            raw_text = ep.get("raw_text") or ""
            summary = ep.get("summary") or ""

            # Decrypt fields if encrypted with client/user key
            if is_encrypted(raw_text) and user_key:
                raw_text = decrypt_field(raw_text, user_key) or raw_text
            if is_encrypted(summary) and user_key:
                summary = decrypt_field(summary, user_key) or summary

            if _matches_turn_content(clean_text, raw_text, summary, sender=sender) and ep_id:
                tools.run_query(
                    """
                    MATCH (ep:Episode {id: $ep_id})
                    OPTIONAL MATCH (ep)-[:HAS_STATE]->(s:State)
                    OPTIONAL MATCH (ep)-[:HAS_ACTION]->(a:Action)
                    OPTIONAL MATCH (ep)-[:HAS_RELATION]->(rel:Relation)
                    DETACH DELETE s, a, rel, ep
                    """,
                    {"ep_id": ep_id},
                )
                deleted_count += 1
                logger.info("Level 2: Pruned Reeve episode %s for namespace %s", ep_id, namespace)

        # 3. Clean up orphaned Entity and Location nodes for this namespace
        if deleted_count > 0:
            tools.run_query(
                """
                MATCH (e:Entity {speaker: $speaker})
                WHERE NOT (e)<-[:INVOLVES]-(:Episode)
                  AND NOT (e)<-[:OF_ENTITY|BY_ENTITY|ON_ENTITY|FROM_ENTITY|TO_ENTITY]-()
                DETACH DELETE e
                """,
                {"speaker": namespace},
            )
            tools.run_query(
                """
                MATCH (l:Location {speaker: $speaker})
                WHERE NOT (l)<-[:AT_LOCATION]-(:Episode)
                DETACH DELETE l
                """,
                {"speaker": namespace},
            )
            try:
                from threelane_memory.retriever import forget_image_probe
                forget_image_probe(namespace)
            except Exception:
                pass

    except Exception as exc:
        logger.warning("Reeve Neo4j episode pruning error: %s", exc)

    return deleted_count


def __getattr__(name: str):
    """
    Backward-compatibility proxy (PEP 562).
    Response generation logic has been decoupled from memory/Reeve service
    and relocated to `response_generator` outside the memory directory.
    """
    if name in (
        "generate_companion_reply",
        "sanitize_companion_reply",
        "strip_emojis",
        "GLOBAL_COMPANION_DIRECTIVES",
        "get_bucketed_time_str",
    ):
        import response_generator

        return getattr(response_generator, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def __dir__():
    return list(globals().keys()) + [
        "generate_companion_reply",
        "sanitize_companion_reply",
        "strip_emojis",
        "GLOBAL_COMPANION_DIRECTIVES",
        "get_bucketed_time_str",
    ]
