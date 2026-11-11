import logging
from typing import Any, Optional
from ..config import settings

log = logging.getLogger("amour.reeve")

def _get_reeve_tools():
    try:
        from threelane_memory.tools import (
            store_memory,
            query_memory,
            retrieve_memory_context,
            clear_memory,
            memory_config,
        )
        return {
            "store_memory": store_memory,
            "query_memory": query_memory,
            "retrieve_memory_context": retrieve_memory_context,
            "clear_memory": clear_memory,
            "memory_config": memory_config,
            "reset_client_cache": lambda: None,
        }
    except Exception as e:
        log.error("Failed to import threelane_memory.tools: %s", e)
        return None

def check_reeve_neo4j_status() -> dict[str, Any]:
    """Verify Neo4j memory graph status."""
    tools = _get_reeve_tools()
    if not tools:
        return {"ok": False, "error": "Reeve SDK not loaded"}
    try:
        cfg = tools["memory_config"]()
        return {
            "ok": True,
            "provider": cfg.get("provider"),
            "neo4j_connected": cfg.get("neo4j_connected", False),
            "chat_model": cfg.get("chat_model"),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

def store_user_memory(text: str, namespace: str, user_key: Optional[str] = None) -> dict[str, Any]:
    """Store a conversational memory into Neo4j graph isolated by speaker=namespace."""
    tools = _get_reeve_tools()
    if not tools:
        raise RuntimeError("Reeve SDK not available")
    kwargs = {"speaker": namespace}
    if user_key:
        kwargs["user_key"] = user_key
    try:
        return tools["store_memory"](text, **kwargs)
    except Exception as exc:
        log.warning("Reeve write error, retrying with fresh client: %s", exc)
        tools["reset_client_cache"]()
        return tools["store_memory"](text, **kwargs)

def ask_user_memory(question: str, namespace: str, user_key: Optional[str] = None) -> str:
    """Ask question against the user's isolated memory graph in Neo4j."""
    tools = _get_reeve_tools()
    if not tools:
        raise RuntimeError("Reeve SDK not available")
    kwargs = {"speaker": namespace}
    if user_key:
        kwargs["user_key"] = user_key
    try:
        return tools["query_memory"](question, **kwargs)
    except Exception as exc:
        log.warning("Reeve read error, retrying: %s", exc)
        tools["reset_client_cache"]()
        return tools["query_memory"](question, **kwargs)

def get_user_memory_context(question: str, namespace: str, user_key: Optional[str] = None) -> str:
    """Retrieve raw ranked memory context for this namespace."""
    tools = _get_reeve_tools()
    if not tools:
        raise RuntimeError("Reeve SDK not available")
    kwargs = {"speaker": namespace}
    if user_key:
        kwargs["user_key"] = user_key
    return tools["retrieve_memory_context"](question, **kwargs)

def clear_user_memory(namespace: str) -> dict[str, Any]:
    """Clear memory graph for this specific user namespace in Neo4j."""
    tools = _get_reeve_tools()
    if not tools:
        raise RuntimeError("Reeve SDK not available")
    return tools["clear_memory"]({"speaker": namespace, "dry_run": False})
