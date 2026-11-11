from datetime import timedelta
from unittest.mock import patch
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .crypto import encrypt_chat_message
from .models import CompanionStoryState, Persona, PersonaChatMessage
from response_generator.story_director import StoryState


class CompanionStoryStateModelTests(TestCase):
    def setUp(self):
        self.namespace = "usr_test-user_persona_test-persona"

    def test_state_can_be_empty_before_initialization(self):
        record = CompanionStoryState.objects.create(
            namespace=self.namespace
        )

        persisted = CompanionStoryState.objects.get(
            namespace=self.namespace
        )

        self.assertIsNone(persisted.state)
        self.assertEqual(persisted.schema_version, 1)
        self.assertEqual(persisted.revision, 0)
        self.assertEqual(record.pk, persisted.pk)

    def test_persists_complete_story_state_json_document(self):
        state = {
            "schema_version": 1,
            "story_summary": "Maya and the user are rebuilding trust.",
            "characters": {
                "maya": {
                    "name": "Maya",
                    "role": "Main character",
                    "current_emotional_state": "Guarded but softening",
                    "current_physical_state": "Sitting on the sofa",
                    "current_goal": "Understand the user's intentions",
                    "current_location": "Living room",
                    "important_knowledge": [
                        "The user apologized for their argument"
                    ],
                }
            },
            "relationships": [
                {
                    "characters": ["maya", "user"],
                    "relationship": "Romantic partners",
                    "current_dynamic": "Rebuilding trust",
                }
            ],
            "plot_threads": [],
            "current_scene": {
                "location": "Living room",
                "time": "Evening",
                "participants": ["maya", "user"],
                "situation": "Having a conversation",
                "atmosphere": "Quiet and intimate",
                "continuity_details": ["Maya is sitting beside the user"],
            },
        }

        CompanionStoryState.objects.create(
            namespace=self.namespace,
            state=state,
            schema_version=state["schema_version"],
            revision=12,
        )

        persisted = CompanionStoryState.objects.get(
            namespace=self.namespace
        )

        self.assertEqual(persisted.state, state)
        self.assertEqual(persisted.schema_version, 1)
        self.assertEqual(persisted.revision, 12)

    def test_namespace_is_unique(self):
        CompanionStoryState.objects.create(
            namespace=self.namespace
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CompanionStoryState.objects.create(
                    namespace=self.namespace
                )

    def test_string_representation_uses_namespace(self):
        record = CompanionStoryState.objects.create(
            namespace=self.namespace
        )

        self.assertEqual(
            str(record),
            f"StoryState: {self.namespace}",
        )


VALID_STORY_STATE = {
    "schema_version": 1,
    "story_summary": "Maya and the user are having a friendly conversation.",
    "characters": {
        "maya": {
            "name": "Maya",
            "role": "Main character",
            "current_emotional_state": "Welcoming",
            "current_physical_state": "Sitting in the library",
            "current_goal": "Study art history",
            "current_location": "University Library",
            "important_knowledge": [],
        },
        "user": {
            "name": "User",
            "role": "User",
            "current_emotional_state": "Curious",
            "current_physical_state": "Standing nearby",
            "current_goal": "Chat with Maya",
            "current_location": "University Library",
            "important_knowledge": [],
        },
    },
    "relationships": [
        {
            "characters": ["maya", "user"],
            "relationship": "Friends",
            "current_dynamic": "Getting acquainted",
        }
    ],
    "plot_threads": [],
    "current_scene": {
        "location": "University Library",
        "time": "Afternoon",
        "participants": ["maya", "user"],
        "situation": "Meeting for study",
        "atmosphere": "Quiet and calm",
        "continuity_details": [],
    },
}


class ChatMemoryEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.persona = Persona.objects.create(
            name="Maya",
            tagline="Art student",
            greeting="Hello there!",
            memory_prompt="Maya is an art student.",
        )
        self.user_id = "test-user-123"
        self.clean_user_id = self.user_id.replace(":", "_").replace("/", "_")
        self.clean_persona_id = str(self.persona.id).replace(":", "_").replace("/", "_")
        self.namespace = f"usr_{self.clean_user_id}_persona_{self.clean_persona_id}"

        self.initial_story_state = StoryState.model_validate(VALID_STORY_STATE)
        CompanionStoryState.objects.create(
            namespace=self.namespace,
            state=self.initial_story_state.model_dump(mode="json"),
            schema_version=1,
            revision=1,
        )

    @patch("memory.views.generate_companion_reply")
    def test_successful_api_response_contains_metadata(self, mock_reply):
        updated_data = self.initial_story_state.model_dump(mode="json")
        updated_data["characters"]["maya"]["current_emotional_state"] = "Pleased"
        updated_state = StoryState.model_validate(updated_data)

        mock_reply.return_value = {
            "success": True,
            "reply": "It's so great to see you again!",
            "conflict_stage": 0,
            "decision": "CONTINUE",
            "updated_story_state": updated_state,
            "context": "Context memories",
        }

        payload = {
            "message": "Hi Maya, how are you?",
            "client_message_id": "msg-uuid-001",
            "persona_id": str(self.persona.id),
            "user_id": self.user_id,
        }

        response = self.client.post("/api/memory/chat/", payload, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertIn("metadata", response.data)
        metadata = response.data["metadata"]
        self.assertEqual(metadata["narrative_decision"], "CONTINUE")
        self.assertIn("story_state", metadata)
        self.assertTrue(metadata["story_state"]["available"])
        self.assertEqual(metadata["story_state"]["schema_version"], 1)
        self.assertEqual(metadata["story_state"]["revision"], 2)
        self.assertTrue(metadata["story_state"]["updated"])

        # Verify PostgreSQL state was updated
        db_state = CompanionStoryState.objects.get(namespace=self.namespace)
        self.assertEqual(db_state.revision, 2)
        self.assertEqual(
            db_state.state["characters"]["maya"]["current_emotional_state"],
            "Pleased",
        )

    @patch("memory.views.generate_companion_reply")
    def test_bot_message_persists_response_metadata_and_client_message_id(self, mock_reply):
        mock_reply.return_value = {
            "success": True,
            "reply": "I love painting landscapes.",
            "conflict_stage": 0,
            "decision": "CHARACTER_DEVELOPMENT",
            "updated_story_state": self.initial_story_state,
            "context": "",
        }

        payload = {
            "message": "What do you like painting?",
            "client_message_id": "msg-uuid-002",
            "persona_id": str(self.persona.id),
            "user_id": self.user_id,
        }

        response = self.client.post("/api/memory/chat/", payload, format="json")
        self.assertEqual(response.status_code, 200)

        bot_msg = PersonaChatMessage.objects.filter(sender="bot").first()
        self.assertIsNotNone(bot_msg)
        self.assertEqual(bot_msg.client_message_id, "msg-uuid-002")
        self.assertIn("narrative_decision", bot_msg.response_metadata)
        self.assertEqual(bot_msg.response_metadata["narrative_decision"], "CHARACTER_DEVELOPMENT")
        self.assertEqual(bot_msg.response_metadata["story_state"]["revision"], 1)
        self.assertFalse(bot_msg.response_metadata["story_state"]["updated"])

    @patch("memory.views.store_memory_for_user")
    @patch("memory.views.generate_companion_reply")
    def test_combined_exchange_is_stored_after_postgres_commit(
        self, mock_reply, mock_store_memory
    ):
        mock_reply.return_value = {
            "success": True,
            "reply": "Maya checks her phone and smiles.",
            "conflict_stage": 0,
            "decision": "CHARACTER_DEVELOPMENT",
            "focus": "maya",
            "next_beat": {
                "event": "Maya receives a message",
                "character_actions": ["Maya checks her phone"],
            },
            "scene_direction": {"staging": "At the cafe table"},
            "planner_state_patch": {},
            "state_patch": {},
            "updated_story_state": self.initial_story_state,
            "context": "",
        }

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            response = self.client.post(
                "/api/memory/chat/",
                {
                    "message": "How is your project going?",
                    "client_message_id": "post-commit-memory-001",
                    "persona_id": str(self.persona.id),
                    "user_id": self.user_id,
                },
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(mock_store_memory.called)
        self.assertEqual(len(callbacks), 1)
        self.assertFalse(
            mock_reply.call_args.kwargs["persist_exchange_to_memory"]
        )

        callbacks[0]()
        mock_store_memory.assert_called_once_with(
            "User: How is your project going?\nAssistant: Maya checks her phone and smiles.",
            self.namespace,
            user_key=None,
        )

    @patch("memory.views.generate_companion_reply")
    def test_get_chat_history_includes_response_metadata(self, mock_reply):
        mock_reply.return_value = {
            "success": True,
            "reply": "Good morning!",
            "conflict_stage": 0,
            "decision": "CONTINUE",
            "updated_story_state": self.initial_story_state,
            "context": "",
        }

        # Send a message to create history
        self.client.post("/api/memory/chat/", {
            "message": "Good morning!",
            "client_message_id": "msg-history-001",
            "persona_id": str(self.persona.id),
            "user_id": self.user_id,
        }, format="json")

        # GET chat history
        response = self.client.get(f"/api/memory/chat/?persona_id={self.persona.id}&user_id={self.user_id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("results", response.data)
        self.assertGreaterEqual(len(response.data["results"]), 2)

        bot_result = [r for r in response.data["results"] if r["sender"] == "bot"][0]
        self.assertIn("response_metadata", bot_result)
        self.assertIn("story_state", bot_result["response_metadata"])

    @patch("memory.views.generate_companion_reply")
    def test_chat_generation_receives_recent_question_and_short_answer(self, mock_reply):
        mock_reply.return_value = {
            "success": True,
            "reply": "Fair enough. Want to talk about something else?",
            "conflict_stage": 0,
            "decision": "CONTINUE",
            "updated_story_state": self.initial_story_state,
            "context": "",
        }
        prior_messages = [
            ("user", "Doraemon"),
            ("bot", "What books are you reading?"),
            ("user", "I was reading Doraemon."),
            ("bot", "What did you like about it?"),
            ("user", "Nothing."),
            ("bot", "Oh, really? What did you like about it?"),
        ]
        base_time = timezone.now() - timedelta(minutes=1)
        records = [
            PersonaChatMessage.objects.create(
                user_identifier=self.user_id,
                persona_identifier=str(self.persona.id),
                namespace=self.namespace,
                sender=sender,
                text=encrypt_chat_message(text, user_id=self.user_id),
            )
            for sender, text in prior_messages
        ]
        for offset, record in enumerate(records):
            PersonaChatMessage.objects.filter(pk=record.pk).update(
                created_at=base_time + timedelta(seconds=offset)
            )

        response = self.client.post(
            "/api/memory/chat/",
            {
                "message": "I liked nothing.",
                "client_message_id": "short-answer-follow-up-001",
                "persona_id": str(self.persona.id),
                "user_id": self.user_id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        history = mock_reply.call_args.kwargs["conversation_history"]
        self.assertEqual(
            history,
            [
                {"role": sender if sender == "user" else "assistant", "content": text}
                for sender, text in prior_messages
            ],
        )
        self.assertEqual(
            mock_reply.call_args.kwargs["message"],
            "I liked nothing.",
        )

    @patch("memory.views.generate_companion_reply")
    def test_idempotent_replay_returns_decrypted_reply_and_saved_metadata(self, mock_reply):
        mock_reply.return_value = {
            "success": True,
            "reply": "This is an idempotent test reply.",
            "conflict_stage": 0,
            "decision": "CONTINUE",
            "updated_story_state": self.initial_story_state,
            "context": "",
        }

        payload = {
            "message": "Hello!",
            "client_message_id": "idempotent-uuid-001",
            "persona_id": str(self.persona.id),
            "user_id": self.user_id,
        }

        first_resp = self.client.post("/api/memory/chat/", payload, format="json")
        self.assertEqual(first_resp.status_code, 200)
        self.assertEqual(mock_reply.call_count, 1)

        # Send second request with identical client_message_id
        second_resp = self.client.post("/api/memory/chat/", payload, format="json")
        self.assertEqual(second_resp.status_code, 200)
        # LLM was NOT called a second time
        self.assertEqual(mock_reply.call_count, 1)
        self.assertEqual(second_resp.data["reply"], "This is an idempotent test reply.")
        self.assertEqual(second_resp.data["client_message_id"], "idempotent-uuid-001")
        self.assertIn("metadata", second_resp.data)
        self.assertEqual(second_resp.data["metadata"]["narrative_decision"], "CONTINUE")

    @patch("memory.views.generate_companion_reply")
    def test_different_user_same_request_id_cannot_replay(self, mock_reply):
        # Seed canonical states for both namespaces so this API test never
        # invokes the real LLM-backed StoryState initializer.
        for user_id in ("user-A", "user-B"):
            namespace = (
                f"usr_{user_id.replace(':', '_').replace('/', '_')}_"
                f"persona_{self.clean_persona_id}"
            )
            CompanionStoryState.objects.create(
                namespace=namespace,
                state=self.initial_story_state.model_dump(mode="json"),
                schema_version=1,
                revision=1,
            )

        mock_reply.return_value = {
            "success": True,
            "reply": "Reply for User A",
            "conflict_stage": 0,
            "decision": "CONTINUE",
            "updated_story_state": self.initial_story_state,
            "context": "",
        }

        self.client.post(
            "/api/memory/chat/",
            {
                "message": "Msg from user A",
                "client_message_id": "shared-uuid-001",
                "persona_id": str(self.persona.id),
                "user_id": "user-A",
            },
            format="json",
        )

        mock_reply.return_value = {
            "success": True,
            "reply": "Reply for User B",
            "conflict_stage": 0,
            "decision": "CONTINUE",
            "updated_story_state": self.initial_story_state,
            "context": "",
        }
        response = self.client.post(
            "/api/memory/chat/",
            {
                "message": "Msg from user B",
                "client_message_id": "shared-uuid-001",
                "persona_id": str(self.persona.id),
                "user_id": "user-B",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["reply"], "Reply for User B")


    def test_incomplete_chat_turn_returns_409_and_prevents_duplicate_user_message(self):
        # User message was saved, but bot message never finished
        from memory.crypto import encrypt_chat_message
        encrypted_text = encrypt_chat_message("Incomplete turn text", user_id=self.user_id)
        PersonaChatMessage.objects.create(
            user_identifier=self.user_id,
            persona_identifier=str(self.persona.id),
            namespace=self.namespace,
            sender="user",
            text=encrypted_text,
            client_message_id="incomplete-uuid-001",
        )

        initial_count = PersonaChatMessage.objects.filter(user_identifier=self.user_id).count()

        # Retry with same client_message_id
        resp = self.client.post("/api/memory/chat/", {
            "message": "Incomplete turn text",
            "client_message_id": "incomplete-uuid-001",
            "persona_id": str(self.persona.id),
            "user_id": self.user_id,
        }, format="json")

        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.data.get("code"), "INCOMPLETE_CHAT_TURN")
        # Ensure no duplicate user message was inserted
        final_count = PersonaChatMessage.objects.filter(user_identifier=self.user_id).count()
        self.assertEqual(initial_count, final_count)

    @patch("memory.views.generate_companion_reply")
    def test_public_response_contract_does_not_expose_raw_patches_or_full_story_state(self, mock_reply):
        mock_reply.return_value = {
            "success": True,
            "reply": "Testing public contract.",
            "conflict_stage": 0,
            "decision": "CONTINUE",
            "focus": "maya",
            "next_beat": {"beat": "details"},
            "scene_direction": {"direction": "details"},
            "planner_state_patch": {"patch": "details"},
            "state_patch": {"patch": "details"},
            "updated_story_state": self.initial_story_state,
            "context": "",
        }

        resp = self.client.post("/api/memory/chat/", {
            "message": "Hi!",
            "client_message_id": "contract-test-001",
            "persona_id": str(self.persona.id),
            "user_id": self.user_id,
        }, format="json")

        self.assertEqual(resp.status_code, 200)
        # Verify internal fields are NOT exposed in public response
        self.assertNotIn("next_beat", resp.data)
        self.assertNotIn("scene_direction", resp.data)
        self.assertNotIn("planner_state_patch", resp.data)
        self.assertNotIn("state_patch", resp.data)
        self.assertNotIn("characters", resp.data)
        self.assertNotIn("characters", resp.data["metadata"])
