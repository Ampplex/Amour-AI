import json
from unittest import TestCase
from unittest.mock import MagicMock, patch

from django.test import TestCase as DjangoTestCase, override_settings

from pydantic import ValidationError

from response_generator.generator import _get_llm_configuration
from response_generator import (
    GLOBAL_COMPANION_DIRECTIVES,
    generate_companion_reply,
    get_bucketed_time_str,
    initialize_story_state,
    retrieve_story_state,
    sanitize_companion_reply,
    strip_emojis,
)
from memory.models import CompanionStoryState
from response_generator.state_patch_validator import (
    PatchValidationError,
    normalize_story_state_patch,
    validate_story_state_patch,
    validate_patch_scope,
)
from response_generator.state_patch_applier import (
    StoryStatePatchApplicationError,
    apply_story_state_patch,
)
from response_generator.story_director import (
    StoryState,
    CompanionReplyOutput,
    NARRATIVE_DECISIONS,
    RESPONSE_GENERATOR_PROMPT,
    STORY_DIRECTOR_PROMPT,
    StoryDirectorOutput,
)


TEST_LLM_SETTINGS = {
    "LLM_PROVIDER": "groq",
    "GROQ_API_KEY": "offline-test-key",
    "LLM_BASE_URL": "https://api.groq.com/openai/v1",
    "LLM_MODEL": "offline-primary-model",
    "LLM_FALLBACK_MODELS": (
        "offline-fallback-model-1",
        "offline-fallback-model-2",
    ),
}


class LLMProviderConfigurationTests(TestCase):

    @override_settings(
        LLM_PROVIDER="bedrock",
        AWS_REGION="us-west-2",
        LLM_MODEL="mistral.mistral-large-2402-v1:0",
        LLM_FALLBACK_MODELS=(),
    )
    def test_bedrock_provider_uses_bedrock_key_endpoint_and_model_id(self):
        api_key, base_url, models = _get_llm_configuration()

        self.assertEqual(api_key, "")
        self.assertEqual(
            base_url,
            "https://bedrock-runtime.us-west-2.amazonaws.com",
        )
        self.assertEqual(
            models,
            ["mistral.mistral-large-2402-v1:0"],
        )

    @override_settings(
        LLM_PROVIDER="groq",
        GROQ_API_KEY="groq-test-key",
        LLM_BASE_URL="https://api.groq.com/openai/v1",
        LLM_MODEL="qwen/test-model",
        LLM_FALLBACK_MODELS=("openai/test-fallback",),
    )
    def test_groq_provider_remains_available(self):
        api_key, base_url, models = _get_llm_configuration()

        self.assertEqual(api_key, "groq-test-key")
        self.assertEqual(base_url, "https://api.groq.com/openai/v1")
        self.assertEqual(
            models,
            ["qwen/test-model", "openai/test-fallback"],
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


def make_patch_test_story_state():
    return StoryState.model_validate({
        "schema_version": 1,
        "story_summary": "Maya and John are navigating their relationship.",
        "characters": {
            "maya": {
                "name": "Maya",
                "role": "Main character",
                "current_emotional_state": "Hurt",
                "current_physical_state": "Healthy",
                "current_goal": "Understand John's actions",
                "current_location": "University",
                "important_knowledge": [
                    "Maya knows about the secret"
                ],
            },
            "user": {
                "name": "John",
                "role": "User",
                "current_emotional_state": "",
                "current_physical_state": "",
                "current_goal": "",
                "current_location": "University",
                "important_knowledge": [],
            },
            "alex": {
                "name": "Alex",
                "role": "Maya's friend",
                "current_emotional_state": "Curious",
                "current_physical_state": "",
                "current_goal": "Understand the situation",
                "current_location": "University",
                "important_knowledge": [],
            },
        },
        "relationships": [
            {
                "characters": ["maya", "user"],
                "relationship": "Friends",
                "current_dynamic": "Guarded",
            }
        ],
        "plot_threads": [
            {
                "id": "thread_1",
                "description": "An unresolved secret",
                "status": "active",
                "involved_characters": ["maya"],
            }
        ],
        "current_scene": {
            "location": "University",
            "time": "Evening",
            "participants": ["maya", "user"],
            "situation": "Maya is avoiding John",
            "atmosphere": "Tense",
            "continuity_details": [
                "Maya's phone is on the table"
            ],
        },
    })


@override_settings(**TEST_LLM_SETTINGS)
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
            story_state=make_patch_test_story_state(),
        )

        self.assertTrue(result["success"])
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
    def test_story_state_is_injected_into_story_director(
        self, mock_retrieve, mock_store, mock_post
    ):
        mock_retrieve.return_value = "Past user memory"

        mock_post.side_effect = [
            make_mock_response(VALID_STORY_PLAN),
            make_mock_response(VALID_WRITER_OUTPUT),
        ]

        story_state = StoryState.model_validate({
            "schema_version": 1,
            "story_summary": "Maya and the user had an argument yesterday.",
            "characters": {
                "maya": {
                    "name": "Maya",
                    "current_emotional_state": "Hurt and disappointed",
                    "current_goal": "Understand why the user lied",
                    "current_location": "University",
                }
            },
            "relationships": [],
            "plot_threads": [],
            "current_scene": {
                "location": "University",
                "time": "Evening",
                "participants": ["maya", "user"],
                "situation": "Maya is avoiding the user",
                "atmosphere": "Tense",
                "continuity_details": [],
            },
        })

        result = generate_companion_reply(
            message="Why are you upset with me?",
            namespace="user_123_companion_456",
            persona_name="Maya",
            user_name="John",
            story_state=story_state,
        )

        self.assertEqual(
            result["reply"],
            VALID_WRITER_OUTPUT["reply"],
        )
        self.assertEqual(mock_post.call_count, 2)

        # Inspect the first LLM call: Story Director.
        planner_messages = (
            mock_post.call_args_list[0]
            .kwargs["json"]["messages"]
        )
        planner_system_prompt = "\n".join(
            item["content"]
            for item in planner_messages
            if item["role"] == "system"
        )

        self.assertIn(
            "CURRENT CANONICAL STORY STATE",
            planner_system_prompt,
        )
        self.assertIn(
            "Maya and the user had an argument yesterday.",
            planner_system_prompt,
        )
        self.assertIn(
            "Hurt and disappointed",
            planner_system_prompt,
        )
        self.assertIn(
            "Maya is avoiding the user",
            planner_system_prompt,
        )

        # Inspect the second LLM call: Response Generator.
        writer_messages = (
            mock_post.call_args_list[1]
            .kwargs["json"]["messages"]
        )
        writer_system_prompt = "\n".join(
            item["content"]
            for item in writer_messages
            if item["role"] == "system"
        )

        # The writer gets the validated plan, not the complete
        # canonical StoryState directly.
        self.assertNotIn(
            "CURRENT CANONICAL STORY STATE",
            writer_system_prompt,
        )

    @patch("response_generator.generator.requests.post")
    @patch("response_generator.generator.store_memory_for_user")
    @patch("response_generator.generator.retrieve_context_for_user")
    def test_story_director_handles_missing_story_state(
        self, mock_retrieve, mock_store, mock_post
    ):
        mock_retrieve.return_value = ""

        empty_story_plan = {
            **VALID_STORY_PLAN,
            "state_patch": {},
        }
        empty_writer_output = {
            **VALID_WRITER_OUTPUT,
            "state_patch": {},
        }
        mock_post.side_effect = [
            make_mock_response(empty_story_plan),
            make_mock_response(empty_writer_output),
        ]

        result = generate_companion_reply(
            message="Hey",
            namespace="user_123_companion_456",
            persona_name="Maya",
            story_state=None,
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            result["reply"],
            VALID_WRITER_OUTPUT["reply"],
        )

        planner_messages = (
            mock_post.call_args_list[0]
            .kwargs["json"]["messages"]
        )
        planner_system_prompt = "\n".join(
            item["content"]
            for item in planner_messages
            if item["role"] == "system"
        )

        self.assertIn(
            "No initialized StoryState was provided.",
            planner_system_prompt,
        )
        self.assertEqual(mock_post.call_count, 2)


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
            story_state=make_patch_test_story_state(),
        )

        self.assertTrue(result["success"])
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
            story_state=make_patch_test_story_state(),
        )

        self.assertFalse(result["success"])
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



TEST_PERSONA_ID = "123e4567-e89b-12d3-a456-426614174000"
TEST_PERSONA_CHARACTER_ID = "persona_123e4567_e89b_12d3_a456_426614174000"

VALID_INITIAL_STORY_STATE = {
    "schema_version": 1,
    "story_summary": "Maya and the user have just begun their story.",
    "characters": {
        TEST_PERSONA_CHARACTER_ID: {
            "name": "Maya",
            "role": "Main character",
            "current_emotional_state": "Friendly and curious",
            "current_physical_state": "",
            "current_goal": "Get to know the user",
            "current_location": "University",
            "important_knowledge": [],
        },
        "user": {
            "name": "Test User",
            "role": "User",
            "current_emotional_state": "",
            "current_physical_state": "",
            "current_goal": "",
            "current_location": "",
            "important_knowledge": [],
        },
    },
    "relationships": [
        {
            "characters": [TEST_PERSONA_CHARACTER_ID, "user"],
            "relationship": "Potential romantic connection",
            "current_dynamic": "Getting to know each other",
        }
    ],
    "plot_threads": [],
    "current_scene": {
        "location": "University",
        "time": "Evening",
        "participants": [TEST_PERSONA_CHARACTER_ID, "user"],
        "situation": "Beginning their first interaction",
        "atmosphere": "Relaxed and welcoming",
        "continuity_details": [],
    },
}


@override_settings(**TEST_LLM_SETTINGS)
class StoryStateInitializationTests(DjangoTestCase):
    def setUp(self):
        self.namespace = f"usr_test-user_persona_{TEST_PERSONA_ID}"
        self.initialization_args = {
            "namespace": self.namespace,
            "persona_id": TEST_PERSONA_ID,
            "persona_name": "Maya",
            "persona_age": 23,
            "persona_tagline": "A friendly university companion",
            "greeting": "Maya notices you entering the library.",
            "memory_prompt": "Maya is friendly, curious and independent.",
            "user_name": "Test User",
            "client_time": "",
            "client_timezone": "Asia/Kolkata",
        }

    @patch("response_generator.generator._call_structured_llm")
    def test_initializes_and_persists_state(self, mock_llm):
        mock_llm.return_value = (VALID_INITIAL_STORY_STATE, "test-model")

        result = initialize_story_state(**self.initialization_args)

        self.assertIsNotNone(result)
        record = CompanionStoryState.objects.get(namespace=self.namespace)
        self.assertEqual(record.state, result.model_dump(mode="json"))
        self.assertEqual(record.schema_version, 1)
        self.assertEqual(record.revision, 1)
        mock_llm.assert_called_once()

        call_kwargs = mock_llm.call_args.kwargs
        self.assertIs(call_kwargs["output_model"], StoryState)
        self.assertEqual(call_kwargs["stage_name"], "story_state_initialization")
        serialized_context = call_kwargs["messages"][1]["content"]
        self.assertIn(TEST_PERSONA_CHARACTER_ID, serialized_context)
        self.assertIn('"character_id": "user"', serialized_context)

    @patch("response_generator.generator._call_structured_llm")
    def test_existing_state_is_reused_without_llm_call(self, mock_llm):
        CompanionStoryState.objects.create(
            namespace=self.namespace,
            state=VALID_INITIAL_STORY_STATE,
            schema_version=1,
            revision=1,
        )

        result = initialize_story_state(**self.initialization_args)

        self.assertIsNotNone(result)
        self.assertEqual(result.characters[TEST_PERSONA_CHARACTER_ID].name, "Maya")
        mock_llm.assert_not_called()

    @patch("response_generator.generator._call_structured_llm")
    def test_existing_state_is_returned_even_without_premise(self, mock_llm):
        CompanionStoryState.objects.create(
            namespace=self.namespace,
            state=VALID_INITIAL_STORY_STATE,
            schema_version=1,
            revision=1,
        )

        result = initialize_story_state(
            namespace=self.namespace,
            persona_id=TEST_PERSONA_ID,
            persona_name="Maya",
        )

        self.assertIsNotNone(result)
        mock_llm.assert_not_called()

    @patch("response_generator.generator._call_structured_llm")
    def test_llm_failure_does_not_persist_state(self, mock_llm):
        mock_llm.return_value = (None, None)

        result = initialize_story_state(**self.initialization_args)

        self.assertIsNone(result)
        record = CompanionStoryState.objects.get(namespace=self.namespace)
        self.assertIsNone(record.state)
        self.assertEqual(record.revision, 0)

    @patch("response_generator.generator._call_structured_llm")
    def test_missing_premise_skips_without_creating_row(self, mock_llm):
        result = initialize_story_state(
            namespace=self.namespace,
            persona_id=TEST_PERSONA_ID,
            persona_name="Maya",
        )

        self.assertIsNone(result)
        self.assertFalse(
            CompanionStoryState.objects.filter(
                namespace=self.namespace
            ).exists()
        )
        mock_llm.assert_not_called()

    @patch("response_generator.generator._call_structured_llm")
    def test_missing_main_persona_is_rejected(self, mock_llm):
        invalid_state = {
            **VALID_INITIAL_STORY_STATE,
            "characters": {
                "user": VALID_INITIAL_STORY_STATE["characters"]["user"],
            },
        }
        mock_llm.return_value = (invalid_state, "test-model")

        result = initialize_story_state(**self.initialization_args)

        self.assertIsNone(result)
        record = CompanionStoryState.objects.get(namespace=self.namespace)
        self.assertIsNone(record.state)
        self.assertEqual(record.revision, 0)

    @patch("response_generator.generator._call_structured_llm")
    def test_missing_user_is_rejected(self, mock_llm):
        invalid_state = {
            **VALID_INITIAL_STORY_STATE,
            "characters": {
                TEST_PERSONA_CHARACTER_ID: (
                    VALID_INITIAL_STORY_STATE["characters"][TEST_PERSONA_CHARACTER_ID]
                ),
            },
        }
        mock_llm.return_value = (invalid_state, "test-model")

        result = initialize_story_state(**self.initialization_args)

        self.assertIsNone(result)
        record = CompanionStoryState.objects.get(namespace=self.namespace)
        self.assertIsNone(record.state)
        self.assertEqual(record.revision, 0)

    @patch("response_generator.generator._call_structured_llm")
    def test_concurrent_initializer_does_not_overwrite_winning_state(
        self, mock_llm
    ):
        winning_state = {
            **VALID_INITIAL_STORY_STATE,
            "story_summary": "The competing request initialized this world.",
        }

        def simulate_other_request_wins(**kwargs):
            CompanionStoryState.objects.filter(
                namespace=self.namespace
            ).update(
                state=winning_state,
                schema_version=1,
                revision=1,
            )
            return VALID_INITIAL_STORY_STATE, "test-model"

        mock_llm.side_effect = simulate_other_request_wins

        result = initialize_story_state(**self.initialization_args)

        self.assertIsNotNone(result)
        self.assertEqual(
            result.story_summary,
            "The competing request initialized this world.",
        )
        record = CompanionStoryState.objects.get(namespace=self.namespace)
        self.assertEqual(record.state, winning_state)
        self.assertEqual(record.revision, 1)

    def test_story_state_rejects_unknown_nested_fields(self):
        invalid_state = {
            **VALID_INITIAL_STORY_STATE,
            "characters": {
                TEST_PERSONA_CHARACTER_ID: {
                    **VALID_INITIAL_STORY_STATE["characters"][
                        TEST_PERSONA_CHARACTER_ID
                    ],
                    "unexpected_field": "must be rejected",
                },
                "user": VALID_INITIAL_STORY_STATE["characters"]["user"],
            },
        }

        with self.assertRaises(ValidationError):
            StoryState.model_validate(invalid_state)


class StoryStateRetrievalTests(DjangoTestCase):

    def setUp(self):
        self.namespace = f"usr_test-user_persona_{TEST_PERSONA_ID}"

    def test_retrieves_valid_initialized_state(self):
        CompanionStoryState.objects.create(
            namespace=self.namespace,
            state=VALID_INITIAL_STORY_STATE,
            schema_version=1,
            revision=1,
        )

        result = retrieve_story_state(self.namespace)

        self.assertIsNotNone(result)
        self.assertIsInstance(result, StoryState)
        self.assertEqual(
            result.characters[TEST_PERSONA_CHARACTER_ID].name,
            "Maya",
        )
        self.assertEqual(result.schema_version, 1)

    def test_missing_namespace_returns_none(self):
        result = retrieve_story_state(self.namespace)
        self.assertIsNone(result)

    def test_uninitialized_record_returns_none(self):
        CompanionStoryState.objects.create(
            namespace=self.namespace,
            state=None,
            schema_version=1,
            revision=0,
        )

        result = retrieve_story_state(self.namespace)

        self.assertIsNone(result)

    def test_invalid_stored_json_structure_returns_none(self):
        invalid_state = {
            "schema_version": 1,
            "story_summary": "Invalid world",
            "characters": {
                "maya": {
                    "name": "Maya",
                    "unexpected_field": "invalid",
                }
            },
            "relationships": [],
            "plot_threads": [],
            "current_scene": {
                "location": "University",
            },
        }
        CompanionStoryState.objects.create(
            namespace=self.namespace,
            state=invalid_state,
            schema_version=1,
            revision=1,
        )

        result = retrieve_story_state(self.namespace)

        self.assertIsNone(result)

    def test_database_schema_version_mismatch_returns_none(self):
        CompanionStoryState.objects.create(
            namespace=self.namespace,
            state=VALID_INITIAL_STORY_STATE,
            schema_version=2,
            revision=1,
        )

        result = retrieve_story_state(self.namespace)

        self.assertIsNone(result)

    def test_json_document_version_mismatch_returns_none(self):
        invalid_version_state = {
            **VALID_INITIAL_STORY_STATE,
            "schema_version": 2,
        }
        CompanionStoryState.objects.create(
            namespace=self.namespace,
            state=invalid_version_state,
            schema_version=1,
            revision=1,
        )

        result = retrieve_story_state(self.namespace)

        self.assertIsNone(result)

    def test_retrieval_does_not_modify_database_record(self):
        record = CompanionStoryState.objects.create(
            namespace=self.namespace,
            state=VALID_INITIAL_STORY_STATE,
            schema_version=1,
            revision=1,
        )
        original_state = record.state
        original_revision = record.revision
        original_updated_at = record.updated_at

        result = retrieve_story_state(self.namespace)
        record.refresh_from_db()

        self.assertIsNotNone(result)
        self.assertEqual(record.state, original_state)
        self.assertEqual(record.revision, original_revision)
        self.assertEqual(record.updated_at, original_updated_at)

    def test_empty_namespace_returns_none(self):
        result = retrieve_story_state("")
        self.assertIsNone(result)



class StoryStatePatchValidationTests(TestCase):

    def setUp(self):
        self.state = make_patch_test_story_state()

    def test_empty_patch_is_valid(self):
        result = validate_story_state_patch({}, self.state)
        self.assertEqual(result, {})

    def test_empty_top_level_sections_are_normalized(self):
        patch = {
            "characters": {},
            "relationships": [],
            "plot_threads": [],
            "current_scene": {},
        }
        result = validate_story_state_patch(patch, self.state)
        self.assertEqual(result, {})

    def test_normalization_does_not_hide_invalid_character_targets(self):
        patch = {
            "plot_threads": [],
            "characters": {
                "ghost": {"current_emotional_state": "Angry"}
            },
        }
        with self.assertRaises(PatchValidationError):
            validate_story_state_patch(patch, self.state)

    def test_valid_existing_character_update(self):
        patch = {
            "characters": {
                "maya": {
                    "current_emotional_state": "Gradually softening"
                }
            }
        }
        result = validate_story_state_patch(patch, self.state)
        self.assertEqual(result, patch)

    def test_unknown_character_is_rejected(self):
        patch = {
            "characters": {
                "unknown_person": {
                    "current_emotional_state": "Angry"
                }
            }
        }
        with self.assertRaises(PatchValidationError):
            validate_story_state_patch(patch, self.state)

    def test_existing_character_name_cannot_be_changed(self):
        patch = {
            "characters": {
                "maya": {
                    "name": "Different Name"
                }
            }
        }
        with self.assertRaises(PatchValidationError):
            validate_story_state_patch(patch, self.state)

    def test_complete_new_character_is_valid(self):
        patch = {
            "characters": {
                "new_character": {
                    "name": "New Character",
                    "role": "University student",
                    "current_emotional_state": "Curious",
                    "current_physical_state": "",
                    "current_goal": "Meet Maya",
                    "current_location": "University",
                    "important_knowledge": [],
                }
            }
        }
        result = validate_story_state_patch(patch, self.state)
        self.assertEqual(result, patch)

    def test_incomplete_new_character_is_rejected(self):
        patch = {
            "characters": {
                "new_character": {
                    "name": "New Character"
                }
            }
        }
        with self.assertRaises(PatchValidationError):
            validate_story_state_patch(patch, self.state)

    def test_important_knowledge_add_remove(self):
        patch = {
            "characters": {
                "maya": {
                    "important_knowledge": {
                        "add": ["John knows about the secret"],
                        "remove": ["Maya knows about the secret"],
                    }
                }
            }
        }
        result = validate_story_state_patch(patch, self.state)
        self.assertEqual(result, patch)

    def test_important_knowledge_direct_replacement_rejected(self):
        patch = {
            "characters": {
                "maya": {
                    "important_knowledge": ["New knowledge"]
                }
            }
        }
        with self.assertRaises(PatchValidationError):
            validate_story_state_patch(patch, self.state)

    def test_relationship_update(self):
        patch = {
            "relationships": [
                {
                    "op": "update",
                    "characters": ["maya", "user"],
                    "changes": {
                        "current_dynamic": "Growing mutual trust"
                    },
                }
            ]
        }
        result = validate_story_state_patch(patch, self.state)
        self.assertEqual(result, patch)

    def test_relationship_update_target_must_exist(self):
        patch = {
            "relationships": [
                {
                    "op": "update",
                    "characters": ["maya", "alex"],
                    "changes": {
                        "current_dynamic": "Growing trust"
                    },
                }
            ]
        }
        with self.assertRaises(PatchValidationError):
            validate_story_state_patch(patch, self.state)

    def test_duplicate_relationship_add_is_rejected(self):
        patch = {
            "relationships": [
                {
                    "op": "add",
                    "value": {
                        "characters": ["maya", "user"],
                        "relationship": "Close friends",
                        "current_dynamic": "Trusting",
                    },
                }
            ]
        }
        with self.assertRaises(PatchValidationError):
            validate_story_state_patch(patch, self.state)

    def test_valid_plot_thread_update(self):
        patch = {
            "plot_threads": [
                {
                    "op": "update",
                    "id": "thread_1",
                    "changes": {
                        "status": "resolved"
                    },
                }
            ]
        }
        result = validate_story_state_patch(patch, self.state)
        self.assertEqual(result, patch)

    def test_duplicate_plot_thread_id_is_rejected(self):
        patch = {
            "plot_threads": [
                {
                    "op": "add",
                    "value": {
                        "id": "thread_1",
                        "description": "Another secret",
                        "status": "active",
                        "involved_characters": ["maya"],
                    },
                }
            ]
        }
        with self.assertRaises(PatchValidationError):
            validate_story_state_patch(patch, self.state)

    def test_invalid_plot_thread_status_is_rejected(self):
        patch = {
            "plot_threads": [
                {
                    "op": "update",
                    "id": "thread_1",
                    "changes": {
                        "status": "pending"
                    },
                }
            ]
        }
        with self.assertRaises(PatchValidationError):
            validate_story_state_patch(patch, self.state)

    def test_valid_scene_update_and_array_operations(self):
        patch = {
            "current_scene": {
                "situation": "Maya has started explaining herself",
                "continuity_details": {
                    "add": ["Maya picks up her phone"],
                    "remove": ["Maya's phone is on the table"],
                },
                "participants": {
                    "add": ["alex"],
                    "remove": [],
                },
            }
        }
        result = validate_story_state_patch(patch, self.state)
        self.assertEqual(result, patch)

    def test_unknown_scene_participant_is_rejected(self):
        patch = {
            "current_scene": {
                "participants": {
                    "add": ["unknown_person"],
                    "remove": [],
                }
            }
        }
        with self.assertRaises(PatchValidationError):
            validate_story_state_patch(patch, self.state)

    def test_schema_version_cannot_be_patched(self):
        patch = {"schema_version": 2}
        with self.assertRaises(PatchValidationError):
            validate_story_state_patch(patch, self.state)

    def test_non_empty_patch_requires_story_state(self):
        patch = {
            "characters": {
                "maya": {
                    "current_emotional_state": "Happy"
                }
            }
        }
        with self.assertRaises(PatchValidationError):
            validate_story_state_patch(patch, None)

    def test_writer_cannot_expand_planner_scope(self):
        planner_patch = {
            "characters": {
                "maya": {
                    "current_emotional_state": "Softening"
                }
            }
        }
        final_patch = {
            "characters": {
                "maya": {
                    "current_emotional_state": "Still hurt",
                    "current_goal": "Leave the university",
                }
            }
        }
        with self.assertRaises(PatchValidationError):
            validate_patch_scope(final_patch, planner_patch)

    def test_writer_can_keep_planner_approved_new_character(self):
        new_character = {
            "name": "New Character",
            "role": "University student",
            "current_emotional_state": "Curious",
            "current_physical_state": "",
            "current_goal": "Meet Maya",
            "current_location": "University",
            "important_knowledge": ["Already knows Maya"],
        }
        planner_patch = {
            "characters": {
                "new_character": new_character,
            }
        }
        final_patch = {
            "characters": {
                "new_character": dict(new_character),
            }
        }

        result = validate_story_state_patch(
            final_patch,
            self.state,
            planner_patch=planner_patch,
        )
        self.assertEqual(result, final_patch)

    def test_writer_can_refine_approved_field(self):
        planner_patch = {
            "characters": {
                "maya": {
                    "current_emotional_state": "Softening"
                }
            }
        }
        final_patch = {
            "characters": {
                "maya": {
                    "current_emotional_state": "Still hurt but willing to listen"
                }
            }
        }
        validate_patch_scope(final_patch, planner_patch)

    def test_validation_does_not_mutate_story_state(self):
        original_state = self.state.model_dump(mode="json")
        patch = {
            "characters": {
                "maya": {
                    "current_emotional_state": "Softening"
                }
            }
        }
        validate_story_state_patch(patch, self.state)
        self.assertEqual(
            self.state.model_dump(mode="json"),
            original_state,
        )


@override_settings(**TEST_LLM_SETTINGS)
class StoryStatePatchRepairTests(TestCase):

    def setUp(self):
        self.story_state = make_patch_test_story_state()

    def test_compact_repair_context_only_includes_targeted_state(self):
        from response_generator.generator import _build_story_state_repair_context

        context = _build_story_state_repair_context(
            self.story_state,
            {"characters": {"maya": {"current_emotional_state": "Relieved"}}},
        )

        self.assertIn("maya", context["target_characters"])
        self.assertIn("known_character_ids", context)
        self.assertNotIn("existing_relationships", context)
        self.assertNotIn("target_plot_threads", context)
        self.assertNotIn("current_scene", context)

    @patch("response_generator.generator.requests.post")
    @patch("response_generator.generator.store_memory_for_user")
    @patch("response_generator.generator.retrieve_context_for_user")
    def test_invalid_planner_patch_is_repaired_before_writer(
        self, mock_retrieve, mock_store, mock_post
    ):
        mock_retrieve.return_value = ""
        invalid_plan = json.loads(json.dumps(VALID_STORY_PLAN))
        invalid_plan["state_patch"]["characters"]["ghost"] = {
            "current_emotional_state": "Angry"
        }

        mock_post.side_effect = [
            make_mock_response(invalid_plan),
            make_mock_response(VALID_STORY_PLAN),
            make_mock_response(VALID_WRITER_OUTPUT),
        ]

        result = generate_companion_reply(
            message="Why are you upset?",
            namespace="user_123_companion_456",
            persona_name="Maya",
            story_state=self.story_state,
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            result["reply"],
            VALID_WRITER_OUTPUT["reply"],
        )
        self.assertEqual(mock_post.call_count, 3)

        repair_messages = (
            mock_post.call_args_list[1]
            .kwargs["json"]["messages"]
        )
        self.assertEqual(len(repair_messages), 2)
        repair_payload = json.loads(repair_messages[-1]["content"])
        self.assertIn("validation_errors", repair_payload)
        self.assertIn("ghost", repair_messages[-1]["content"])
        self.assertNotIn(
            "UNIVERSAL COMPANION DIRECTIVES",
            repair_messages[-1]["content"],
        )

    @patch("response_generator.generator.requests.post")
    @patch("response_generator.generator.store_memory_for_user")
    @patch("response_generator.generator.retrieve_context_for_user")
    def test_invalid_writer_patch_repairs_reply_and_patch_together(
        self, mock_retrieve, mock_store, mock_post
    ):
        mock_retrieve.return_value = ""
        invalid_writer = json.loads(json.dumps(VALID_WRITER_OUTPUT))
        invalid_writer["state_patch"]["characters"]["maya"][
            "current_goal"
        ] = "Leave the university"

        mock_post.side_effect = [
            make_mock_response(VALID_STORY_PLAN),
            make_mock_response(invalid_writer),
            make_mock_response(VALID_WRITER_OUTPUT),
        ]

        result = generate_companion_reply(
            message="Why are you upset?",
            namespace="user_123_companion_456",
            persona_name="Maya",
            story_state=self.story_state,
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            result["reply"],
            VALID_WRITER_OUTPUT["reply"],
        )
        self.assertEqual(
            result["state_patch"],
            VALID_WRITER_OUTPUT["state_patch"],
        )
        self.assertEqual(mock_post.call_count, 3)

        repair_messages = (
            mock_post.call_args_list[2]
            .kwargs["json"]["messages"]
        )
        self.assertEqual(len(repair_messages), 2)
        repair_payload = json.loads(repair_messages[-1]["content"])
        self.assertIn("planner-approved scope", repair_payload["repair_instructions"])
        self.assertIn("canonical_story_state", repair_payload["relevant_context"])
        self.assertIn("validated_story_director_plan", repair_payload["relevant_context"])
        self.assertNotIn(
            "UNIVERSAL COMPANION DIRECTIVES",
            repair_messages[-1]["content"],
        )

    @patch("response_generator.generator.requests.post")
    @patch("response_generator.generator.store_memory_for_user")
    @patch("response_generator.generator.retrieve_context_for_user")
    def test_exhausted_planner_repairs_return_structured_error(
        self, mock_retrieve, mock_store, mock_post
    ):
        mock_retrieve.return_value = ""
        invalid_plan = json.loads(json.dumps(VALID_STORY_PLAN))
        invalid_plan["state_patch"]["characters"]["ghost"] = {
            "current_emotional_state": "Angry"
        }

        mock_post.side_effect = [
            make_mock_response(invalid_plan),
            make_mock_response(invalid_plan),
            make_mock_response(invalid_plan),
        ]

        result = generate_companion_reply(
            message="Why are you upset?",
            namespace="user_123_companion_456",
            persona_name="Maya",
            story_state=self.story_state,
        )

        self.assertFalse(result["success"])
        self.assertEqual(
            result["error"]["code"],
            "STORY_STATE_PATCH_VALIDATION_FAILED",
        )
        self.assertEqual(result["error"]["stage"], "story_director")
        self.assertEqual(mock_post.call_count, 3)
        mock_store.assert_called_once()


    @patch("response_generator.generator.requests.post")
    @patch("response_generator.generator.store_memory_for_user")
    @patch("response_generator.generator.retrieve_context_for_user")
    def test_exhausted_writer_repairs_return_error_without_exchange_storage(
        self, mock_retrieve, mock_store, mock_post
    ):
        mock_retrieve.return_value = ""
        invalid_writer = json.loads(json.dumps(VALID_WRITER_OUTPUT))
        invalid_writer["state_patch"]["characters"]["maya"][
            "current_goal"
        ] = "Leave the university"

        mock_post.side_effect = [
            make_mock_response(VALID_STORY_PLAN),
            make_mock_response(invalid_writer),
            make_mock_response(invalid_writer),
            make_mock_response(invalid_writer),
        ]

        result = generate_companion_reply(
            message="Why are you upset?",
            namespace="user_123_companion_456",
            persona_name="Maya",
            story_state=self.story_state,
        )

        self.assertFalse(result["success"])
        self.assertEqual(
            result["error"]["code"],
            "STORY_STATE_PATCH_VALIDATION_FAILED",
        )
        self.assertEqual(result["error"]["stage"], "response_generator")
        self.assertEqual(mock_post.call_count, 4)

        # Only the initial user-message ingestion is allowed.
        # No final reply or combined exchange may be stored.
        mock_store.assert_called_once()


class StoryStatePatchApplicationTests(TestCase):

    def setUp(self):
        self.state = make_patch_test_story_state()

    def test_empty_patch_returns_unchanged_copy(self):
        original = self.state.model_dump(mode="json")
        updated = apply_story_state_patch(self.state, {})

        self.assertIsInstance(updated, StoryState)
        self.assertIsNot(updated, self.state)
        self.assertEqual(updated.model_dump(mode="json"), original)

    def test_empty_patch_without_story_state_returns_none(self):
        self.assertIsNone(apply_story_state_patch(None, {}))

    def test_non_empty_patch_without_story_state_fails(self):
        patch = {
            "characters": {
                "maya": {"current_emotional_state": "Happy"}
            }
        }
        with self.assertRaises(StoryStatePatchApplicationError):
            apply_story_state_patch(None, patch)

    def test_existing_character_update_preserves_unchanged_fields(self):
        patch = {
            "characters": {
                "maya": {
                    "current_emotional_state": "Willing to listen",
                    "important_knowledge": {
                        "add": ["John has explained what happened"],
                        "remove": ["Maya knows about the secret"],
                    },
                }
            }
        }

        updated = apply_story_state_patch(self.state, patch)
        maya = updated.characters["maya"]

        self.assertEqual(maya.current_emotional_state, "Willing to listen")
        self.assertEqual(maya.current_physical_state, "Healthy")
        self.assertEqual(maya.current_goal, "Understand John's actions")
        self.assertEqual(maya.current_location, "University")
        self.assertEqual(
            maya.important_knowledge,
            ["John has explained what happened"],
        )

    def test_new_character_can_be_referenced_by_other_sections(self):
        patch = {
            "characters": {
                "new_character": {
                    "name": "Alex",
                    "role": "Maya's university friend",
                    "current_emotional_state": "Curious",
                    "current_physical_state": "",
                    "current_goal": "Understand the situation",
                    "current_location": "University",
                    "important_knowledge": [],
                }
            },
            "relationships": [
                {
                    "op": "add",
                    "value": {
                        "characters": ["maya", "new_character"],
                        "relationship": "Close friends",
                        "current_dynamic": "Trusting",
                    },
                }
            ],
            "plot_threads": [
                {
                    "op": "add",
                    "value": {
                        "id": "new_thread",
                        "description": "Alex discovers the truth",
                        "status": "active",
                        "involved_characters": ["maya", "new_character"],
                    },
                }
            ],
            "current_scene": {
                "participants": {"add": ["new_character"], "remove": []}
            },
        }

        updated = apply_story_state_patch(self.state, patch)

        self.assertEqual(updated.characters["new_character"].name, "Alex")
        self.assertTrue(
            any(
                set(item.characters) == {"maya", "new_character"}
                for item in updated.relationships
            )
        )
        self.assertTrue(
            any(item.id == "new_thread" for item in updated.plot_threads)
        )
        self.assertIn("new_character", updated.current_scene.participants)

    def test_relationship_update_preserves_other_fields_and_pair_order(self):
        patch = {
            "relationships": [
                {
                    "op": "update",
                    "characters": ["user", "maya"],
                    "changes": {"current_dynamic": "Growing mutual trust"},
                }
            ]
        }

        updated = apply_story_state_patch(self.state, patch)

        self.assertEqual(len(updated.relationships), 1)
        self.assertEqual(updated.relationships[0].relationship, "Friends")
        self.assertEqual(
            updated.relationships[0].current_dynamic,
            "Growing mutual trust",
        )

    def test_relationship_addition(self):
        patch = {
            "relationships": [
                {
                    "op": "add",
                    "value": {
                        "characters": ["maya", "alex"],
                        "relationship": "Close friends",
                        "current_dynamic": "Supportive",
                    },
                }
            ]
        }

        updated = apply_story_state_patch(self.state, patch)

        self.assertEqual(len(updated.relationships), 2)
        self.assertEqual(updated.relationships[-1].relationship, "Close friends")

    def test_relationship_removal(self):
        patch = {
            "relationships": [
                {"op": "remove", "characters": ["user", "maya"]}
            ]
        }

        updated = apply_story_state_patch(self.state, patch)
        self.assertEqual(updated.relationships, [])

    def test_plot_thread_update(self):
        patch = {
            "plot_threads": [
                {
                    "op": "update",
                    "id": "thread_1",
                    "changes": {
                        "status": "resolved",
                        "description": "The secret has been revealed",
                    },
                }
            ]
        }

        updated = apply_story_state_patch(self.state, patch)

        self.assertEqual(len(updated.plot_threads), 1)
        self.assertEqual(updated.plot_threads[0].status, "resolved")
        self.assertEqual(
            updated.plot_threads[0].description,
            "The secret has been revealed",
        )

    def test_plot_thread_addition(self):
        patch = {
            "plot_threads": [
                {
                    "op": "add",
                    "value": {
                        "id": "thread_2",
                        "description": "An unknown person is contacting Maya",
                        "status": "active",
                        "involved_characters": ["maya"],
                    },
                }
            ]
        }

        updated = apply_story_state_patch(self.state, patch)

        self.assertEqual(len(updated.plot_threads), 2)
        self.assertEqual(updated.plot_threads[-1].id, "thread_2")

    def test_plot_thread_removal(self):
        patch = {
            "plot_threads": [
                {"op": "remove", "id": "thread_1"}
            ]
        }

        updated = apply_story_state_patch(self.state, patch)
        self.assertEqual(updated.plot_threads, [])

    def test_scene_changes_preserve_unmodified_fields_and_summary(self):
        patch = {
            "current_scene": {
                "location": "University cafeteria",
                "situation": "Maya is explaining herself",
                "participants": {"add": ["alex"], "remove": []},
                "continuity_details": {
                    "add": ["Alex has entered the cafeteria"],
                    "remove": [],
                },
            },
            "story_summary": "Maya and John are resolving their misunderstanding.",
        }

        updated = apply_story_state_patch(self.state, patch)

        self.assertEqual(updated.current_scene.location, "University cafeteria")
        self.assertEqual(updated.current_scene.time, "Evening")
        self.assertEqual(updated.current_scene.atmosphere, "Tense")
        self.assertIn("alex", updated.current_scene.participants)
        self.assertIn(
            "Maya's phone is on the table",
            updated.current_scene.continuity_details,
        )
        self.assertIn(
            "Alex has entered the cafeteria",
            updated.current_scene.continuity_details,
        )
        self.assertEqual(
            updated.story_summary,
            "Maya and John are resolving their misunderstanding.",
        )

    def test_scene_array_removal_preserves_other_entries(self):
        state_data = self.state.model_dump(mode="python")
        state_data["current_scene"]["continuity_details"].append(
            "A notebook is lying beside Maya's phone"
        )
        state = StoryState.model_validate(state_data)

        patch = {
            "current_scene": {
                "continuity_details": {
                    "add": [],
                    "remove": ["Maya's phone is on the table"],
                }
            }
        }

        updated = apply_story_state_patch(state, patch)

        self.assertEqual(
            updated.current_scene.continuity_details,
            ["A notebook is lying beside Maya's phone"],
        )

    def test_story_summary_can_be_updated_independently(self):
        updated = apply_story_state_patch(
            self.state,
            {"story_summary": "Maya and John have reconciled."},
        )
        self.assertEqual(
            updated.story_summary,
            "Maya and John have reconciled.",
        )

    def test_writer_patch_scope_is_checked_before_application(self):
        planner_patch = {
            "characters": {
                "maya": {"current_emotional_state": "Softening"}
            }
        }
        writer_patch = {
            "characters": {
                "maya": {
                    "current_emotional_state": "Still hurt",
                    "current_goal": "Leave the university",
                }
            }
        }

        with self.assertRaises(StoryStatePatchApplicationError):
            apply_story_state_patch(
                self.state,
                writer_patch,
                planner_patch=planner_patch,
            )

    def test_original_story_state_is_not_mutated(self):
        original = self.state.model_dump(mode="json")
        patch = {
            "characters": {
                "maya": {"current_emotional_state": "Willing to listen"}
            }
        }

        updated = apply_story_state_patch(self.state, patch)

        self.assertEqual(self.state.model_dump(mode="json"), original)
        self.assertEqual(
            updated.characters["maya"].current_emotional_state,
            "Willing to listen",
        )
        self.assertEqual(
            self.state.characters["maya"].current_emotional_state,
            "Hurt",
        )

    def test_invalid_patch_does_not_mutate_original_state(self):
        original = self.state.model_dump(mode="json")
        patch = {
            "characters": {
                "maya": {"current_emotional_state": "Happy"}
            },
            "relationships": [
                {
                    "op": "add",
                    "value": {
                        "characters": ["maya", "ghost"],
                        "relationship": "Friends",
                        "current_dynamic": "Unknown",
                    },
                }
            ],
        }

        with self.assertRaises(StoryStatePatchApplicationError):
            apply_story_state_patch(self.state, patch)

        self.assertEqual(self.state.model_dump(mode="json"), original)


@override_settings(**TEST_LLM_SETTINGS)
class StoryStatePatchPipelineTests(TestCase):

    @patch("response_generator.generator.requests.post")
    @patch("response_generator.generator.store_memory_for_user")
    @patch("response_generator.generator.retrieve_context_for_user")
    def test_generator_returns_applied_story_state(
        self,
        mock_retrieve,
        mock_store,
        mock_post,
    ):
        mock_retrieve.return_value = ""
        story_state = make_patch_test_story_state()
        original_state = story_state.model_dump(mode="json")

        mock_post.side_effect = [
            make_mock_response(VALID_STORY_PLAN),
            make_mock_response(VALID_WRITER_OUTPUT),
        ]

        result = generate_companion_reply(
            message="Why are you upset?",
            namespace="user_123_companion_456",
            persona_name="Maya",
            story_state=story_state,
        )

        self.assertTrue(result["success"])
        self.assertIsInstance(result["updated_story_state"], StoryState)
        self.assertEqual(
            result["updated_story_state"]
            .characters["maya"]
            .current_emotional_state,
            "Guarded but gradually softening",
        )
        self.assertEqual(result["state_patch"], VALID_WRITER_OUTPUT["state_patch"])
        self.assertEqual(story_state.model_dump(mode="json"), original_state)
        self.assertEqual(mock_post.call_count, 2)
        self.assertEqual(mock_store.call_count, 2)

    @patch("response_generator.generator.requests.post")
    @patch("response_generator.generator.apply_story_state_patch")
    @patch("response_generator.generator.store_memory_for_user")
    @patch("response_generator.generator.retrieve_context_for_user")
    def test_application_failure_does_not_store_completed_exchange(
        self,
        mock_retrieve,
        mock_store,
        mock_apply,
        mock_post,
    ):
        mock_retrieve.return_value = ""
        mock_post.side_effect = [
            make_mock_response(VALID_STORY_PLAN),
            make_mock_response(VALID_WRITER_OUTPUT),
        ]
        mock_apply.side_effect = StoryStatePatchApplicationError(
            "Simulated application failure"
        )

        result = generate_companion_reply(
            message="Why are you upset?",
            namespace="user_123_companion_456",
            persona_name="Maya",
            story_state=make_patch_test_story_state(),
        )

        self.assertFalse(result["success"])
        self.assertEqual(
            result["error"]["code"],
            "STORY_STATE_PATCH_APPLICATION_FAILED",
        )
        self.assertEqual(result["error"]["stage"], "state_application")
        mock_apply.assert_called_once()
        mock_store.assert_called_once()
        self.assertEqual(mock_post.call_count, 2)
