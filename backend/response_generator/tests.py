from unittest.mock import MagicMock, patch
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase, override_settings

from response_generator.generator import generate_companion_reply
from response_generator.llm_client import call_llm
from response_generator.observability import extract_rate_limit_headers, extract_token_usage
from response_generator.prompt_builder import build_roleplay_system_prompt
from response_generator.tone_tracker import _extract_tone_label, classify_tone_with_bedrock
from response_generator.usage_view import LLMUsageView


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

    def test_turn_focus_respects_non_mature_story_tones(self):
        casual_prompt = self._build_sample(story_tone="casual")
        comfort_prompt = self._build_sample(story_tone="comfort")
        default_prompt = self._build_sample(story_tone="default")
        mature_prompt = self._build_sample(story_tone="mature")

        casual_tail = casual_prompt.split("--- THIS TURN ---")[1].lower()
        comfort_tail = comfort_prompt.split("--- THIS TURN ---")[1].lower()
        default_tail = default_prompt.split("--- THIS TURN ---")[1].lower()
        mature_tail = mature_prompt.split("--- THIS TURN ---")[1].lower()

        self.assertIn("do not force prior sensual or mature tension", casual_tail)
        self.assertIn("rather than pushing sensual escalation", comfort_tail)
        self.assertIn("non-adult topic", default_tail)
        self.assertIn("mature romantic progression", mature_tail)

        casual_auto_tail = self._build_sample(story_tone="casual", is_autonomous_continue=True).split("--- THIS TURN ---")[1].lower()
        self.assertNotIn("escalate the current romantic or mature tension", casual_auto_tail)

    def test_autonomous_continue_avoids_silence_and_waiting_triggers(self):
        full_prompt_forbidden = (
            "silence",
            "isn't talking",
            "waiting to",
            "waiting passively",
            "waiting for the user",
        )
        turn_tail_forbidden = ("silence", "pauses", "isn't talking", "waiting")
        for tone in ("default", "mature", "casual", "comfort"):
            prompt = self._build_sample(story_tone=tone, is_autonomous_continue=True).lower()
            turn_tail = prompt.split("--- this turn ---")[1]
            self.assertIn("pick up a split second after your last line", turn_tail)
            for term in full_prompt_forbidden:
                self.assertNotIn(term, prompt, f"Unexpected trigger {term!r} in autonomous prompt for tone={tone}")
            for term in turn_tail_forbidden:
                self.assertNotIn(term, turn_tail, f"Unexpected trigger {term!r} in autonomous turn tail for tone={tone}")


class ToneTrackerParsingTests(SimpleTestCase):
    def test_extract_tone_label_handles_wrapped_and_punctuated_outputs(self):
        self.assertEqual(_extract_tone_label("casual"), "casual")
        self.assertEqual(_extract_tone_label("Tone: casual."), "casual")
        self.assertEqual(_extract_tone_label("'comfort'"), "comfort")
        self.assertEqual(_extract_tone_label("default - topic changed"), "default")
        self.assertEqual(_extract_tone_label("  MATURE\n"), "mature")
        self.assertIsNone(_extract_tone_label("unknown"))
        self.assertIsNone(_extract_tone_label(""))

    def test_classify_tone_transitions_from_mature_on_wrapped_llm_outputs(self):
        for raw_reply, expected in [
            ("Tone: casual.", "casual"),
            ("Next tone: comfort", "comfort"),
            ("default - user changed topic", "default"),
            ("mature", "mature"),
        ]:
            result = classify_tone_with_bedrock(
                user_message="How was your day?",
                current_tone="mature",
                classify_fn=lambda _msgs, **_kw: raw_reply,
            )
            self.assertEqual(result, expected)

    def test_classify_tone_falls_back_to_current_tone_on_error_or_unrecognized_output(self):
        def failing_fn(_msgs, **_kw):
            raise RuntimeError("Bedrock unavailable")

        self.assertEqual(
            classify_tone_with_bedrock("Hi there", current_tone="mature", classify_fn=failing_fn),
            "mature",
        )
        self.assertEqual(
            classify_tone_with_bedrock(
                "Hi there",
                current_tone="mature",
                classify_fn=lambda _msgs, **_kw: "unclear",
            ),
            "mature",
        )


class GeneratorAndClientTests(SimpleTestCase):
    def test_extract_token_usage_supports_openai_and_bedrock_shapes(self):
        self.assertEqual(
            extract_token_usage({"prompt_tokens": "24", "completion_tokens": 9}),
            (24, 9),
        )
        self.assertEqual(
            extract_token_usage({"inputTokens": 31, "outputTokens": 12}),
            (31, 12),
        )
        self.assertEqual(extract_token_usage(None), (None, None))

    def test_extract_rate_limit_headers_normalizes_provider_quota(self):
        quota = extract_rate_limit_headers({
            "X-RateLimit-Limit-Tokens": "500000",
            "x-ratelimit-remaining-tokens": "490000",
            "x-ratelimit-reset-tokens": "1m",
        })
        self.assertEqual(quota["rate_limit_limit_tokens"], 500000)
        self.assertEqual(quota["rate_limit_remaining_tokens"], 490000)
        self.assertEqual(quota["rate_limit_reset_tokens"], "1m")

    @override_settings(DEBUG=False, SECRET_KEY="test-console-secret")
    def test_llm_usage_endpoint_rejects_anonymous_requests(self):
        request = RequestFactory().get("/api/llm/usage/")
        request.user = AnonymousUser()

        response = LLMUsageView.as_view()(request)

        self.assertEqual(response.status_code, 403)

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
            patch("response_generator.llm_client.record_llm_request"),
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

    def test_call_llm_records_groq_usage_and_quota_headers(self):
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.headers = {
            "x-ratelimit-limit-requests": "1000",
            "x-ratelimit-remaining-requests": "987",
            "x-ratelimit-reset-requests": "2m30s",
            "x-ratelimit-limit-tokens": "500000",
            "x-ratelimit-remaining-tokens": "490000",
            "x-ratelimit-reset-tokens": "1m",
        }
        fake_response.json.return_value = {
            "choices": [{"message": {"content": "Hello."}}],
            "usage": {"prompt_tokens": 42, "completion_tokens": 7},
        }

        with (
            patch("response_generator.llm_client.get_llm_configuration", return_value=("key", "https://api.groq.com/openai/v1", ["qwen/qwen3.8-27b"])),
            patch("response_generator.llm_client.get_groq_api_keys", return_value=["key"]),
            patch("response_generator.llm_client.settings.RESPONSE_LLM_PROVIDER", "groq"),
            patch("response_generator.llm_client.requests.post", return_value=fake_response),
            patch("response_generator.llm_client.record_llm_request") as mock_record,
        ):
            text, model = call_llm(messages=[{"role": "user", "content": "Hi"}])

        self.assertEqual((text, model), ("Hello.", "qwen/qwen3.8-27b"))
        mock_record.assert_called_once()
        recorded = mock_record.call_args.kwargs
        self.assertEqual(recorded["provider"], "groq")
        self.assertEqual(recorded["input_tokens"], 42)
        self.assertEqual(recorded["output_tokens"], 7)
        self.assertEqual(recorded["status"], "success")
        self.assertEqual(
            recorded["rate_limit_headers"]["x-ratelimit-remaining-tokens"],
            "490000",
        )

    def test_call_llm_records_groq_rate_limit_attempt(self):
        fake_response = MagicMock()
        fake_response.status_code = 429
        fake_response.headers = {"x-ratelimit-reset-tokens": "1m"}

        with (
            patch("response_generator.llm_client.get_llm_configuration", return_value=("key", "https://groq.test/openai/v1", ["qwen/qwen3.8-27b"])),
            patch("response_generator.llm_client.get_groq_api_keys", return_value=["key"]),
            patch("response_generator.llm_client.settings.RESPONSE_LLM_PROVIDER", "groq"),
            patch("response_generator.llm_client.requests.post", return_value=fake_response),
            patch("response_generator.llm_client.record_llm_request") as mock_record,
        ):
            text, model = call_llm(messages=[{"role": "user", "content": "Hi"}])

        self.assertEqual((text, model), (None, None))
        mock_record.assert_called_once()
        recorded = mock_record.call_args.kwargs
        self.assertEqual(recorded["status"], "rate_limited")
        self.assertEqual(recorded["response_status"], 429)

    def test_autonomous_continue_merges_history_and_scrubs_memory_labels(self):
        history = [
            {"role": "user", "content": "Hey there."},
            {"role": "assistant", "content": "*I lean on the counter.* First line."},
            {"role": "assistant", "content": "Second line."},
        ]

        with (
            patch("response_generator.generator.retrieve_context_for_user", return_value="Assistant (continued): Old beat."),
            patch("response_generator.generator.call_llm", return_value=("*I pour another glass.* Third line.", "test-model")) as mock_call,
            patch("response_generator.generator.store_memory_for_user") as mock_store,
        ):
            res = generate_companion_reply(
                message="",
                namespace="usr_1_persona_2",
                persona_name="Elena",
                user_name="Alex",
                conversation_history=history,
                is_autonomous_continue=True,
                persist_exchange_to_memory=True,
            )

        self.assertTrue(res["success"])
        mock_call.assert_called_once()
        sent_messages = mock_call.call_args.kwargs["messages"]
        self.assertEqual(
            sent_messages[1:],
            [
                {"role": "user", "content": "Hey there."},
                {"role": "assistant", "content": "*I lean on the counter.* First line.\n\nSecond line."},
                {
                    "role": "user",
                    "content": "[Next beat: keep going immediately from your last line with your next thought, line, or movement.]",
                },
            ],
        )
        self.assertNotIn("(continued)", res["context"])
        mock_store.assert_called_once()
        stored_entry = mock_store.call_args.args[0]
        self.assertEqual(stored_entry, "Assistant: *I pour another glass.* Third line.")

    def test_autonomous_continue_strips_prior_leaks_and_retries_once(self):
        history = [
            {"role": "user", "content": "Hey."},
            {"role": "assistant", "content": "*I set down my cup.* Why aren't you speaking? I don't wait for answers."},
        ]

        with (
            patch("response_generator.generator.retrieve_context_for_user", return_value=""),
            patch(
                "response_generator.generator.call_llm",
                side_effect=[
                    ("I dont wait for answers, you are not speaking anything.", "test-model"),
                    ("*I step closer and straighten your collar.* Come walk with me.", "test-model"),
                ],
            ) as mock_call,
        ):
            res = generate_companion_reply(
                message="",
                namespace="usr_1_persona_2",
                persona_name="Elena",
                user_name="Alex",
                conversation_history=history,
                is_autonomous_continue=True,
                persist_exchange_to_memory=False,
            )

        self.assertTrue(res["success"])
        self.assertEqual(mock_call.call_count, 2)
        self.assertEqual(res["reply"], "*I step closer and straighten your collar.* Come walk with me.")
        first_attempt_messages = mock_call.call_args_list[0].kwargs["messages"]
        self.assertEqual(first_attempt_messages[2]["content"], "*I set down my cup.*")

    def test_normal_reply_does_not_trigger_autonomous_retry(self):
        with (
            patch("response_generator.generator.retrieve_context_for_user", return_value=""),
            patch(
                "response_generator.generator.call_llm",
                return_value=("You're awfully quiet tonight.", "test-model"),
            ) as mock_call,
        ):
            res = generate_companion_reply(
                message="I stayed quiet because I was thinking.",
                namespace="usr_1_persona_2",
                persona_name="Elena",
                user_name="Alex",
                is_autonomous_continue=False,
                persist_exchange_to_memory=False,
            )

        self.assertTrue(res["success"])
        mock_call.assert_called_once()
        self.assertEqual(res["reply"], "You're awfully quiet tonight.")
