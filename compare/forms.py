"""Forms for handling document comparison uploads."""
from __future__ import annotations

from typing import Iterable

from django import forms
from django.conf import settings


class DocCompareForm(forms.Form):
    """Form for uploading two DOCX files with optional diff settings."""

    doc_a = forms.FileField(label="Document A")
    doc_b = forms.FileField(label="Document B")
    ignore_case = forms.BooleanField(required=False, initial=True)
    ignore_punctuation = forms.BooleanField(required=False, initial=False)
    ignore_whitespace = forms.BooleanField(required=False, initial=False)

    error_messages = {
        "invalid_extension": "Only .docx files are supported.",
        "max_size": "Files must be smaller than 15MB.",
    }

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
