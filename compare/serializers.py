"""Serializers for API responses."""
from __future__ import annotations

from rest_framework import serializers

from .models import DiffResult


class DiffResultSerializer(serializers.ModelSerializer):
    """Serialize stored diff results for API consumers."""

    class Meta:
        model = DiffResult
        fields = [
            "id",
            "created_at",
            "summary",
            "options",
            "source_filenames",
            "diff_json",
        ]
        read_only_fields = fields
