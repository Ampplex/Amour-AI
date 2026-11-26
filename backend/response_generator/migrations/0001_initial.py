from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="LLMRequestMetric",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("provider", models.CharField(db_index=True, max_length=32)),
                ("model", models.CharField(db_index=True, max_length=255)),
                ("purpose", models.CharField(default="chat", max_length=32)),
                ("status", models.CharField(choices=[("success", "Success"), ("error", "Error"), ("rate_limited", "Rate limited")], db_index=True, max_length=16)),
                ("duration_ms", models.PositiveIntegerField(default=0)),
                ("input_tokens", models.PositiveIntegerField(blank=True, null=True)),
                ("output_tokens", models.PositiveIntegerField(blank=True, null=True)),
                ("response_status", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("error_type", models.CharField(blank=True, default="", max_length=128)),
                ("rate_limit_limit_requests", models.PositiveIntegerField(blank=True, null=True)),
                ("rate_limit_remaining_requests", models.PositiveIntegerField(blank=True, null=True)),
                ("rate_limit_reset_requests", models.CharField(blank=True, default="", max_length=64)),
                ("rate_limit_limit_tokens", models.PositiveIntegerField(blank=True, null=True)),
                ("rate_limit_remaining_tokens", models.PositiveIntegerField(blank=True, null=True)),
                ("rate_limit_reset_tokens", models.CharField(blank=True, default="", max_length=64)),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["provider", "model", "created_at"], name="llm_metric_provider_time_idx"),
                    models.Index(fields=["status", "created_at"], name="llm_metric_status_time_idx"),
                ],
            },
        ),
    ]
