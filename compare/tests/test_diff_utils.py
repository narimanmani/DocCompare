from __future__ import annotations

from compare.diff_utils import DiffOptions, build_diff
from compare.html_tokens import paragraphs_from_html
from compare.url_utils import UrlNormalizationOptions


def test_build_diff_detects_link_href_change_in_equal_paragraphs() -> None:
    left_html = "<p>Read the <a href='https://example.com/docs'>documentation</a>.</p>"
    right_html = "<p>Read the <a href='https://example.com/docs/v2'>documentation</a>.</p>"

    paragraphs_a = paragraphs_from_html(left_html)
    paragraphs_b = paragraphs_from_html(right_html)

    result = build_diff(
        paragraphs_a,
        paragraphs_b,
        DiffOptions(ignore_case=False, ignore_punctuation=False, ignore_whitespace=False),
        UrlNormalizationOptions(),
    )

    assert result.summary["links_changed_href"] == 1
    assert len(result.link_changes) == 1
    assert result.link_changes[0]["type"] == "link-href-changed"
    assert "link-href-changed" in result.html
    assert "diff-link-href'>https://example.com/docs/v2" in result.html


def test_build_diff_marks_link_additions_in_equal_segments() -> None:
    left_html = "<p>Visit example</p>"
    right_html = "<p>Visit <a href='https://example.com'>example</a></p>"

    paragraphs_a = paragraphs_from_html(left_html)
    paragraphs_b = paragraphs_from_html(right_html)

    result = build_diff(
        paragraphs_a,
        paragraphs_b,
        DiffOptions(ignore_case=False, ignore_punctuation=False, ignore_whitespace=False),
        UrlNormalizationOptions(),
    )

    assert result.summary["links_added"] == 1
    assert any(record["type"] == "link-added" for record in result.link_changes)
    assert "diff-panel--link-change" in result.html
    assert "diff-link-href'>https://example.com" in result.html


def test_build_diff_flags_text_differences_hidden_by_normalization() -> None:
    left_html = "<p>Nav Canada</p>"
    right_html = "<p>NAV CANADA</p>"

    paragraphs_a = paragraphs_from_html(left_html)
    paragraphs_b = paragraphs_from_html(right_html)

    result = build_diff(
        paragraphs_a,
        paragraphs_b,
        DiffOptions(ignore_case=True, ignore_punctuation=False, ignore_whitespace=False),
        UrlNormalizationOptions(),
    )

    assert result.summary["replacements"] >= 1
    assert "diff-panel--replace" in result.html


def test_build_diff_preserves_links_when_anchor_indices_shift() -> None:
    left_html = "<p><a href='https://old.example.com'>Docs</a> are here.</p>"
    right_html = "<p>Read the <a href='https://new.example.com'>Docs</a> now.</p>"

    paragraphs_a = paragraphs_from_html(left_html)
    paragraphs_b = paragraphs_from_html(right_html)

    result = build_diff(
        paragraphs_a,
        paragraphs_b,
        DiffOptions(ignore_case=False, ignore_punctuation=False, ignore_whitespace=False),
        UrlNormalizationOptions(),
    )

    assert "[[ANCHOR" not in result.html
    assert "https://old.example.com" in result.html
    assert "https://new.example.com" in result.html
