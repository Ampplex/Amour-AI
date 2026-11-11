from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("memory", "0011_companionstorystate"),
    ]

    operations = [
        migrations.AddField(
            model_name="personachatmessage",
            name="response_metadata",
            field=models.JSONField(
                default=dict,
                blank=True,
            ),
        ),
    ]
