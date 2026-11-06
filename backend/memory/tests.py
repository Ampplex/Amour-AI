from django.test import SimpleTestCase

from .chat_service import normalize_history_turns
from .llm_client import normalize_bedrock_messages
from .narrative_service import format_narrative_state_for_prompt
from .reeve_service import should_ingest_into_reeve, should_retrieve_from_reeve
from .views import build_reeve_namespace


class ConversationContinuityTests(SimpleTestCase):
    def test_history_accepts_canonical_and_legacy_shapes(self):
        history = [
            {"sender": "user", "text": "Hey"},
            {"sender": "bot", "text": "The party is loud."},
            {"role": "user", "content": "Wow"},
            {"role": "assistant", "content": "I look over."},
        ]
        self.assertEqual(
            normalize_history_turns(history),
            [
                {"sender": "user", "text": "Hey"},
                {"sender": "bot", "text": "The party is loud."},
                {"sender": "user", "text": "Wow"},
                {"sender": "bot", "text": "I look over."},
            ],
        )

    def test_unknown_sender_is_not_misclassified_as_user(self):
        self.assertEqual(
            normalize_history_turns([{"sender": "system", "text": "ignore"}]),
            [],
        )

    def test_repeated_message_text_can_be_a_new_turn(self):
        history = normalize_history_turns([{"sender": "user", "text": "Hey"}])
        history.append({"sender": "user", "text": "Hey"})
        self.assertEqual(len(history), 2)

    def test_bedrock_assistant_first_history_uses_neutral_marker(self):
        messages = normalize_bedrock_messages(
            [
                {"sender": "bot", "text": "Opening greeting already delivered."},
                {"sender": "user", "text": "Hey"},
            ],
            persona_name="Elijah",
        )
        self.assertEqual([message["role"] for message in messages], ["user", "assistant", "user"])
        marker = messages[0]["content"][0]["text"]
        self.assertIn("already underway", marker)
        self.assertNotIn("Scene begins", marker)

    def test_bedrock_merges_consecutive_messages_of_same_role(self):
        messages = normalize_bedrock_messages(
            [
                {"sender": "user", "text": "First"},
                {"sender": "user", "text": "Second"},
                {"sender": "bot", "text": "Reply"},
            ]
        )
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "user")
        self.assertIn("First", messages[0]["content"][0]["text"])
        self.assertIn("Second", messages[0]["content"][0]["text"])

    def test_retrieval_skips_fillers_and_accepts_recall_questions(self):
        for message in ("Hey", "Wow", "OK", "Hellloooo"):
            self.assertFalse(should_retrieve_from_reeve(message))
        self.assertTrue(should_retrieve_from_reeve("Remember our trip to Paris?"))
        self.assertTrue(should_retrieve_from_reeve("What happened to your sister?"))
        self.assertFalse(should_ingest_into_reeve("Remember our trip to Paris?"))

    def test_namespace_is_consistent(self):
        self.assertEqual(
            build_reeve_namespace("user:1", "persona/2"),
            "usr_user_1_persona_persona_2",
        )

    def test_narrative_state_labels_recent_events_as_history(self):
        prompt = format_narrative_state_for_prompt(
            {
                "current_scene": {"location": "Cafe", "situation": "Having coffee"},
                "recent_events": [{"summary": "Arrived at the station"}],
                "characters": [
                    {
                        "name": "Mina",
                        "personality_summary": "Blunt but loyal",
                        "independent_goals": ["Find a new apartment"],
                        "current_activity": "Looking at listings",
                    }
                ],
            }
        )
        self.assertIn("active", prompt.lower())
        self.assertIn("historical", prompt.lower())
        self.assertIn("Arrived at the station", prompt)
        self.assertIn("Looking at listings", prompt)
