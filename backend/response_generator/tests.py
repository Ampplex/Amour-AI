import json
from unittest import TestCase
from unittest.mock import patch, MagicMock

from response_generator import (
    generate_companion_reply,
    sanitize_companion_reply,
    strip_emojis,
    get_bucketed_time_str,
    GLOBAL_COMPANION_DIRECTIVES,
)


class ResponseGeneratorUnitTests(TestCase):
    def test_strip_emojis(self):
        sample = "Hello! ❤️ 😊 Have a great day! 🔥"
        cleaned = strip_emojis(sample)
        self.assertNotIn("❤️", cleaned)
        self.assertNotIn("😊", cleaned)
        self.assertNotIn("🔥", cleaned)
        self.assertEqual(" ".join(cleaned.split()), "Hello! Have a great day!")

    def test_sanitize_companion_reply(self):
        text_with_fences = "Hey! ```python\nprint('secret')\n``` (no emojis) How are you?"
        cleaned = sanitize_companion_reply(text_with_fences)
        self.assertNotIn("```", cleaned)
        self.assertNotIn("no emojis", cleaned)
        self.assertIn("Hey!", cleaned)
        self.assertIn("How are you?", cleaned)

    def test_get_bucketed_time_str(self):
        bucketed = get_bucketed_time_str()
        self.assertTrue(len(bucketed) > 0)
        self.assertTrue(":00" in bucketed or ":30" in bucketed)

    @patch("response_generator.generator.requests.post")
    @patch("response_generator.generator.store_memory_for_user")
    @patch("response_generator.generator.retrieve_context_for_user")
    def test_generate_companion_reply_success(
        self, mock_retrieve, mock_store, mock_post
    ):
        mock_retrieve.return_value = "Past user memory"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {"reply": "I missed you today.", "conflict_stage": 0}
                        )
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 10,
                "prompt_time": 0.05,
                "completion_time": 0.02,
            },
        }
        mock_post.return_value = mock_resp

        result = generate_companion_reply(
            message="Hey, are you free tonight?",
            namespace="user_123_companion_456",
            persona_name="Aria",
            user_name="John Doe",
        )

        self.assertEqual(result["reply"], "I missed you today.")
        self.assertEqual(result["conflict_stage"], 0)
        self.assertEqual(result["namespace"], "user_123_companion_456")
        self.assertEqual(result["context"], "Past user memory")
        # Check that user message was stored
        mock_store.assert_any_call("User (John): Hey, are you free tonight?", "user_123_companion_456", user_key=None)
        # Check that assistant reply was stored
        mock_store.assert_any_call("Assistant: I missed you today.", "user_123_companion_456", user_key=None)
