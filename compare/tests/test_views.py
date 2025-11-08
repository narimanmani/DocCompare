from __future__ import annotations

from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from docx import Document


def _docx_bytes(paragraphs: list[str]) -> bytes:
    document = Document()
    for text in paragraphs:
        document.add_paragraph(text)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


@pytest.mark.django_db
def test_health_check(client) -> None:
    response = client.get(reverse("compare:health"))
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_upload_page_renders_form(client) -> None:
    response = client.get(reverse("compare:upload"))
    assert response.status_code == 200
    assert b"DOCX Diff" in response.content


@pytest.mark.django_db
def test_api_compare_persists_result(client) -> None:
    first = SimpleUploadedFile("a.docx", _docx_bytes(["Hello"]), content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    second = SimpleUploadedFile("b.docx", _docx_bytes(["Hello there"]), content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    response = client.post(
        reverse("compare:api-compare"),
        data={
            "doc_a": first,
            "doc_b": second,
            "ignore_case": "on",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["summary"]["insertions"] >= 0
    assert "id" in payload
