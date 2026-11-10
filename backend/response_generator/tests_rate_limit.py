import json
import time
from unittest import TestCase
from unittest.mock import MagicMock, patch

from pydantic import BaseModel

from response_generator import generator


class StructuredProbeOutput(BaseModel):
    ok: bool


def make_response(status_code, payload=None, *, headers=None, text=""):
    response = MagicMock()
    response.status_code = status_code
    response.headers = headers or {}
    response.text = text
    if payload is not None:
        response.json.return_value = {
            "choices": [{"message": {"content": json.dumps(payload)}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
    return response


class LLMRateLimitReliabilityTests(TestCase):
    def setUp(self):
        self.cooldown_patch = patch.dict(
            generator._RATE_LIMIT_COOLDOWNS,
            {},
            clear=True,
        )
        self.cooldown_patch.start()
        self.addCleanup(self.cooldown_patch.stop)

    def _call(self, models):
        return generator._call_structured_llm(
            messages=[{"role": "user", "content": "test"}],
            output_model=StructuredProbeOutput,
            stage_name="rate_limit_test",
            llm_api_key="test-key",
            llm_base_url="https://api.example.test/v1",
            models_to_try=models,
        )

    @patch("response_generator.generator.requests.post")
    def test_bedrock_request_uses_runtime_chat_completions_endpoint(self, mock_post):
        mock_post.return_value = make_response(200, {"ok": True})

        output, model = generator._call_structured_llm(
            messages=[{"role": "user", "content": "test"}],
            output_model=StructuredProbeOutput,
            stage_name="bedrock_test",
            llm_api_key="bedrock-test-key",
            llm_base_url=(
                "https://bedrock-runtime.us-west-2.amazonaws.com/openai/v1"
            ),
            models_to_try=["mistral.mistral-large-3-675b-instruct"],
        )

        self.assertEqual(output, {"ok": True})
        self.assertEqual(model, "mistral.mistral-large-3-675b-instruct")
        self.assertEqual(
            mock_post.call_args.args[0],
            (
                "https://bedrock-runtime.us-west-2.amazonaws.com/"
                "openai/v1/chat/completions"
            ),
        )
        self.assertEqual(
            mock_post.call_args.kwargs["headers"]["Authorization"],
            "Bearer bedrock-test-key",
        )
        self.assertEqual(
            mock_post.call_args.kwargs["json"]["model"],
            "mistral.mistral-large-3-675b-instruct",
        )

    @patch("response_generator.generator.requests.post")
    def test_429_does_not_retry_same_model_before_trying_fallback(self, mock_post):
        mock_post.side_effect = [
            make_response(
                429,
                headers={"Retry-After": "30"},
                text="rate limited",
            ),
            make_response(200, {"ok": True}),
        ]

        output, model = self._call(["primary-model", "fallback-model"])

        self.assertEqual(output, {"ok": True})
        self.assertEqual(model, "fallback-model")
        self.assertEqual(mock_post.call_count, 2)
        self.assertEqual(
            [
                call.kwargs["json"]["model"]
                for call in mock_post.call_args_list
            ],
            ["primary-model", "fallback-model"],
        )

    @patch("response_generator.generator.requests.post")
    def test_413_does_not_resend_identical_payload_to_fallback(self, mock_post):
        mock_post.return_value = make_response(
            413,
            text="request too large",
        )

        output, model = self._call(["primary-model", "fallback-model"])

        self.assertIsNone(output)
        self.assertIsNone(model)
        self.assertEqual(mock_post.call_count, 1)
        self.assertEqual(
            mock_post.call_args.kwargs["json"]["model"],
            "primary-model",
        )

    @patch("response_generator.generator.requests.post")
    def test_rate_limited_model_is_skipped_during_later_pipeline_stage(
        self,
        mock_post,
    ):
        mock_post.side_effect = [
            make_response(
                429,
                headers={"Retry-After": "45"},
                text="rate limited",
            ),
            make_response(200, {"ok": True}),
            make_response(200, {"ok": True}),
        ]

        first_output, first_model = self._call(
            ["primary-model", "fallback-model"]
        )
        second_output, second_model = self._call(
            ["primary-model", "fallback-model"]
        )

        self.assertEqual(first_output, {"ok": True})
        self.assertEqual(first_model, "fallback-model")
        self.assertEqual(second_output, {"ok": True})
        self.assertEqual(second_model, "fallback-model")
        self.assertEqual(mock_post.call_count, 3)
        self.assertEqual(
            [
                call.kwargs["json"]["model"]
                for call in mock_post.call_args_list
            ],
            [
                "primary-model",
                "fallback-model",
                "fallback-model",
            ],
        )

    @patch("response_generator.generator.requests.post")
    def test_all_models_in_cooldown_make_no_http_requests(self, mock_post):
        reset_at = time.monotonic() + 60
        for model in ("primary-model", "fallback-model"):
            key = generator._rate_limit_cooldown_key(
                "https://api.example.test/v1",
                model,
            )
            generator._RATE_LIMIT_COOLDOWNS[key] = reset_at

        output, model = self._call(["primary-model", "fallback-model"])

        self.assertIsNone(output)
        self.assertIsNone(model)
        mock_post.assert_not_called()

    def test_provider_reset_headers_use_longest_quota_window(self):
        delay = generator._rate_limit_cooldown_seconds(
            {
                "Retry-After": "4",
                "retry-after-ms": "5500",
                "x-ratelimit-reset-requests": "3s",
                "x-ratelimit-reset-tokens": "8s",
            }
        )

        self.assertEqual(delay, 8.0)

    def test_duration_headers_support_seconds_and_minutes(self):
        self.assertEqual(
            generator._parse_rate_limit_delay("2.5s"),
            2.5,
        )
        self.assertEqual(
            generator._parse_rate_limit_delay("1m"),
            60.0,
        )
        self.assertEqual(
            generator._parse_rate_limit_delay("2500", milliseconds=True),
            2.5,
        )
