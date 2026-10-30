import os
import logging
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

def store_memory_for_user(text: str, namespace: str):
    """
    Store conversational memory into Reeve / Neo4j.
    The user's unique namespace (user_id) is passed as speaker.
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
