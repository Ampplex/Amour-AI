"""
Text sanitization utilities for Amour companion responses.
"""

import re
import unicodedata


def strip_emojis(text: str) -> str:
    """Strip all unicode emoji characters, pictographs, and symbols from text."""
    if not text:
        return ""
    result = []
    for char in text:
        cat = unicodedata.category(char)
        cp = ord(char)
        # Skip emojis, dingbats, transport/map symbols, emoticons, pictographs
        if (
            cat == "So"
            or 0x1F600 <= cp <= 0x1F64F
            or 0x1F300 <= cp <= 0x1F5FF
            or 0x1F680 <= cp <= 0x1F6FF
            or 0x1F700 <= cp <= 0x1F77F
            or 0x1F780 <= cp <= 0x1F7FF
            or 0x1F800 <= cp <= 0x1F8FF
            or 0x1F900 <= cp <= 0x1F9FF
            or 0x1FA00 <= cp <= 0x1FA6F
            or 0x1FA70 <= cp <= 0x1FAFF
            or 0x2600 <= cp <= 0x26FF
            or 0x2700 <= cp <= 0x27BF
            or 0xFE00 <= cp <= 0xFE0F
            or 0x1F1E6 <= cp <= 0x1F1FF
        ):
            continue
        result.append(char)
    cleaned = "".join(result)
    return re.sub(r"  +", " ", cleaned).strip()


def sanitize_companion_reply(text: str) -> str:
    """Sanitize reply: strip emojis, remove markdown code blocks, clean artifacts."""
    if not text:
        return ""
    cleaned = strip_emojis(text)
    if "```" in cleaned:
        cleaned = re.sub(r"```[\s\S]*?```", "", cleaned).strip()
    # Strip meta-parentheticals like (just kidding, no emojis)
    cleaned = re.sub(
        r"\((?:just kidding,?\s*)?no emojis?\)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    return cleaned
