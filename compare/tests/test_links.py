from __future__ import annotations

from compare.diff_links import compare_links_by_text
from compare.html_tokens import Paragraph, Token
from compare.url_utils import UrlNormalizationOptions, canonicalize_url


def make_anchor(text: str, href: str) -> Paragraph:
    return Paragraph(tokens=[Token(type="anchor", text=text, href=href)])


def test_canonicalize_url_drops_tracking_params() -> None:
    options = UrlNormalizationOptions(
        drop_tracking_params=True,
        ignore_protocol=True,
        normalize_trailing_slash=True,
        strip_fragment=True,
    )
    result = canonicalize_url("https://example.com/docs/?utm_source=test&utm_medium=email#intro", options)
    assert result.canonical == "//example.com/docs"
    assert "tracking params removed" in result.notes
    assert "protocol normalized" in result.notes


def test_compare_links_by_text_detects_href_change() -> None:
    options = UrlNormalizationOptions(
        ignore_protocol=True,
        drop_tracking_params=True,
        normalize_trailing_slash=True,
    )
    left = [make_anchor("Docs", "http://example.com/path/?utm_source=newsletter")]
    right = [make_anchor("Docs", "https://example.com/path/")]

    left_statuses, right_statuses, records = compare_links_by_text(left, right, options)

    assert records
    assert records[0].text == "Docs"
    assert records[0].changed is True
    assert records[0].left_href == "http://example.com/path/?utm_source=newsletter"
    assert records[0].right_href == "https://example.com/path/"
    assert left_statuses[0][0] == "link-href-changed"
    assert right_statuses[0][0] == "link-href-changed"


def test_compare_links_by_text_marks_unchanged_links() -> None:
    options = UrlNormalizationOptions()
    left = [make_anchor("Docs", "https://example.com/docs")]
    right = [make_anchor("Docs", "https://example.com/docs")]

    left_statuses, right_statuses, records = compare_links_by_text(left, right, options)

    assert records
    assert records[0].changed is False
    assert left_statuses == {}
    assert right_statuses == {}
