"""
Pure LLM-driven tone classification powered by Amazon Bedrock (Mistral Large).

No hardcoded regex or keyword matching.
Classifies user intent dynamically and keeps Qwen exclusively for chat generation.
"""

import logging
import os

logger = logging.getLogger("amour.tone_tracker")

VALID_TONES = {"default", "casual", "comfort", "mature"}


def _call_bedrock_converse(messages: list, max_tokens: int = 8, temperature: float = 0.1) -> str:
    """Call Bedrock Converse API with connection timeouts for fast classification."""
    import boto3
    from botocore.config import Config
    from django.conf import settings

    region = (
        getattr(settings, "AWS_REGION", "")
        or os.environ.get("AWS_REGION", "us-west-2")
    ).strip()
    model_id = (
        getattr(settings, "BEDROCK_SMALL_MODEL_ID", "")
        or os.environ.get("BEDROCK_SMALL_MODEL_ID", "")
        or getattr(settings, "BEDROCK_CLASSIFIER_MODEL_ID", "")
        or os.environ.get("BEDROCK_CLASSIFIER_MODEL_ID", "meta.llama3-1-8b-instruct-v1:0")
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

    boto_config = Config(
        connect_timeout=3,
        read_timeout=4,
        retries={"max_attempts": 1},
    )
    client = boto3.client("bedrock-runtime", region_name=region, config=boto_config)
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


def classify_tone_with_bedrock(
    user_message: str,
    current_tone: str = "default",
    classify_fn=None,
) -> str:
    """
    Pure LLM-driven tone classification using Amazon Bedrock.
    Classifies user message intent into: default, casual, comfort, or mature.
    Zero hardcoded regex or keyword matching.
    """
    clean_current = (current_tone or "default").strip().lower()
    if clean_current not in VALID_TONES:
        clean_current = "default"

    if not user_message or not isinstance(user_message, str) or not user_message.strip():
        return clean_current

    if classify_fn is None:
        classify_fn = _call_bedrock_converse

    prompt = [
        {
            "role": "system",
            "content": (
                "You are an expert story tone classifier for an AI companion roleplay.\n"
                "Allowed tones: default, casual, comfort, mature.\n"
                "Definitions:\n"
                "- mature: Any adult fiction, erotic/sensual tension, physical intimacy, sexual passion, or mature intentions from the user.\n"
                "- comfort: Emotional support, caretaking, reassurance, soothing, or listening when the user is sad, tired, or distressed.\n"
                "- casual: Everyday light platonic chat with no romantic or adult undertones.\n"
                "- default: Adaptive general roleplay, romantic banter, and everyday pacing.\n"
                "Rules:\n"
                "1. If the user's message displays mature themes, adult intentions, erotic tension, or adult fiction, immediately classify as 'mature'.\n"
                "2. When current tone is 'mature', keep it 'mature' unless the user clearly redirects the conversation away from adult fiction.\n"
                "3. Short, neutral, or continuation replies ('ok', 'go on', '*nods*') must keep the CURRENT tone.\n"
                "4. Reply with ONLY one word from: default, casual, comfort, mature."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Current tone: {clean_current}\n"
                f"User message: {user_message.strip()}\n"
                "Tone:"
            ),
        },
    ]

    try:
        raw = (classify_fn(prompt, max_tokens=8, temperature=0.1) or "").strip().lower().strip(".,\"'")
        if raw in VALID_TONES:
            return raw
    except Exception as exc:
        logger.warning("Bedrock tone classification failed, falling back to current tone: %s", exc)

    return clean_current
