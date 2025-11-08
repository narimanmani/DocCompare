from __future__ import annotations

from compare.diff_links import diff_paragraph_links
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


def test_diff_paragraph_links_detects_href_change() -> None:
    options = UrlNormalizationOptions(
        ignore_protocol=True,
        drop_tracking_params=True,
        normalize_trailing_slash=True,
    )
    left = make_anchor("Docs", "http://example.com/path/?utm_source=newsletter")
    right = make_anchor("Docs", "https://example.com/path/")

    left_status, right_status, records, counters = diff_paragraph_links("p-1", left, right, options)

    assert counters["links_changed_href"] == 1
    assert not counters["links_changed_text"]
    assert left_status[0] == "link-href-changed"
    assert right_status[0] == "link-href-changed"
    assert records[0].type == "link-href-changed"
    assert "tracking params removed" in records[0].notes


def test_diff_paragraph_links_detects_text_change() -> None:
    options = UrlNormalizationOptions()
    left = make_anchor("Docs", "https://example.com/docs")
    right = make_anchor("Documentation", "https://example.com/docs")

    left_status, right_status, records, counters = diff_paragraph_links("p-2", left, right, options)

    assert counters["links_changed_text"] == 1
    assert left_status[0] == "link-text-changed"
    assert right_status[0] == "link-text-changed"
    assert records[0].type == "link-text-changed"
