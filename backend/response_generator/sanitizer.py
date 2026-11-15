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


def clean_user_name_vocatives(
    text: str,
    user_name: str = "",
    allow_name: bool = False,
    persona_name: str = "",
) -> str:
    """
    Grammatically clean user name vocatives without hardcoded keywords.
    - If allow_name is False: strips leading, trailing, and mid-sentence vocatives,
      and converts narrative action references (e.g. 'at Alex' -> 'at you', 'Alex\'s' -> 'your').
    - If allow_name is True: permits at most 1 natural mention, pruning repetitive vocatives.
    - Explicitly guards against persona_name so the persona's own identity is never modified.
    """
    if not text or not user_name:
        return text

    first_name = user_name.strip().split()[0]
    if not first_name or first_name.lower() in ("guest", "user", "anonymous"):
        return text

    # Guard: If user's name matches the persona's name, do not alter third-person persona actions
    persona_first = persona_name.strip().split()[0] if persona_name else ""
    if persona_first and first_name.lower() == persona_first.lower():
        return text

    esc = re.escape(first_name)

    if not allow_name:
        # 1. Trailing vocative: e.g. "Are you okay, Alex?" -> "Are you okay?"
        text = re.sub(rf",\s*{esc}(?=[.!?~…\n]|$)", "", text, flags=re.IGNORECASE)

        # 2. Leading vocative: e.g. "Alex, what happened?" -> "What happened?"
        # Also handles after punctuation, newline, or action asterisk
        def fix_leading(m):
            post = m.group(1) or ""
            cap = post[:1].upper() + post[1:] if post else ""
            start = m.start()
            needs_space = start > 0 and text[start - 1] not in ("\n", " ", "\t")
            return (" " if needs_space else "") + cap

        text = re.sub(
            rf"(?i)(?:^|(?<=[.!?\n])|(?<=\*))\s*(?:(?:hey|hi|hello|oh|ah|dear)\s+)?{esc}\s*[,…\.]+\s*([a-zA-Z])?",
            fix_leading,
            text,
        )

        # 3. Mid-sentence vocative: e.g. "I think, Alex, that..." -> "I think that..."
        text = re.sub(rf",\s*{esc}\s*,", ",", text, flags=re.IGNORECASE)

        # 4. Actions / Narrative prepositions: e.g. "*smiles at Alex*" -> "*smiles at you*"
        text = re.sub(rf"(?i)\b(at|to|with|toward|towards|beside|near|from|for)\s+{esc}\b", r"\1 you", text)

        # 5. Possessives: e.g. "Alex's hand" -> "your hand"
        text = re.sub(rf"(?i)\b{esc}['’]s\b", "your", text)

        return re.sub(r"  +", " ", text).strip()

    # When allow_name is True: cap at 1 mention, prune subsequent repetitive vocatives
    matches = list(re.finditer(rf"\b{esc}\b", text, flags=re.IGNORECASE))
    if len(matches) > 1:
        first_span_end = matches[0].end()
        head = text[:first_span_end]
        tail = text[first_span_end:]
        tail = re.sub(rf",\s*{esc}(?=[.!?~…\n]|$)", "", tail, flags=re.IGNORECASE)
        tail = re.sub(rf"(?i)\b{esc}\s*,\s*", "", tail)
        text = head + tail

    return re.sub(r"  +", " ", text).strip()


def sanitize_companion_reply(text: str, user_name: str = "", allow_name: bool = False) -> str:
    """Sanitize reply: strip emojis, remove markdown code blocks, clean artifacts, and clean name vocatives."""
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
    return clean_user_name_vocatives(cleaned, user_name=user_name, allow_name=allow_name)
