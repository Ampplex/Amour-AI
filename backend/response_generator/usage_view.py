from datetime import timedelta

from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.utils import timezone
from django.views import View

from authentication.console_auth import is_console_authorized
from .models import LLMRequestMetric


class LLMUsageView(View):
    """Return prompt-free LLM usage analytics to authorized console administrators."""

    def get(self, request):
        if not is_console_authorized(request):
            return JsonResponse({"error": "Admin credentials required"}, status=403)

        now = timezone.now()
        since_24h = now - timedelta(hours=24)
        since_7d = now - timedelta(days=7)
        current_metrics = LLMRequestMetric.objects.filter(created_at__gte=since_24h)
        summary = current_metrics.aggregate(
            requests=Count("id"),
            successes=Count("id", filter=Q(status="success")),
            failures=Count("id", filter=Q(status="error")),
            rate_limited=Count("id", filter=Q(status="rate_limited")),
            input_tokens=Sum("input_tokens"),
            output_tokens=Sum("output_tokens"),
            average_latency_ms=Avg("duration_ms"),
        )

        model_usage = list(
            LLMRequestMetric.objects.filter(created_at__gte=since_7d)
            .values("provider", "model")
            .annotate(
                requests=Count("id"),
                successes=Count("id", filter=Q(status="success")),
                rate_limited=Count("id", filter=Q(status="rate_limited")),
                input_tokens=Sum("input_tokens"),
                output_tokens=Sum("output_tokens"),
                average_latency_ms=Avg("duration_ms"),
            )
            .order_by("-requests", "provider", "model")[:25]
        )

        daily_usage = list(
            LLMRequestMetric.objects.filter(created_at__gte=since_7d)
            .annotate(day=TruncDate("created_at", tzinfo=timezone.get_current_timezone()))
            .values("day")
            .annotate(
                requests=Count("id"),
                input_tokens=Sum("input_tokens"),
                output_tokens=Sum("output_tokens"),
            )
            .order_by("day")
        )
        for day in daily_usage:
            day["day"] = day["day"].isoformat()

        quota_snapshots = []
        seen_models = set()
        quota_metrics = (
            LLMRequestMetric.objects.filter(
                created_at__gte=since_7d,
                provider="groq",
            )
            .exclude(
                rate_limit_limit_requests__isnull=True,
                rate_limit_remaining_requests__isnull=True,
                rate_limit_limit_tokens__isnull=True,
                rate_limit_remaining_tokens__isnull=True,
            )
            .order_by("-created_at")
            .values(
                "provider",
                "model",
                "created_at",
                "rate_limit_limit_requests",
                "rate_limit_remaining_requests",
                "rate_limit_reset_requests",
                "rate_limit_limit_tokens",
                "rate_limit_remaining_tokens",
                "rate_limit_reset_tokens",
            )[:200]
        )
        for metric in quota_metrics:
            key = (metric["provider"], metric["model"])
            if key in seen_models:
                continue
            seen_models.add(key)
            metric["observed_at"] = metric.pop("created_at").isoformat()
            quota_snapshots.append(metric)

        recent_requests = list(
            LLMRequestMetric.objects.filter(created_at__gte=since_24h)
            .values(
                "created_at",
                "provider",
                "model",
                "purpose",
                "status",
                "duration_ms",
                "input_tokens",
                "output_tokens",
                "response_status",
                "error_type",
            )[:30]
        )
        for metric in recent_requests:
            metric["created_at"] = metric["created_at"].isoformat()

        return JsonResponse({
            "window_start": since_24h.isoformat(),
            "summary": {
                key: (round(value, 1) if key == "average_latency_ms" and value is not None else value or 0)
                for key, value in summary.items()
            },
            "models": model_usage,
            "daily": daily_usage,
            "quota_snapshots": quota_snapshots,
            "recent": recent_requests,
        })
