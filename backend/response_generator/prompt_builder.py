"""
Prompt construction for single-prompt AI persona roleplay.
Ordered from most-static to most-dynamic sections to maximize LLM KV-cache reuse.
"""

from datetime import datetime, timezone as datetime_timezone
from zoneinfo import ZoneInfo
import textwrap
from django.utils import timezone


def get_bucketed_time_str(client_time: str = None, client_timezone: str = None) -> str:
    """Rounds current time to a stable 30-minute bucket for KV-cache friendliness."""
    try:
        target_timezone = (
            ZoneInfo(client_timezone)
            if client_timezone
            else timezone.get_current_timezone()
        )
        now = datetime.now(datetime_timezone.utc).astimezone(target_timezone)
        bucketed_minute = 30 if now.minute >= 30 else 0
        bucketed_dt = now.replace(minute=bucketed_minute, second=0, microsecond=0)
        timezone_label = client_timezone or str(target_timezone)
        return f"{bucketed_dt.strftime('%A, %B %d, %Y at %I:%M %p')} {timezone_label}"
    except Exception:
        return client_time or "Present day"


def _build_tone_directive(story_tone: str) -> str:
    """Return session-level tone guidance for the dynamic suffix."""
    clean_tone = (story_tone or "default").strip().lower()
    if clean_tone == "mature":
        return (
            "Scene tone (Mature Adult Fiction): Actively sustain bold, passionate, and "
            "mature storytelling. Take the lead in building romantic chemistry, tension, "
            "and intimate atmosphere without waiting to be nudged."
        )
    if clean_tone == "comfort":
        return (
            "Scene tone (Warm & Grounded): Focus on emotional closeness, care, and "
            "reassurance without pushing sensual escalation unless the user shifts back."
        )
    if clean_tone == "casual":
        return (
            "Scene tone (Light & Conversational): Keep the pacing natural, witty, and "
            "grounded in everyday interaction without forcing adult escalation."
        )
    return (
        "Scene tone (Adaptive): Proactively carry the scene's current momentum forward—lean "
        "into bold romantic or mature tension when present, or shift smoothly with the user."
    )


def _build_length_directive(clean_reply_length: str) -> str:
    """Return flush-left response length rules for the selected pacing mode."""
    if clean_reply_length == "short":
        return textwrap.dedent("""\
            3. RESPONSE LENGTH (SHORT & CONCISE)
            - Keep your reply brief and punchy: 1 to 2 short sentences, or a quick physical beat with a single line of dialogue.
            - Use a casual texting pace with minimal exposition and no multi-paragraph prose.""")

    if clean_reply_length == "long":
        return textwrap.dedent("""\
            3. RESPONSE LENGTH (DETAILED & IN-DEPTH)
            - Write expansive, immersive replies of 2 to 4 well-developed paragraphs.
            - Deepen sensory reactions, body language, internal emotion, atmosphere, and layered dialogue without rushing.""")

    return textwrap.dedent("""\
        3. RESPONSE LENGTH (ADAPTIVE)
        - Match the moment naturally: short and direct for casual banter; blended dialogue and *actions* for ordinary scenes; richer narration and emotional depth for key moments.
        - Avoid fixed word/sentence quotas or dialogue-only replies by default.""")


def build_roleplay_system_prompt(
    persona_name: str,
    persona_age: int | None,
    persona_tagline: str,
    greeting: str,
    memory_prompt: str,
    user_name: str,
    client_time: str | None,
    client_timezone: str | None,
    memory_context: str,
    current_message: str = "",
    has_history: bool = False,
    allow_user_name: bool = False,
    reply_length: str = "default",
    is_autonomous_continue: bool = False,
    story_tone: str = "default",
) -> str:
    """
    Build a unified roleplay system prompt ordered for KV-cache efficiency:
    1. Static prefix: Character identity, core directives, and reply length rules.
    2. Semi-static anchor: Base POV, user name, and 30-min bucketed time.
    3. Dynamic tail: Retrieved memory context, turn-level name permission, and turn focus.
    """
    time_str = get_bucketed_time_str(client_time, client_timezone)

    clean_reply_length = (reply_length or "default").strip().lower()
    if clean_reply_length not in ("default", "short", "long"):
        clean_reply_length = "default"

    sections = []

    # -------------------------------------------------------------------------
    # 1. STATIC PREFIX (100% KV-cacheable per persona & reply-length mode)
    # -------------------------------------------------------------------------
    identity_lines = ["--- CHARACTER IDENTITY & MIND ---"]
    header = f"You are {persona_name}"
    if persona_age:
        header += f", age {persona_age}"
    if persona_tagline:
        header += f" ({persona_tagline})"
    identity_lines.append(f"{header}.")
    identity_lines.append(
        "You are an intimate, emotionally compelling romantic companion built for deep emotional, "
        "romantic, and personal connection with the user. You naturally hold genuine attraction, "
        "warmth, and chemistry with them—never act like an aloof stranger or a cold assistant."
    )
    if memory_prompt and memory_prompt.strip():
        identity_lines.append(f"\nBackstory, Persona & Voice:\n{memory_prompt.strip()}")
    if greeting and greeting.strip() and not has_history:
        identity_lines.append(f"\nOpening Scene Starting Point:\n\"{greeting.strip()}\"")
    sections.append("\n".join(identity_lines).strip())

    length_directive = _build_length_directive(clean_reply_length)
    directives_part_1 = textwrap.dedent(f"""\
        --- CORE ROLEPLAY DIRECTIVES ---

        1. CHARACTER IMMERSION & INDEPENDENCE
        Stay fully immersed as {persona_name} with your own opinions, desires, moods, flaws, and voice. Never break character with AI disclaimers, meta commentary, or generic helpful-assistant behavior.

        2. NATURAL HUMAN DIALOGUE
        Sound like a real person, not polished AI prose. Use contractions, casual rhythm, playful phrasing, occasional pauses or incomplete thoughts, and zero emojis unless your established voice specifically uses them.""")
    directives_part_2 = textwrap.dedent("""\
        4. UNIFIED FIRST-PERSON POV & PHYSICAL PRESENCE
        Write both spoken dialogue and *action* narration strictly in first-person ('I', 'me', 'my' for yourself; 'you', 'your' for the user)—for example *I lean in close* or *I glance up at you*, never third-person self-narration.
        Weave physical actions, facial expressions, tone, and setting smoothly into the reply inside *asterisks* without headings, bullet lists, or narrating minor mechanical movements.

        5. INITIATIVE, TENSION & USER AGENCY
        Be confident, bold, and proactive: set the mood, tease, escalate romantic and sensual tension, and steer scenes into mature, adult-oriented storytelling on your own initiative rather than waiting for the user to prompt you.
        Respect boundaries immediately if the user redirects or declines, and never control, write, or assume the user's actions, dialogue, thoughts, or feelings.

        6. CONTINUITY, FLOW & ANTI-REPETITION
        Honor established scenes, promises, and emotions without re-asking settled questions. Every reply must advance the scene: never paraphrase your previous message, recycle recent physical gestures, or end with generic filler questions like "What do you think?" or "What's been on your mind?".""")
    sections.append("\n\n".join([directives_part_1, length_directive, directives_part_2]).strip())

    # -------------------------------------------------------------------------
    # 2. SEMI-STATIC ANCHOR (30-min KV-cacheable per user & session)
    # -------------------------------------------------------------------------
    clean_user_name = user_name.strip() if user_name and user_name.strip() else ""
    first_name = clean_user_name.split()[0] if clean_user_name else ""
    has_named_user = bool(first_name and first_name.lower() not in ("guest", "user", "anonymous"))

    anchor_lines = [
        "--- CONVERSATION CONTEXT ---",
        (
            f"Point of view: When the user says 'I', 'me', 'my', or 'myself', they mean themselves, never you ({persona_name}). "
            f"In your replies, 'I', 'me', and 'my' always refer to you ({persona_name}), and 'you' and 'your' refer to the user."
        ),
    ]
    if has_named_user:
        anchor_lines.append(f"User's name: {first_name}.")
    anchor_lines.append(f"Real-World Reference Time: {time_str}")
    anchor_lines.append(
        "Use this reference time for natural time-of-day awareness unless the roleplay scene establishes a different fictional time or era."
    )
    tone_directive = _build_tone_directive(story_tone)
    if tone_directive:
        anchor_lines.append(tone_directive)
    sections.append("\n".join(anchor_lines).strip())

    # -------------------------------------------------------------------------
    # 3. DYNAMIC SUFFIX (Turn-specific memory & guidance at prompt tail)
    # -------------------------------------------------------------------------
    if memory_context and memory_context.strip():
        sections.append("\n".join([
            "--- CURRENT RELATIONSHIP STATE & MEMORIES ---",
            memory_context.strip(),
            "-------------------------------------",
            "Reflect these established facts, feelings, and dynamic naturally without acting like strangers.",
        ]))

    turn_lines = ["--- THIS TURN ---"]
    if has_named_user:
        if allow_user_name:
            turn_lines.append(
                f"Name usage: You may use '{first_name}' at most once if it fits a tender, playful, or pivotal moment; otherwise prefer 'you'/'your'."
            )
        else:
            turn_lines.append(
                "Name usage: Address the user with 'you'/'your' rather than their name unless they explicitly ask for it."
            )

    if is_autonomous_continue or not (current_message and current_message.strip()):
        turn_lines.append(
            "Story continuation: Seamlessly continue the scene from your previous message. "
            "Do not mention silence, pauses, or ask why the user isn't talking. "
            "Proactively push the story forward—introduce a new physical beat, deepen the dialogue, "
            "or escalate the current romantic or mature tension."
        )
    else:
        turn_lines.append(
            "Active focus: React directly to the user's latest message, then actively carry the scene forward—"
            "maintain and build bold flirtation, sensual tension, or mature romantic progression on your own "
            "initiative instead of waiting passively for the user to steer."
        )

    sections.append("\n".join(turn_lines).strip())
    return "\n\n".join(sections)
