from __future__ import annotations

from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError
from django.urls import reverse
from docx import Document
from io import BytesIO

from compare.services import DocumentParseError
from compare.views import STORAGE_ERROR_MESSAGE


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
    assert "links_added" in payload["summary"]
    assert "id" in payload


@pytest.mark.django_db
def test_compare_view_handles_parse_errors(client, monkeypatch) -> None:
    first = SimpleUploadedFile(
        "a.docx",
        _docx_bytes(["Hello"]),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    second = SimpleUploadedFile(
        "b.docx",
        _docx_bytes(["World"]),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    def _raise_parse_error(files, options):  # type: ignore[unused-arg]
        raise DocumentParseError("Unable to parse a.docx")

    monkeypatch.setattr("compare.views.perform_comparison", _raise_parse_error)

    response = client.post(
        reverse("compare:compare"),
        data={
            "doc_a": first,
            "doc_b": second,
        },
    )

    assert response.status_code == 400
    assert b"Unable to parse a.docx" in response.content


@pytest.mark.django_db
def test_compare_view_htmx_redirects_on_success(client) -> None:
    first = SimpleUploadedFile(
        "a.docx",
        _docx_bytes(["Hello"]),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    second = SimpleUploadedFile(
        "b.docx",
        _docx_bytes(["World"]),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    response = client.post(
        reverse("compare:compare"),
        data={
            "doc_a": first,
            "doc_b": second,
        },
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert response.headers.get("HX-Redirect", "").startswith("/result/")


@pytest.mark.django_db
def test_compare_view_htmx_returns_partial_when_storage_fails(client, monkeypatch) -> None:
    first = SimpleUploadedFile(
        "a.docx",
        _docx_bytes(["Hello"]),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    second = SimpleUploadedFile(
        "b.docx",
        _docx_bytes(["World"]),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    def _raise_storage_error(*_args, **_kwargs):
        raise DatabaseError("database offline")

    monkeypatch.setattr("compare.views.store_diff_result", _raise_storage_error)

    response = client.post(
        reverse("compare:compare"),
        data={
            "doc_a": first,
            "doc_b": second,
        },
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert response.headers.get("HX-Redirect") is None
    from html import unescape

    content = unescape(response.content.decode())
    assert STORAGE_ERROR_MESSAGE in content
    assert "Your comparison result will appear here" not in content
