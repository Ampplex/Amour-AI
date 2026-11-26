"""
Async background tone tracker for story/scene mood classification.

Runs AFTER the reply is already sent to the user, so it adds 0 ms to response
latency while still catching subtext, pacing shifts, and gradual mood changes
that keyword lists miss.

Flow:
  1. Current turn uses the existing `story_tone` stored in PostgreSQL.
  2. After returning the reply, `schedule_tone_update` fires a daemon thread
     that inspects the latest exchange with a fast, low-cost model.
  3. If the mood genuinely shifts, it updates `story_tone` in PostgreSQL so
     the next turn picks up the new tone.
"""

import logging
import threading

logger = logging.getLogger("amour.tone_tracker")

VALID_TONES = {"default", "casual", "comfort", "mature"}


def _classify_next_tone(
    user_message: str,
    assistant_reply: str,
    current_tone: str,
    classify_fn,  # (messages, max_tokens, temperature) -> str
) -> str:
    prompt = [
        {
            "role": "system",
            "content": (
                "You track the active story tone of a roleplay conversation.\n"
                "Allowed tones: default, casual, comfort, mature.\n"
                "Rules:\n"
                "- Keep the CURRENT tone unless the latest exchange clearly shifts the mood or intimacy level.\n"
                "- Short or neutral replies ('ok', 'go on', '*nods*') must keep the CURRENT tone.\n"
                "- Reply with ONLY one word from: default, casual, comfort, mature."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Current tone: {current_tone}\n"
                f"User: {user_message}\n"
                f"Assistant: {assistant_reply}\n"
                "Next tone:"
            ),
        },
    ]

    raw = (classify_fn(prompt, max_tokens=8, temperature=0.1) or "").strip().lower().strip(".,\"'")
    return raw if raw in VALID_TONES else current_tone


def schedule_tone_update(
    conversation_id,
    user_message: str,
    assistant_reply: str,
    current_tone: str,
    classify_fn,
    save_tone_fn,  # (conv_id, new_tone) -> None
) -> None:
    """Fire-and-forget background tone check so chat latency stays untouched."""
    clean_current = current_tone if current_tone in VALID_TONES else "default"

    def _worker():
        try:
            next_tone = _classify_next_tone(
                user_message=user_message,
                assistant_reply=assistant_reply,
                current_tone=clean_current,
                classify_fn=classify_fn,
            )
            if next_tone != clean_current:
                save_tone_fn(conversation_id, next_tone)
                logger.info(
                    "story_tone updated %s → %s for conversation %s",
                    clean_current, next_tone, conversation_id,
                )
        except Exception as exc:
            logger.warning("Background story_tone update failed: %s", exc)

    threading.Thread(target=_worker, daemon=True).start()
