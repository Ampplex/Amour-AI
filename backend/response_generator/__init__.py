"""
Response Generator package for Amour AI.

Handles conversational persona response generation, KV cache prompt assembly,
output sanitization, and LLM inference outside the memory/Reeve service directory.
"""

from .generator import (
    generate_companion_reply,
    initialize_story_state,
    retrieve_story_state,
    sanitize_companion_reply,
    strip_emojis,
    GLOBAL_COMPANION_DIRECTIVES,
    get_bucketed_time_str,
)

__all__ = [
    "generate_companion_reply",
    "initialize_story_state",
    "retrieve_story_state",
    "sanitize_companion_reply",
    "strip_emojis",
    "GLOBAL_COMPANION_DIRECTIVES",
    "get_bucketed_time_str",
]
