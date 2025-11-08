"""Database models for storing comparison results."""
from __future__ import annotations

import uuid
from typing import Any

from django.db import models
from django.utils import timezone


class DiffResult(models.Model):
    """Persisted diff data for reuse and export."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(default=timezone.now)
    options = models.JSONField(default=dict)
    summary = models.JSONField(default=dict)
    diff_html = models.TextField()
    diff_json = models.JSONField(default=dict)
    source_filenames = models.JSONField(default=list)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover
        return f"DiffResult({self.id})"

    def as_api_payload(self) -> dict[str, Any]:
        """Return a serializable payload for API responses."""
        return {
            "id": str(self.id),
            "created_at": self.created_at.isoformat(),
            "summary": self.summary,
            "options": self.options,
            "source_filenames": self.source_filenames,
            "diff": self.diff_json,
        }
