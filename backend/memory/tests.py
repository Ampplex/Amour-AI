from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import CompanionStoryState


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
