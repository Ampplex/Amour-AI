import json
from unittest import TestCase
from unittest.mock import patch, MagicMock

from pydantic import ValidationError
from response_generator import (
    generate_companion_reply,
    sanitize_companion_reply,
    strip_emojis,
    get_bucketed_time_str,
    GLOBAL_COMPANION_DIRECTIVES,
)
from response_generator.story_director import (
    CompanionResponseOutput,
    NARRATIVE_DECISIONS,
    STORY_DIRECTOR_PROMPT,
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
                            {
                                "reply": "I missed you today.",
                                "conflict_stage": 0,
                                "decision": "CONTINUE",
                                "focus": None,
                                "next_beat": {
                                    "event": None,
                                    "narrative_development": "Continue conversation",
                                    "character_actions": [],
                                    "emotional_direction": "Warm",
                                    "dialogue_direction": "Casual greeting",
                                },
                                "scene_direction": {},
                                "state_patch": {},
                            }
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
        self.assertEqual(result["decision"], "CONTINUE")
        self.assertEqual(result["namespace"], "user_123_companion_456")
        self.assertEqual(result["context"], "Past user memory")
        # Check that user message was stored
        mock_store.assert_any_call("User (John): Hey, are you free tonight?", "user_123_companion_456", user_key=None)
        # Check that assistant reply was stored
        mock_store.assert_any_call("Assistant: I missed you today.", "user_123_companion_456", user_key=None)

        # Verify Story Director instructions are included
        self.assertEqual(mock_post.call_count, 1)
        request_payload = mock_post.call_args.kwargs["json"]
        system_prompt = request_payload["messages"][0]["content"]
        self.assertIn(STORY_DIRECTOR_PROMPT, system_prompt)
        self.assertIn(
            "No initialized StoryState was provided.",
            system_prompt,
        )
        # Verify existing context is preserved
        self.assertIn("Past user memory", system_prompt)
        self.assertIn("PERSONA IDENTITY", system_prompt)
        self.assertIn(
            GLOBAL_COMPANION_DIRECTIVES,
            system_prompt,
        )

    @patch("response_generator.generator.requests.post")
    @patch("response_generator.generator.store_memory_for_user")
    @patch("response_generator.generator.retrieve_context_for_user")
    def test_generate_companion_reply_validation_failover(
        self, mock_retrieve, mock_store, mock_post
    ):
        mock_retrieve.return_value = ""
        # First model returns invalid output (missing required keys)
        resp_invalid = MagicMock()
        resp_invalid.status_code = 200
        resp_invalid.json.return_value = {
            "choices": [{"message": {"content": json.dumps({"reply": "hi"})}}],
            "usage": {},
        }
        # Second model returns valid 7-key output
        resp_valid = MagicMock()
        resp_valid.status_code = 200
        resp_valid.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "reply": "Hello there!",
                                "conflict_stage": 1,
                                "decision": "CONTINUE",
                                "focus": None,
                                "next_beat": {
                                    "event": None,
                                    "narrative_development": "Keep chatting",
                                    "character_actions": [],
                                    "emotional_direction": "Calm",
                                    "dialogue_direction": "Friendly",
                                },
                                "scene_direction": {},
                                "state_patch": {},
                            }
                        )
                    }
                }
            ],
            "usage": {},
        }
        mock_post.side_effect = [resp_invalid, resp_valid]

        result = generate_companion_reply(
            message="Hi",
            namespace="user_123_companion_456",
            persona_name="Aria",
        )

        self.assertEqual(result["reply"], "Hello there!")
        self.assertEqual(result["conflict_stage"], 1)
        self.assertEqual(result["decision"], "CONTINUE")
        self.assertEqual(mock_post.call_count, 2)


class StructuredOutputTests(TestCase):
    def setUp(self):
        self.valid_output = {
            "reply": "Maya looks away nervously.",
            "conflict_stage": 0,
            "decision": "CHARACTER_DEVELOPMENT",
            "focus": "maya",
            "next_beat": {
                "event": None,
                "narrative_development": "Maya becomes hesitant.",
                "character_actions": ["Avoids eye contact"],
                "emotional_direction": "Anxious",
                "dialogue_direction": "Respond cautiously",
            },
            "scene_direction": {},
            "state_patch": {},
        }

    def test_valid_output(self):
        result = CompanionResponseOutput.model_validate(
            self.valid_output
        )
        self.assertEqual(
            result.decision,
            "CHARACTER_DEVELOPMENT",
        )

    def test_all_narrative_decisions_are_valid(self):
        for decision in NARRATIVE_DECISIONS:
            output = {
                **self.valid_output,
                "decision": decision,
            }
            result = CompanionResponseOutput.model_validate(output)
            self.assertEqual(result.decision, decision)

    def test_invalid_decision_raises(self):
        output = {**self.valid_output, "decision": "INVALID_DECISION"}
        with self.assertRaises(ValidationError):
            CompanionResponseOutput.model_validate(output)

    def test_extra_keys_forbidden(self):
        output = {**self.valid_output, "extra_key": "forbidden"}
        with self.assertRaises(ValidationError):
            CompanionResponseOutput.model_validate(output)

    def test_missing_required_keys_raises(self):
        incomplete = {k: v for k, v in self.valid_output.items() if k != "reply"}
        with self.assertRaises(ValidationError):
            CompanionResponseOutput.model_validate(incomplete)
