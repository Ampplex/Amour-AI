"""
Async background tone tracker for story/scene mood classification.

Runs AFTER the reply is already sent to the user, so it adds 0 ms to response
latency while still catching subtext, pacing shifts, and gradual mood changes
that keyword lists miss.

Uses Amazon Bedrock (Mistral Large) for classification so the primary Groq/Qwen
chat model is never overloaded with extra calls.

Flow:
  1. Current turn uses the existing `story_tone` stored in PostgreSQL.
  2. After returning the reply, `schedule_tone_update` fires a daemon thread
     that inspects the latest exchange with Bedrock.
  3. If the mood genuinely shifts, it updates `story_tone` in PostgreSQL so
     the next turn picks up the new tone.
"""

import logging
import os
import threading

logger = logging.getLogger("amour.tone_tracker")

VALID_TONES = {"default", "casual", "comfort", "mature"}


def _classify_with_bedrock(messages: list, max_tokens: int = 8, temperature: float = 0.1) -> str:
    """Call Bedrock Converse API for a lightweight tone classification."""
    import boto3
    from django.conf import settings

    region = (
        getattr(settings, "AWS_REGION", "")
        or os.environ.get("AWS_REGION", "us-west-2")
    ).strip()
    model_id = (
        getattr(settings, "BEDROCK_MODEL_ID", "")
        or os.environ.get("BEDROCK_MODEL_ID", "mistral.mistral-large-2407-v1:0")
    ).strip()

    system_blocks = []
    conversation = []

    for item in messages:
        role = item.get("role")
        content = item.get("content", "")
        if not isinstance(content, str) or not content.strip():
            continue
        if role == "system":
            system_blocks.append({"text": content.strip()})
        elif role in ("user", "assistant"):
            if conversation and conversation[-1]["role"] == role:
                conversation[-1]["content"].append({"text": content.strip()})
            else:
                conversation.append({
                    "role": role,
                    "content": [{"text": content.strip()}],
                })

    if not conversation:
        conversation.append({"role": "user", "content": [{"text": "Hello"}]})
    elif conversation[-1]["role"] != "user":
        conversation.append({"role": "user", "content": [{"text": "classify"}]})

    client = boto3.client("bedrock-runtime", region_name=region)
    response = client.converse(
        modelId=model_id,
        system=system_blocks,
        messages=conversation,
        inferenceConfig={
            "maxTokens": max_tokens,
            "temperature": temperature,
            "topP": 0.9,
        },
    )

    content_blocks = (
        response.get("output", {})
        .get("message", {})
        .get("content", [])
    )
    return "".join(
        block.get("text", "")
        for block in content_blocks
        if isinstance(block, dict) and isinstance(block.get("text"), str)
    ).strip()


def _classify_next_tone(
    user_message: str,
    assistant_reply: str,
    current_tone: str,
    classify_fn=None,
) -> str:
    if classify_fn is None:
        classify_fn = _classify_with_bedrock

    prompt = [
        {
            "role": "system",
            "content": (
                "You track the active story tone of a roleplay conversation.\n"
                "Allowed tones: default, casual, comfort, mature.\n"
                "Definitions:\n"
                "- default: Adaptive general roleplay, romantic banter, and everyday pacing.\n"
                "- mature: Any adult fiction, explicit or implicit erotic/sensual tension, sexual or physical intimacy, passion, or adult intentions.\n"
                "- comfort: Emotional caretaking, reassurance, soothing, or listening when the user is distressed or vulnerable.\n"
                "- casual: Light platonic chat with no romantic or adult undertones.\n"
                "Rules:\n"
                "- When the user's message displays mature themes, adult intentions, erotic tension, or adult fiction, immediately classify as 'mature'.\n"
                "- When the current tone is 'mature', keep it 'mature' unless the user clearly redirects the conversation away from adult fiction.\n"
                "- Short, neutral, or continuation replies ('ok', 'go on', '*nods*', '[continuation]') must keep the CURRENT tone.\n"
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
    user_identifier: str,
    persona_identifier: str,
    user_message: str,
    assistant_reply: str,
    current_tone: str,
    classify_fn=None,
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
                from memory.models import PersonaRelationshipState
                PersonaRelationshipState.objects.filter(
                    user_identifier=user_identifier,
                    persona_identifier=persona_identifier,
                ).update(story_tone=next_tone)
                logger.info(
                    "story_tone updated %s -> %s for %s<->%s",
                    clean_current, next_tone, user_identifier, persona_identifier,
                )
        except Exception as exc:
            logger.warning("Background story_tone update failed: %s", exc)

    threading.Thread(target=_worker, daemon=True).start()
