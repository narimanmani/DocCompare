"""Django application configuration for compare."""
from __future__ import annotations

from django.apps import AppConfig


class CompareConfig(AppConfig):
    """Application configuration."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "compare"
