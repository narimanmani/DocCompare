"""Forms for handling document comparison uploads."""
from __future__ import annotations

from typing import Iterable

from django import forms
from django.conf import settings


class DocCompareForm(forms.Form):
    """Form for uploading two DOCX files with optional diff settings."""

    doc_a = forms.FileField(label="Document A")
    doc_b = forms.FileField(label="Document B")
    ignore_case = forms.BooleanField(
        required=False,
        initial=True,
        label="Ignore case differences",
        help_text="Treat uppercase and lowercase characters as equal.",
    )
    ignore_punctuation = forms.BooleanField(
        required=False,
        initial=False,
        label="Ignore punctuation",
        help_text="Strip punctuation before computing the diff.",
    )
    ignore_whitespace = forms.BooleanField(
        required=False,
        initial=False,
        label="Ignore extra whitespace",
        help_text="Collapse repeated spaces and line breaks before diffing.",
    )
    ignore_protocol = forms.BooleanField(
        required=False,
        initial=False,
        label="Ignore protocol (http/https)",
        help_text="Treat http and https links as the same destination.",
    )
    normalize_trailing_slash = forms.BooleanField(
        required=False,
        initial=False,
        label="Normalize trailing slash",
        help_text="Consider /path and /path/ equivalent when comparing URLs.",
    )
    drop_tracking_params = forms.BooleanField(
        required=False,
        initial=True,
        label="Drop tracking parameters",
        help_text="Remove UTM and ad-tracking parameters before comparing URLs.",
    )
    lowercase_host = forms.BooleanField(
        required=False,
        initial=False,
        label="Lowercase host name",
        help_text="Compare host names case-insensitively.",
    )
    ignore_url_fragments = forms.BooleanField(
        required=False,
        initial=False,
        label="Ignore URL fragments",
        help_text="Strip #section fragments from links before comparing.",
    )

    error_messages = {
        "invalid_extension": "Only .docx files are supported.",
        "max_size": "Files must be smaller than 15MB.",
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        file_attrs = {"class": "app-input"}
        checkbox_attrs = {"class": "app-checkbox"}
        for name in ("doc_a", "doc_b"):
            self.fields[name].widget.attrs.update(file_attrs)
        for name in (
            "ignore_case",
            "ignore_punctuation",
            "ignore_whitespace",
            "ignore_protocol",
            "normalize_trailing_slash",
            "drop_tracking_params",
            "lowercase_host",
            "ignore_url_fragments",
        ):
            self.fields[name].widget.attrs.update(checkbox_attrs)

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean()
        for field in ("doc_a", "doc_b"):
            upload = cleaned_data.get(field)
            if upload is None:
                continue
            if not upload.name.lower().endswith(".docx"):
                self.add_error(field, self.error_messages["invalid_extension"])
            if upload.size > settings.UPLOAD_MAX_SIZE:
                self.add_error(field, self.error_messages["max_size"])
        return cleaned_data

    def iter_files(self) -> Iterable[tuple[str, bytes]]:
        """Yield file names and raw content from the cleaned form data."""
        for field in ("doc_a", "doc_b"):
            upload = self.cleaned_data[field]
            upload.seek(0)
            yield upload.name, upload.read()
