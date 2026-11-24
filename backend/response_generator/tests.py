from unittest.mock import MagicMock, patch
from django.test import SimpleTestCase

from response_generator.generator import generate_companion_reply
from response_generator.llm_client import call_llm
from response_generator.prompt_builder import build_roleplay_system_prompt


class PromptBuilderTests(SimpleTestCase):
    def _build_sample(self, **overrides):
        params = {
            "persona_name": "Elena",
            "persona_age": 24,
            "persona_tagline": "Warm and playful partner",
            "greeting": "I set down my curved blade and smile at you.",
            "memory_prompt": "Loves midnight walks and dry humor.",
            "user_name": "Alex",
            "client_time": "Monday, 10:00 AM",
            "client_timezone": "UTC",
            "memory_context": "Alex likes espresso.",
            "current_message": "Hey, missed me?",
            "has_history": True,
            "allow_user_name": False,
            "reply_length": "default",
            "is_autonomous_continue": False,
        }
        params.update(overrides)
        return build_roleplay_system_prompt(**params)

    def test_removes_safety_disclaimer_and_third_person_conflict(self):
        prompt = self._build_sample()
        lower = prompt.lower()
        self.assertNotIn("applicable safety requirements", lower)
        self.assertNotIn("truthful handling of real-world facts", lower)
        self.assertNotIn("third-person narration", lower)
        self.assertIn("first-person", lower)

    def test_gates_greeting_by_has_history(self):
        greeting = "I set down my curved blade and smile at you."
        first_turn_prompt = self._build_sample(greeting=greeting, has_history=False)
        later_turn_prompt = self._build_sample(greeting=greeting, has_history=True)
        self.assertIn(greeting, first_turn_prompt)
        self.assertNotIn(greeting, later_turn_prompt)

    def test_no_indented_directive_blocks(self):
        for mode in ("default", "short", "long"):
            prompt = self._build_sample(
                reply_length=mode,
                memory_context="Line 1 memory.\nLine 2 memory.",
            )
            for line in prompt.splitlines():
                self.assertEqual(
                    line,
                    line.lstrip(),
                    f"Unexpected leading whitespace found in {mode} line: {line!r}",
                )

    def test_kv_cache_prefix_identical_across_dynamic_turn_changes(self):
        prompt_a = self._build_sample(
            memory_context="Memory A: met at cafe.",
            current_message="UNIQUE_CURRENT_MSG_ALPHA",
            allow_user_name=False,
            is_autonomous_continue=False,
        )
        prompt_b = self._build_sample(
            memory_context="Memory B: watched a movie together.",
            current_message="UNIQUE_CURRENT_MSG_BETA",
            allow_user_name=True,
            is_autonomous_continue=True,
        )

        # Current user message is already sent as the final user turn, not duplicated in system prompt
        self.assertNotIn("UNIQUE_CURRENT_MSG_ALPHA", prompt_a)
        self.assertNotIn("UNIQUE_CURRENT_MSG_BETA", prompt_b)

        prefix_a = prompt_a.split("--- CURRENT RELATIONSHIP STATE & MEMORIES ---")[0]
        prefix_b = prompt_b.split("--- CURRENT RELATIONSHIP STATE & MEMORIES ---")[0]
        self.assertEqual(prefix_a, prefix_b)
        self.assertIn("--- CONVERSATION CONTEXT ---", prefix_a)
        self.assertIn("--- CORE ROLEPLAY DIRECTIVES ---", prefix_a)


class GeneratorAndClientTests(SimpleTestCase):
    def test_generator_uses_10_history_messages_and_passes_penalties(self):
        history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"Turn {i}"}
            for i in range(12)
        ]

        with (
            patch("response_generator.generator.retrieve_context_for_user", return_value=""),
            patch("response_generator.generator.call_llm", return_value=("*I grin* Turn 12.", "test-model")) as mock_call,
        ):
            res = generate_companion_reply(
                message="Latest message",
                namespace="usr_1_persona_2",
                persona_name="Elena",
                user_name="Alex",
                conversation_history=history,
                persist_exchange_to_memory=False,
            )

        self.assertTrue(res["success"])
        mock_call.assert_called_once()
        kwargs = mock_call.call_args.kwargs
        self.assertEqual(kwargs["frequency_penalty"], 0.5)
        self.assertEqual(kwargs["presence_penalty"], 0.5)
        sent_messages = kwargs["messages"]
        # 1 system + last 10 history + 1 current user message
        self.assertEqual(len(sent_messages), 12)
        self.assertEqual([m["content"] for m in sent_messages[1:-1]], [f"Turn {i}" for i in range(2, 12)])
        self.assertEqual(sent_messages[-1], {"role": "user", "content": "Latest message"})

    def test_call_llm_forwards_penalties_in_openai_payload(self):
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {"choices": [{"message": {"content": "Hey there."}}]}

        with (
            patch("response_generator.llm_client.get_llm_configuration", return_value=("key", "https://api.groq.com/openai/v1", ["qwen/qwen3.8-27b"])),
            patch("response_generator.llm_client.requests.post", return_value=fake_response) as mock_post,
        ):
            text, model = call_llm(
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=512,
                temperature=0.88,
                frequency_penalty=0.65,
                presence_penalty=0.4,
            )

        self.assertEqual(text, "Hey there.")
        self.assertEqual(model, "qwen/qwen3.8-27b")
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["frequency_penalty"], 0.65)
        self.assertEqual(payload["presence_penalty"], 0.4)
