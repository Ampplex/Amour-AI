from django.db import models


class LLMRequestMetric(models.Model):
    STATUS_CHOICES = (
        ("success", "Success"),
        ("error", "Error"),
        ("rate_limited", "Rate limited"),
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    provider = models.CharField(max_length=32, db_index=True)
    model = models.CharField(max_length=255, db_index=True)
    purpose = models.CharField(max_length=32, default="chat")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, db_index=True)
    duration_ms = models.PositiveIntegerField(default=0)
    input_tokens = models.PositiveIntegerField(null=True, blank=True)
    output_tokens = models.PositiveIntegerField(null=True, blank=True)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    error_type = models.CharField(max_length=128, blank=True, default="")
    rate_limit_limit_requests = models.PositiveIntegerField(null=True, blank=True)
    rate_limit_remaining_requests = models.PositiveIntegerField(null=True, blank=True)
    rate_limit_reset_requests = models.CharField(max_length=64, blank=True, default="")
    rate_limit_limit_tokens = models.PositiveIntegerField(null=True, blank=True)
    rate_limit_remaining_tokens = models.PositiveIntegerField(null=True, blank=True)
    rate_limit_reset_tokens = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["provider", "model", "created_at"],
                name="llm_metric_provider_time_idx",
            ),
            models.Index(
                fields=["status", "created_at"],
                name="llm_metric_status_time_idx",
            ),
        ]
