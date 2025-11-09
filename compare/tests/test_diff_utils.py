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
