"""
Opt-in integration tests that exercise the real configured LLM.

These tests intentionally do NOT mock requests.post. They call the same
Story Director -> Response Generator -> Feature 5 validation/repair ->
Feature 6 application pipeline used by a real chat turn.

Only Reeve storage and retrieval are replaced so the suite does not write to
or depend on an external memory service. This module uses unittest.TestCase
and does not require a Django test database.

Run explicitly:

    AMOUR_RUN_LIVE_LLM_TESTS=1 python manage.py test \
      --settings=amour_backend.live_test_settings \
      response_generator.tests_live_llm.LiveChatEndpointLLMIntegrationTests

The regular deterministic suite does not make paid LLM calls.
"""

import os
import re
import unittest
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase as DjangoTestCase
from rest_framework.test import APIClient

from memory.crypto import decrypt_chat_message
from memory.models import CompanionStoryState, Persona, PersonaChatMessage
from response_generator import generator as response_generator_module
from response_generator.generator import generate_companion_reply
from response_generator.state_patch_validator import validate_story_state_patch
from response_generator.story_director import StoryState


def make_live_llm_story_state() -> StoryState:
    """Build a realistic, isolated world for live model scenarios."""
    return StoryState.model_validate(
        {
            "schema_version": 1,
            "story_summary": (
                "Maya and John are close friends working through a recent "
                "disagreement. An unresolved mystery concerns anonymous "
                "messages Maya has been receiving."
            ),
            "characters": {
                "maya": {
                    "name": "Maya",
                    "role": "John's companion and close friend",
                    "current_emotional_state": (
                        "Angry and hurt after yesterday's disagreement"
                    ),
                    "current_physical_state": "Healthy",
                    "current_goal": (
                        "Understand whether she can trust John again"
                    ),
                    "current_location": "University cafeteria",
                    "important_knowledge": [
                        "An unidentified person has sent Maya anonymous messages"
                    ],
                },
                "user": {
                    "name": "John",
                    "role": "User",
                    "current_emotional_state": "Concerned",
                    "current_physical_state": "",
                    "current_goal": "Repair the disagreement with Maya",
                    "current_location": "University cafeteria",
                    "important_knowledge": [],
                },
                "leo": {
                    "name": "Leo",
                    "role": "Maya's former business partner",
                    "current_emotional_state": "Unknown",
                    "current_physical_state": "",
                    "current_goal": "Unknown",
                    "current_location": "Unknown",
                    "important_knowledge": [],
                },
            },
            "relationships": [
                {
                    "characters": ["maya", "user"],
                    "relationship": "Close friends",
                    "current_dynamic": (
                        "Guarded and distant after a recent disagreement"
                    ),
                }
            ],
            "plot_threads": [
                {
                    "id": "anonymous_messages",
                    "description": (
                        "An unidentified person has been sending Maya "
                        "anonymous messages."
                    ),
                    "status": "active",
                    "involved_characters": ["maya"],
                }
            ],
            "current_scene": {
                "location": "University cafeteria",
                "time": "Evening",
                "participants": ["maya", "user"],
                "situation": (
                    "Maya and John are sitting together after a disagreement."
                ),
                "atmosphere": "Quiet and tense",
                "continuity_details": [
                    "Maya's phone is on the table"
                ],
            },
        }
    )


@unittest.skipUnless(
    os.environ.get("AMOUR_RUN_LIVE_LLM_TESTS") == "1",
    (
        "Live LLM tests are opt-in. Set AMOUR_RUN_LIVE_LLM_TESTS=1 "
        "to make real model calls."
    ),
)
class LiveStoryStateLLMIntegrationTests(unittest.TestCase):
    """
    Real-LLM tests for section selection and incremental StoryState updates.

    These tests are intentionally separate from tests.py because they:
    - make external LLM API calls;
    - can consume API quota and incur usage costs;
    - are slower and nondeterministic compared with unit tests.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        provider = (
            getattr(settings, "LLM_PROVIDER", "")
            or os.environ.get("LLM_PROVIDER", "bedrock")
        ).strip().lower()
        api_key, _, models = response_generator_module._get_llm_configuration()

        if not models:
            raise unittest.SkipTest(
                "No models are configured for the selected LLM provider."
            )
        if provider != "bedrock" and not api_key:
            raise unittest.SkipTest(
                "The API key for the selected non-Bedrock provider is not configured."
            )


    def setUp(self):
        self.story_state = make_live_llm_story_state()

    def _all_configured_models_are_rate_limited(self) -> bool:
        """Distinguish provider throttling from an application regression."""
        _, llm_base_url, models = (
            response_generator_module._get_llm_configuration()
        )

        return all(
            response_generator_module._get_model_rate_limit_cooldown(
                llm_base_url,
                model,
            ) > 0
            for model in models
        )

    def _run_live_turn(
        self,
        message: str,
        *,
        persona_name: str = "Maya",
        persona_age: int = 24,
        greeting: str = (
            "Maya is sitting with John in the university cafeteria."
        ),
        memory_prompt: str = (
            "Maya and John have been close friends for several years. "
            "Yesterday's disagreement left their friendship strained. Maya "
            "has also been receiving anonymous messages."
        ),
        user_name: str = "John",
        story_state: StoryState | None = None,
    ) -> dict:
        """
        Execute the real two-stage LLM pipeline.

        Reeve is isolated, but requests.post is deliberately untouched.
        Therefore Story Director and Response Generator are real model calls.
        """
        effective_story_state = (
            story_state if story_state is not None else self.story_state
        )
        with (
            patch(
                "response_generator.generator.store_memory_for_user"
            ) as mock_store,
            patch(
                "response_generator.generator.retrieve_context_for_user",
                return_value="",
            ) as mock_retrieve,
        ):
            result = generate_companion_reply(
                message=message,
                namespace=f"live_llm_test_user_persona_{persona_name.casefold()}",
                persona_name=persona_name,
                persona_age=persona_age,
                greeting=greeting,
                memory_prompt=memory_prompt,
                user_name=user_name,
                conversation_history=[],
                current_conflict_stage=1,
                story_state=effective_story_state,
            )

            # Both Reeve writes are isolated. No Reeve network request is made.
            self.assertGreaterEqual(mock_store.call_count, 1)
            mock_retrieve.assert_called_once()

        diagnostic = (
            f"\nGeneration result: {result!r}\n"
            f"Planner patch: {result.get('planner_state_patch')!r}\n"
            f"Final patch: {result.get('state_patch')!r}"
        )

        if (
            not result.get("success")
            and self._all_configured_models_are_rate_limited()
        ):
            raise unittest.SkipTest(
                "All configured models are in rate-limit cooldown; "
                "this live scenario is inconclusive, not an application failure."
            )

        self.assertTrue(
            result.get("success"),
            msg="Live LLM generation failed." + diagnostic,
        )
        self.assertIsInstance(
            result.get("updated_story_state"),
            StoryState,
            msg="Feature 6 did not return a StoryState." + diagnostic,
        )

        # Independently verify that the final LLM patch remains valid and
        # inside the Story Director's approved scope.
        validated_patch = validate_story_state_patch(
            patch=result["state_patch"],
            story_state=effective_story_state,
            planner_patch=result["planner_state_patch"],
        )
        self.assertEqual(validated_patch, result["state_patch"])

        return result

    def _diagnostic(self, result: dict) -> str:
        return (
            f"\nReply: {result.get('reply')!r}"
            f"\nPlanner patch: {result.get('planner_state_patch')!r}"
            f"\nFinal patch: {result.get('state_patch')!r}"
            f"\nUpdated state: "
            f"{result.get('updated_story_state').model_dump(mode='json')!r}"
        )

    def test_live_llm_authors_concrete_readings_and_takes_action(self):
        """A persona's background should ground specific readings and action."""
        persona = {
            "name": "Valerie",
            "age": 31,
            "tagline": "Submersible systems engineer and expedition co-pilot",
            "greeting": (
                "Valerie is at the controls of a research submersible with "
                "Ankesh during a deep-water survey."
            ),
            "memory_prompt": (
                "Valerie grew up in Halifax, where her father repaired "
                "commercial fishing boats. She studied marine engineering "
                "and has spent eight years maintaining deep-water research "
                "submersibles. On her last expedition, a faulty temperature "
                "probe produced a false alarm, so she learned to compare "
                "independent sensors before drawing conclusions. She and "
                "Ankesh are experienced crewmates on their first survey "
                "together."
            ),
        }
        story_state = StoryState.model_validate(
            {
                "schema_version": 1,
                "story_summary": (
                    "Valerie and Ankesh are operating a research submersible "
                    "during a deep-water survey."
                ),
                "characters": {
                    "valerie": {
                        "name": "Valerie",
                        "role": (
                            "Submersible systems engineer and co-pilot"
                        ),
                        "current_emotional_state": "Focused",
                        "current_physical_state": "Healthy",
                        "current_goal": (
                            "Monitor the submersible and keep the crew safe"
                        ),
                        "current_location": "Submersible control room",
                        "important_knowledge": [],
                    },
                    "user": {
                        "name": "Ankesh",
                        "role": "Pilot",
                        "current_emotional_state": "Focused",
                        "current_physical_state": "Healthy",
                        "current_goal": "Complete the deep-water survey",
                        "current_location": "Submersible control room",
                        "important_knowledge": [],
                    },
                },
                "relationships": [
                    {
                        "characters": ["valerie", "user"],
                        "relationship": "Crewmates",
                        "current_dynamic": "Professional and collaborative",
                    }
                ],
                "plot_threads": [],
                "current_scene": {
                    "location": "Research submersible control room",
                    "time": "During a deep-water survey",
                    "participants": ["valerie", "user"],
                    "situation": (
                        "Valerie and Ankesh are monitoring the submersible "
                        "during its descent."
                    ),
                    "atmosphere": "Quiet and focused",
                    "continuity_details": [
                        "Thermal telemetry and depth sensors are active"
                    ],
                },
            }
        )
        question = (
            "What do the thermal telemetry and depth sensors show on your "
            "console?"
        )

        result = self._run_live_turn(
            question,
            persona_name=persona["name"],
            persona_age=persona["age"],
            greeting=persona["greeting"],
            memory_prompt=persona["memory_prompt"],
            user_name="Ankesh",
            story_state=story_state,
        )

        plan = result["next_beat"]
        planned_dialogue = plan["dialogue_direction"]
        planned_details = " ".join(
            (
                plan["narrative_development"],
                planned_dialogue,
                *plan["character_actions"],
            )
        )
        reply = result["reply"]
        diagnostic = self._diagnostic(result)

        self.assertRegex(
            planned_details,
            r"(?i)(temperature|thermal).*\d|\d.*(temperature|thermal)",
            "The plan should provide a concrete temperature reading."
            + diagnostic,
        )
        self.assertRegex(
            planned_details,
            r"(?i)(depth|meters?|metres?).*\d|\d.*(depth|meters?|metres?)",
            "The plan should provide a concrete depth reading." + diagnostic,
        )
        self.assertRegex(
            planned_dialogue,
            r"(?i)(because|so|which means|indicat|suggest|therefore|"
            r"my read|I think|I suspect)",
            "Dialogue direction should include an interpretation, not a "
            "placeholder." + diagnostic,
        )
        self.assertGreaterEqual(
            len(re.findall(r"\d+(?:\.\d+)?", reply)),
            2,
            "The reply should convey concrete sensor readings." + diagnostic,
        )
        self.assertRegex(
            reply,
            r"(?i)\b(check|compare|cross-check|adjust|switch|reroute|"
            r"inspect|trace|stabilize|monitor|run|verify|take)\w*\b",
            "Valerie should take a purposeful action, not only report data."
            + diagnostic,
        )
        self.assertNotIn(
            question.casefold(),
            reply.casefold(),
            "The reply should not repeat the user's question." + diagnostic,
        )

    def test_live_llm_selects_character_state_for_emotional_change(self):
        """A clearly established emotional change should update Maya."""
        original_emotion = (
            self.story_state.characters["maya"].current_emotional_state
        )

        result = self._run_live_turn(
            "Maya, I sincerely apologize for yesterday. Maya accepts my "
            "apology, explicitly tells John that she is no longer angry, "
            "and says she now feels relieved and emotionally safe with him. "
            "This forgiveness and emotional change are established in the "
            "scene, not just hypothetical."
        )

        patch = result["state_patch"]
        self.assertIn(
            "characters",
            patch,
            msg="Expected a character section for an explicit emotional change."
            + self._diagnostic(result),
        )
        self.assertIn("maya", patch["characters"], self._diagnostic(result))
        self.assertIn(
            "current_emotional_state",
            patch["characters"]["maya"],
            self._diagnostic(result),
        )
        self.assertNotEqual(
            result["updated_story_state"]
            .characters["maya"]
            .current_emotional_state,
            original_emotion,
            self._diagnostic(result),
        )

    def test_live_llm_selects_relationship_for_mutual_trust_change(self):
        """A mutually confirmed relationship development should target the pair."""
        original_relationship = self.story_state.relationships[0].relationship
        original_dynamic = self.story_state.relationships[0].current_dynamic

        result = self._run_live_turn(
            "Maya explicitly tells John that she trusts him again and wants "
            "them to rebuild their romantic relationship. John clearly "
            "confirms that he feels the same. Treat their mutual decision "
            "as an established relationship development."
        )

        operations = result["state_patch"].get("relationships", [])
        matching_operations = [
            operation
            for operation in operations
            if frozenset(
                operation.get(
                    "characters",
                    operation.get("value", {}).get("characters", []),
                )
            ) == {"maya", "user"}
        ]

        self.assertTrue(
            matching_operations,
            msg="Expected a relationship operation targeting Maya and John."
            + self._diagnostic(result),
        )

        updated_relationship = next(
            (
                relationship
                for relationship in result["updated_story_state"].relationships
                if frozenset(relationship.characters) == {"maya", "user"}
            ),
            None,
        )
        self.assertIsNotNone(updated_relationship, self._diagnostic(result))
        self.assertTrue(
            updated_relationship.relationship != original_relationship
            or updated_relationship.current_dynamic != original_dynamic,
            msg=(
                "Expected the relationship type or current dynamic to change."
                + self._diagnostic(result)
            ),
        )

    def test_live_llm_selects_existing_plot_thread_by_id(self):
        """A confirmed revelation should update the relevant existing thread."""
        result = self._run_live_turn(
            "Maya shows John a verified message from Leo admitting that he "
            "sent the anonymous messages. Maya accepts the admission as "
            "proof, and the mystery of who sent the messages is now resolved. "
            "Treat this as a confirmed revelation, not a suspicion."
        )

        operations = result["state_patch"].get("plot_threads", [])
        matching_operations = [
            operation
            for operation in operations
            if operation.get("id") == "anonymous_messages"
        ]

        self.assertTrue(
            matching_operations,
            msg="Expected a plot-thread operation targeting anonymous_messages."
            + self._diagnostic(result),
        )

        updated_thread = next(
            (
                thread
                for thread in result["updated_story_state"].plot_threads
                if thread.id == "anonymous_messages"
            ),
            None,
        )
        self.assertIsNotNone(updated_thread, self._diagnostic(result))
        self.assertEqual(
            updated_thread.status,
            "resolved",
            self._diagnostic(result),
        )

    def test_live_llm_selects_current_scene_for_location_transition(self):
        """An explicitly completed location transition should update the scene."""
        original_location = self.story_state.current_scene.location

        result = self._run_live_turn(
            "We have now left the university cafeteria and arrived at "
            "Riverside Park. Maya and John are sitting together on a bench "
            "there. It is now 9:30 PM. This is the current established scene."
        )

        self.assertIn(
            "current_scene",
            result["state_patch"],
            msg="Expected a current_scene section for an explicit scene transition."
            + self._diagnostic(result),
        )

        updated_scene = result["updated_story_state"].current_scene
        self.assertNotEqual(updated_scene.location, original_location)
        self.assertIn(
            "park",
            updated_scene.location.casefold(),
            self._diagnostic(result),
        )

    def test_live_llm_can_return_empty_patch_for_ordinary_conversation(self):
        """A casual exchange with no persistent development should not force a patch."""
        result = self._run_live_turn(
            "Haha, that was a good joke. Tell me another one while we stay "
            "right here. Nothing meaningful has changed in the story, "
            "our relationship, anyone's emotional state, or the current scene."
        )

        self.assertEqual(
            result["state_patch"],
            {},
            msg="Expected an empty patch for ordinary conversation."
            + self._diagnostic(result),
        )
        self.assertEqual(
            result["updated_story_state"].model_dump(mode="json"),
            self.story_state.model_dump(mode="json"),
        )


@unittest.skipUnless(
    os.environ.get("AMOUR_RUN_LIVE_LLM_TESTS") == "1",
    (
        "Live LLM tests are opt-in. Set AMOUR_RUN_LIVE_LLM_TESTS=1 "
        "to make real model calls."
    ),
)
class LiveChatEndpointLLMIntegrationTests(DjangoTestCase):
    """Exercise the client-shaped chat request through the real API pipeline."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        provider = (
            getattr(settings, "LLM_PROVIDER", "")
            or os.environ.get("LLM_PROVIDER", "bedrock")
        ).strip().lower()
        api_key, _, models = response_generator_module._get_llm_configuration()
        if not models:
            raise unittest.SkipTest(
                "No models are configured for the selected LLM provider."
            )
        if provider != "bedrock" and not api_key:
            raise unittest.SkipTest(
                "The API key for the selected non-Bedrock provider is not configured."
            )

    def test_live_chat_endpoint_runs_persona_pipeline_end_to_end(self):
        from response_generator.generator import generate_companion_reply

        persona = Persona.objects.create(
            name="Valerie",
            age=31,
            tagline="Submersible systems engineer and expedition co-pilot",
            greeting=(
                "Valerie is at the controls of a research submersible with "
                "Ankesh during a deep-water survey."
            ),
            memory_prompt=(
                "Valerie grew up in Halifax, where her father repaired "
                "commercial fishing boats. She studied marine engineering "
                "and has spent eight years maintaining deep-water research "
                "submersibles. On her last expedition, a faulty temperature "
                "probe produced a false alarm, so she learned to compare "
                "independent sensors before drawing conclusions. She and "
                "Ankesh are experienced crewmates on their first survey "
                "together."
            ),
        )
        user_id = "live-e2e-ankesh"
        user_key = "live-e2e-memory-key"
        client_message_id = "live-e2e-valerie-sensors-001"
        question = (
            "What do the thermal telemetry and depth sensors show on your "
            "console?"
        )
        payload = {
            "client_message_id": client_message_id,
            "message": question,
            "persona_id": str(persona.id),
            "persona_name": persona.name,
            "greeting": persona.greeting,
            "memory_prompt": persona.memory_prompt,
            "client_time": "Wednesday, November 11, 2026, 6:40 PM",
            "client_timezone": "Asia/Kolkata",
            "user_id": user_id,
            "user_name": "Ankesh",
            "user_key": user_key,
        }
        generation_results = []

        def capture_live_generation(*args, **kwargs):
            result = generate_companion_reply(*args, **kwargs)
            generation_results.append(result)
            return result

        with (
            patch(
                "response_generator.generator.store_memory_for_user"
            ) as mock_store,
            patch(
                "response_generator.generator.retrieve_context_for_user",
                return_value="",
            ) as mock_retrieve,
            patch(
                "memory.views.generate_companion_reply",
                side_effect=capture_live_generation,
            ),
        ):
            response = APIClient().post(
                "/api/memory/chat/",
                payload,
                format="json",
                HTTP_X_MEMORY_USER_KEY=user_key,
            )

        diagnostic = (
            f"\nHTTP status: {response.status_code}"
            f"\nHTTP response: {getattr(response, 'data', response.content)!r}"
            f"\nGeneration: {generation_results!r}"
        )
        self.assertEqual(response.status_code, 200, diagnostic)
        self.assertEqual(len(generation_results), 1, diagnostic)
        self.assertGreaterEqual(mock_store.call_count, 2)
        mock_retrieve.assert_called_once()

        result = generation_results[0]
        self.assertTrue(result.get("success"), diagnostic)
        self.assertEqual(response.data["reply"], result["reply"], diagnostic)
        self.assertEqual(
            response.data["client_message_id"],
            client_message_id,
            diagnostic,
        )

        state_record = CompanionStoryState.objects.get(
            namespace=response.data["namespace"]
        )
        self.assertEqual(state_record.revision, response.data["metadata"]["story_state"]["revision"])
        self.assertGreaterEqual(state_record.revision, 1, diagnostic)
        state = state_record.state
        persona_character_id = f"persona_{str(persona.id).replace('-', '_')}"
        self.assertIn(persona_character_id, state["characters"], diagnostic)
        self.assertEqual(
            state["characters"][persona_character_id]["name"],
            persona.name,
        )

        messages = list(
            PersonaChatMessage.objects.filter(
                user_identifier=user_id,
                persona_identifier=str(persona.id),
            ).order_by("created_at")
        )
        self.assertEqual([item.sender for item in messages], ["user", "bot"])
        self.assertEqual(messages[0].client_message_id, client_message_id)
        self.assertEqual(messages[1].client_message_id, client_message_id)
        self.assertEqual(
            decrypt_chat_message(
                messages[0].text,
                user_id=user_id,
                client_key=user_key,
            ),
            question,
        )
        self.assertEqual(
            decrypt_chat_message(
                messages[1].text,
                user_id=user_id,
                client_key=user_key,
            ),
            response.data["reply"],
        )

        plan = result["next_beat"]
        planned_dialogue = plan["dialogue_direction"]
        planned_details = " ".join(
            (
                plan["narrative_development"],
                planned_dialogue,
                *plan["character_actions"],
            )
        )
        reply = response.data["reply"]
        behavior_diagnostic = (
            f"\nPlanner next_beat: {plan!r}"
            f"\nReply: {reply!r}"
            f"\nPersona memory profile: {persona.memory_prompt!r}"
        )
        print(f"\nLIVE_CHAT_PLAN: {plan!r}")
        print(f"LIVE_CHAT_REPLY: {reply}")
        self.assertRegex(
            planned_details,
            r"(?i)(temperature|thermal).*\d|\d.*(temperature|thermal)",
            "The live plan must author a concrete thermal reading."
            + behavior_diagnostic,
        )
        self.assertRegex(
            planned_details,
            r"(?i)(depth|meters?|metres?).*\d|\d.*(depth|meters?|metres?)",
            "The live plan must author a concrete depth reading."
            + behavior_diagnostic,
        )
        self.assertRegex(
            planned_dialogue,
            r"(?i)(because|so|which means|indicat|suggest|therefore|"
            r"my read|I think|I suspect)",
            "The dialogue direction must state a concrete interpretation."
            + behavior_diagnostic,
        )
        self.assertGreaterEqual(
            len(re.findall(r"\d+(?:\.\d+)?", reply)),
            2,
            "The live reply must communicate both sensor readings."
            + behavior_diagnostic,
        )
        self.assertRegex(
            reply,
            r"(?i)\b(check|compare|cross-check|adjust|switch|reroute|"
            r"inspect|trace|stabilize|monitor|run|verify|take)\w*\b",
            "The persona must take a purposeful next action."
            + behavior_diagnostic,
        )
        self.assertNotIn(
            question.casefold(),
            reply.casefold(),
            "The reply must not echo the user's question."
            + behavior_diagnostic,
        )
