"""Initial migration for DiffResult model."""
from __future__ import annotations

import django.utils.timezone
import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies: list[tuple[str, str]] = []

    operations = [
        migrations.CreateModel(
            name="DiffResult",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("options", models.JSONField(default=dict)),
                ("summary", models.JSONField(default=dict)),
                ("diff_html", models.TextField()),
                ("diff_json", models.JSONField(default=dict)),
                ("source_filenames", models.JSONField(default=list)),
            ],
        ),
    ]
