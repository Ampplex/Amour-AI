import json
from unittest import TestCase
from unittest.mock import MagicMock, patch

from pydantic import ValidationError

from response_generator import (
    GLOBAL_COMPANION_DIRECTIVES,
    generate_companion_reply,
    get_bucketed_time_str,
    sanitize_companion_reply,
    strip_emojis,
)
from response_generator.story_director import (
    CompanionReplyOutput,
    NARRATIVE_DECISIONS,
    RESPONSE_GENERATOR_PROMPT,
    STORY_DIRECTOR_PROMPT,
    StoryDirectorOutput,
)


VALID_STORY_PLAN = {
    "decision": "RELATIONSHIP_DEVELOPMENT",
    "focus": "maya",
    "next_beat": {
        "event": None,
        "narrative_development": "Maya gradually becomes more comfortable.",
        "character_actions": [
            "Maya moves closer.",
            "She briefly maintains eye contact.",
        ],
        "emotional_direction": "Guarded but softening",
        "dialogue_direction": "More emotionally vulnerable",
    },
    "scene_direction": {
        "atmosphere": "Quiet evening",
        "physical_details": ["Maya sits closer to the user."],
    },
    "state_patch": {
        "characters": {
            "maya": {
                "current_emotional_state": "Guarded but gradually softening"
            }
        }
    },
}


VALID_WRITER_OUTPUT = {
    "reply": (
        "She looks at you for a moment before moving closer. "
        "I guess I don't mind having you around."
    ),
    "conflict_stage": 2,
    "state_patch": {
        "characters": {
            "maya": {
                "current_emotional_state": "Guarded but gradually softening"
            }
        }
    },
}


def make_mock_response(payload, status_code=200):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = {
        "choices": [{"message": {"content": json.dumps(payload)}}],
        "usage": {"prompt_tokens": 50, "completion_tokens": 20},
    }
    response.text = ""
    return response


class ResponseGeneratorUnitTests(TestCase):
    def test_strip_emojis(self):
        sample = "Hello! ❤️ 😊 Have a great day! 🔥"
        cleaned = strip_emojis(sample)
        self.assertNotIn("❤️", cleaned)
        self.assertNotIn("😊", cleaned)
        self.assertNotIn("🔥", cleaned)
        self.assertEqual(" ".join(cleaned.split()), "Hello! Have a great day!")

    def test_sanitize_companion_reply(self):
        text = "Hey! ```python\nprint('secret')\n``` (no emojis) How are you?"
        cleaned = sanitize_companion_reply(text)
        self.assertNotIn("```", cleaned)
        self.assertNotIn("no emojis", cleaned)
        self.assertIn("Hey!", cleaned)
        self.assertIn("How are you?", cleaned)

    def test_get_bucketed_time_str(self):
        bucketed = get_bucketed_time_str()
        self.assertTrue(bucketed)
        self.assertTrue(":00" in bucketed or ":30" in bucketed)

    @patch("response_generator.generator.requests.post")
    @patch("response_generator.generator.store_memory_for_user")
    @patch("response_generator.generator.retrieve_context_for_user")
    def test_two_stage_handoff_and_combined_reeve_storage(
        self, mock_retrieve, mock_store, mock_post
    ):
        mock_retrieve.return_value = "Past user memory"
        mock_post.side_effect = [
            make_mock_response(VALID_STORY_PLAN),
            make_mock_response(VALID_WRITER_OUTPUT),
        ]

        result = generate_companion_reply(
            message="Hey, are you free tonight?",
            namespace="user_123_companion_456",
            persona_name="Aria",
            user_name="John Doe",
            conversation_history=[
                {"role": "user", "content": "We met yesterday."},
                {"role": "assistant", "content": "I remember."},
            ],
            user_key="user-123",
        )

        self.assertEqual(result["reply"], VALID_WRITER_OUTPUT["reply"])
        self.assertEqual(result["conflict_stage"], 2)
        self.assertEqual(result["decision"], "RELATIONSHIP_DEVELOPMENT")
        self.assertEqual(result["focus"], "maya")
        self.assertEqual(result["next_beat"], VALID_STORY_PLAN["next_beat"])
        self.assertEqual(result["scene_direction"], VALID_STORY_PLAN["scene_direction"])
        self.assertEqual(result["planner_state_patch"], VALID_STORY_PLAN["state_patch"])
        self.assertEqual(result["state_patch"], VALID_WRITER_OUTPUT["state_patch"])
        self.assertEqual(result["namespace"], "user_123_companion_456")
        self.assertEqual(result["context"], "Past user memory")
        self.assertEqual(mock_post.call_count, 2)

        # Verify that the complete plan and original context reach the writer.
        writer_messages = mock_post.call_args_list[1].kwargs["json"]["messages"]
        writer_system_prompt = "\n".join(
            item["content"] for item in writer_messages if item["role"] == "system"
        )
        self.assertIn(RESPONSE_GENERATOR_PROMPT, writer_system_prompt)
        self.assertIn("RELATIONSHIP_DEVELOPMENT", writer_system_prompt)
        self.assertIn("Maya gradually becomes more comfortable.", writer_system_prompt)
        self.assertIn("scene_direction", writer_system_prompt)
        self.assertIn("Past user memory", writer_system_prompt)
        self.assertIn("PERSONA IDENTITY", writer_system_prompt)
        self.assertIn(GLOBAL_COMPANION_DIRECTIVES, writer_system_prompt)
        self.assertIn("We met yesterday.", [m["content"] for m in writer_messages])
        self.assertIn("Hey, are you free tonight?", [m["content"] for m in writer_messages])

        # The user message is ingested for retrieval, and the complete
        # user + final assistant exchange is stored after generation.
        mock_store.assert_any_call(
            "User (John): Hey, are you free tonight?",
            "user_123_companion_456",
            user_key="user-123",
        )
        mock_store.assert_any_call(
            "User: Hey, are you free tonight?\nAssistant: "
            + VALID_WRITER_OUTPUT["reply"],
            "user_123_companion_456",
            user_key="user-123",
        )

    @patch("response_generator.generator.requests.post")
    @patch("response_generator.generator.store_memory_for_user")
    @patch("response_generator.generator.retrieve_context_for_user")
    def test_planner_validation_failover_then_writer(
        self, mock_retrieve, mock_store, mock_post
    ):
        mock_retrieve.return_value = ""
        mock_post.side_effect = [
            make_mock_response({"reply": "not a plan"}),
            make_mock_response(VALID_STORY_PLAN),
            make_mock_response(VALID_WRITER_OUTPUT),
        ]

        result = generate_companion_reply(
            message="Hi",
            namespace="user_123_companion_456",
            persona_name="Aria",
        )

        self.assertEqual(result["reply"], VALID_WRITER_OUTPUT["reply"])
        self.assertEqual(mock_post.call_count, 3)

    @patch("response_generator.generator.requests.post")
    @patch("response_generator.generator.store_memory_for_user")
    @patch("response_generator.generator.retrieve_context_for_user")
    def test_planner_failure_does_not_call_writer(
        self, mock_retrieve, mock_store, mock_post
    ):
        mock_retrieve.return_value = ""
        mock_post.side_effect = [
            make_mock_response({"reply": "invalid"}),
            make_mock_response({"reply": "still invalid"}),
            make_mock_response({"reply": "invalid again"}),
        ]

        result = generate_companion_reply(
            message="Hi",
            namespace="user_123_companion_456",
            persona_name="Aria",
        )

        self.assertEqual(result["reply"], "")
        self.assertEqual(mock_post.call_count, 3)
        mock_store.assert_called_once()

    @patch("response_generator.generator.requests.post")
    @patch("response_generator.generator.store_memory_for_user")
    @patch("response_generator.generator.retrieve_context_for_user")
    def test_writer_failure_does_not_fabricate_reply(
        self, mock_retrieve, mock_store, mock_post
    ):
        mock_retrieve.return_value = ""
        mock_post.side_effect = [
            make_mock_response(VALID_STORY_PLAN),
            make_mock_response({"reply": "invalid"}),
            make_mock_response({"reply": "invalid"}),
            make_mock_response({"reply": "invalid"}),
        ]

        result = generate_companion_reply(
            message="Hi",
            namespace="user_123_companion_456",
            persona_name="Aria",
        )

        self.assertEqual(result["reply"], "")
        self.assertEqual(result["decision"], VALID_STORY_PLAN["decision"])
        self.assertEqual(mock_post.call_count, 4)


class StructuredOutputTests(TestCase):
    def setUp(self):
        self.valid_plan = dict(VALID_STORY_PLAN)
        self.valid_writer = dict(VALID_WRITER_OUTPUT)

    def test_valid_story_plan(self):
        output = StoryDirectorOutput.model_validate(self.valid_plan)
        self.assertEqual(output.decision, "RELATIONSHIP_DEVELOPMENT")

    def test_all_narrative_decisions_are_valid(self):
        for decision in NARRATIVE_DECISIONS:
            plan = {**self.valid_plan, "decision": decision}
            self.assertEqual(
                StoryDirectorOutput.model_validate(plan).decision,
                decision,
            )

    def test_invalid_decision_raises(self):
        plan = {**self.valid_plan, "decision": "INVALID_DECISION"}
        with self.assertRaises(ValidationError):
            StoryDirectorOutput.model_validate(plan)

    def test_planner_missing_fields_and_extra_fields_raise(self):
        for field in ("next_beat", "scene_direction", "state_patch"):
            incomplete = {k: v for k, v in self.valid_plan.items() if k != field}
            with self.subTest(field=field), self.assertRaises(ValidationError):
                StoryDirectorOutput.model_validate(incomplete)

        extra = {**self.valid_plan, "unexpected": True}
        with self.assertRaises(ValidationError):
            StoryDirectorOutput.model_validate(extra)

    def test_valid_writer_output(self):
        output = CompanionReplyOutput.model_validate(self.valid_writer)
        self.assertEqual(output.reply, VALID_WRITER_OUTPUT["reply"])

    def test_writer_invalid_outputs_raise(self):
        cases = [
            {**self.valid_writer, "reply": ""},
            {**self.valid_writer, "conflict_stage": 4},
            {**self.valid_writer, "unexpected": True},
            {k: v for k, v in self.valid_writer.items() if k != "state_patch"},
        ]
        for payload in cases:
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                CompanionReplyOutput.model_validate(payload)
