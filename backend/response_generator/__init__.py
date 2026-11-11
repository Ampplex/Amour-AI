"""
Response Generator package for Amour AI.

Modular conversational persona response generation, KV cache prompt assembly,
output sanitization, and LLM inference.
"""

from .generator import generate_companion_reply
from .prompt_builder import (
    build_roleplay_system_prompt,
    get_bucketed_time_str,
)
from .llm_client import (
    call_llm,
    get_llm_configuration,
)
from .sanitizer import (
    sanitize_companion_reply,
    strip_emojis,
)

__all__ = [
    "generate_companion_reply",
    "build_roleplay_system_prompt",
    "get_bucketed_time_str",
    "call_llm",
    "get_llm_configuration",
    "sanitize_companion_reply",
    "strip_emojis",
]
