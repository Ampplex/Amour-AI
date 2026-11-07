# Generated for the canonical companion StoryState model.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("memory", "0010_usermemorykeybackup"),
    ]

    operations = [
        migrations.CreateModel(
            name="CompanionStoryState",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("namespace", models.CharField(max_length=255, unique=True)),
                ("state", models.JSONField(blank=True, null=True)),
                ("schema_version", models.PositiveSmallIntegerField(default=1)),
                ("revision", models.PositiveBigIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "companion_story_states",
            },
        ),
    ]
