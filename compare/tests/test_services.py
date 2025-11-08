from __future__ import annotations

from io import BytesIO

import pytest
from docx import Document

from compare.diff_utils import DiffComputationResult
from compare.services import DiffOptions, perform_comparison, store_diff_result


def make_docx(paragraphs: list[str]) -> bytes:
    document = Document()
    for text in paragraphs:
        document.add_paragraph(text)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


@pytest.mark.django_db
def test_store_diff_result_creates_record() -> None:
    diff = DiffComputationResult(
        html="<p>ok</p>",
        summary={
            "insertions": 1,
            "deletions": 0,
            "replacements": 0,
            "percent_changed": 50.0,
            "links_added": 0,
            "links_removed": 0,
            "links_changed_text": 0,
            "links_changed_href": 0,
        },
        paragraphs=[],
        link_changes=[],
    )
    result = store_diff_result(diff, DiffOptions(), ["a.docx", "b.docx"])
    assert result.summary["insertions"] == 1
    assert result.options["ignore_case"] is True


@pytest.mark.django_db
def test_perform_comparison_generates_summary() -> None:
    file_a = make_docx(["Hello world", "Goodbye"])
    file_b = make_docx(["hello world", "Farewell"])

    diff, filenames = perform_comparison(
        [("first.docx", file_a), ("second.docx", file_b)],
        DiffOptions(ignore_case=True, ignore_punctuation=False, ignore_whitespace=False),
    )

    assert filenames == ["first.docx", "second.docx"]
    assert diff.summary["insertions"] >= 0
    assert diff.summary["percent_changed"] >= 0
    assert {"links_added", "links_removed", "links_changed_text", "links_changed_href"} <= diff.summary.keys()
