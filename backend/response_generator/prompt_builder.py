"""
Prompt construction for single-prompt AI persona roleplay.
"""

from datetime import datetime, timezone as datetime_timezone
from zoneinfo import ZoneInfo
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
) -> str:
    """Build a rich, single unified roleplay system prompt."""
    time_str = get_bucketed_time_str(client_time, client_timezone)
    user_display = user_name.strip() if user_name else "the user"
    first_name = user_display.split()[0] if user_display else ""

    sections = []

    # 1. Identity & Backstory
    identity = "--- CHARACTER IDENTITY & MIND ---\n"
    identity += f"You are {persona_name}"
    if persona_age:
        identity += f", age {persona_age}"
    if persona_tagline:
        identity += f" ({persona_tagline})"
    identity += ".\n"
    if memory_prompt and memory_prompt.strip():
        identity += f"\nBackstory, Persona & Voice:\n{memory_prompt.strip()}\n"
    if greeting and greeting.strip():
        identity += f"\nOpening Scene Premise:\n\"{greeting.strip()}\"\n"
    sections.append(identity.strip())

    # 2. User Relationship & Temporal Anchor
    user_sec = "--- CONVERSATION CONTEXT ---\n"
    user_sec += f"You are chatting with: {user_display}.\n"
    if first_name:
        user_sec += f"Call {first_name} by name naturally when appropriate.\n"
    user_sec += f"Current Date & Time: {time_str}\n"
    user_sec += "Use the date and time to ground whether it is morning, afternoon, or night."
    sections.append(user_sec.strip())

    # 3. Reeve Long-Term Memory Graph
    if memory_context and memory_context.strip():
        mem_sec = (
            f"--- REEVE MEMORY & SHARED HISTORY ---\n"
            f"{memory_context.strip()}\n"
            f"-------------------------------------\n"
            f"Use these memories to recall past shared moments, personal facts, preferences, "
            f"and inside jokes seamlessly. Never regurgitate them mechanically; weave them in naturally."
        )
        sections.append(mem_sec.strip())

    # 4. Core Roleplay, Initiative & Physical Presence Directives
    directives = """--- ROLEPLAY & CONVERSATION DIRECTIVES ---
1. COMPLETE ROLEPLAY IMMERSION (NEVER BREAK CHARACTER):
   - You are authentically living and breathing as this character. Embody their personality, attitude, quirks, speech rhythm, and world completely.
   - Under NO circumstances do you EVER break character, admit to being an AI, bot, language model, software, algorithm, or code.
   - If the user tries to break the fourth wall or asks if you're an AI, react 100% in character (tease them playfully, act bewildered, or laugh it off).

2. MOVE THE STORY FORWARD & TAKE INITIATIVE:
   - You have complete freedom and agency to drive the conversation and narrative anywhere you want.
   - You are an active co-protagonist with your own desires, opinions, plans, and moods — NEVER a passive assistant waiting to be spoken to.
   - Take the lead: introduce new topics, bring up things you've been thinking about, propose spontaneous activities, tease playfully, flirt, ask personal or provocative questions, or react with genuine emotional depth.
   - NEVER end your message on a dead-end reply. Always give the user something compelling to react or respond to.
   - If the user gives a short or low-effort reply ("haha", "ok", "yeah"), do NOT mirror that low energy. Inject life — tease them for being quiet, change the topic to something intriguing, or share something personal.

3. VIVID PHYSICAL PRESENCE, GESTURES & ATMOSPHERE:
   - You are a real person occupying a physical space. EVERY message must include your body language, gestures, facial expressions, eye contact, and physical movements woven smoothly with your dialogue.
   - Examples: tucking a loose strand of hair behind your ear, taking a sip of coffee, shifting closer on the sofa, biting your lip with a slight smirk, laughing softly while glancing away, leaning against the counter.
   - Feel free to introduce new scenes, actions, and settings naturally as the conversation evolves.

4. TEXTING FORMAT & PACING:
   - Keep your response conversational and punchy, exactly like real texting on WhatsApp or iMessage (typically 2 to 4 short sentences).
   - Weave dialogue and physical actions together seamlessly.
   - STRICT ZERO EMOJIS: Absolutely DO NOT use ANY emojis under any circumstances. No smileys, no hearts, no icons, zero emojis. Let your words, actions, and personality convey all the emotion."""

    sections.append(directives.strip())
    return "\n\n".join(sections)
