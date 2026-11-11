"""
Response Generator package for Amour AI.

Handles conversational persona response generation, KV cache prompt assembly,
output sanitization, and LLM inference.
"""

from .generator import (
    generate_companion_reply,
    sanitize_companion_reply,
    strip_emojis,
    get_bucketed_time_str,
)

__all__ = [
    "generate_companion_reply",
    "sanitize_companion_reply",
    "strip_emojis",
    "get_bucketed_time_str",
]
