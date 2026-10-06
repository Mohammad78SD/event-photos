from django.db import migrations, models


def raise_old_default(apps, schema_editor):
    # Events created under the old default of 30 never chose that number.
    apps.get_model("events", "Event").objects.filter(max_files_batch=30).update(max_files_batch=100)


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0002_event_moderator_token"),
    ]

    operations = [
        migrations.AlterField(
            model_name="event",
            name="max_files_batch",
            field=models.PositiveIntegerField(default=100),
        ),
        migrations.RunPython(raise_old_default, migrations.RunPython.noop),
    ]
