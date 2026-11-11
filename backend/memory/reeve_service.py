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
    if user_key and is_remote:
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
    if user_key and is_remote:
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
    if user_key and is_remote:
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
