from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("memory", "0012_personachatmessage_response_metadata"),
    ]

    operations = [
        migrations.DeleteModel(
            name="CompanionStoryState",
        ),
    ]
