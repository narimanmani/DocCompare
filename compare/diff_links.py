"""Link comparison helpers focused on matching anchor text across documents."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Sequence

from .html_tokens import Paragraph
from .url_utils import UrlNormalizationOptions, canonicalize_url


@dataclass(slots=True)
class AnchorOccurrence:
    """Represents a single hyperlink encountered in a paragraph."""

    paragraph_index: int
    token_index: int
    text: str
    href: str
    normalized_href: str


@dataclass(slots=True)
class LinkComparisonRecord:
    """Matched hyperlink text across both documents."""

    text: str
    left_href: str
    right_href: str
    left_paragraph: int
    right_paragraph: int
    changed: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "text": self.text,
            "leftHref": self.left_href,
            "rightHref": self.right_href,
            "leftParagraph": self.left_paragraph,
            "rightParagraph": self.right_paragraph,
            "changed": self.changed,
        }


def _collect_anchor_occurrences(
    paragraphs: Sequence[Paragraph],
    options: UrlNormalizationOptions,
) -> list[AnchorOccurrence]:
    occurrences: list[AnchorOccurrence] = []
    for paragraph_index, paragraph in enumerate(paragraphs):
        for token_index, token in enumerate(paragraph.tokens):
            if token.type != "anchor":
                continue
            text = (token.text or "").strip()
            if not text:
                continue
            href = token.href or ""
            normalized = canonicalize_url(href, options).canonical if href else ""
            occurrences.append(
                AnchorOccurrence(
                    paragraph_index=paragraph_index,
                    token_index=token_index,
                    text=text,
                    href=href,
                    normalized_href=normalized,
                )
            )
    return occurrences


def compare_links_by_text(
    left_paragraphs: Sequence[Paragraph],
    right_paragraphs: Sequence[Paragraph],
    options: UrlNormalizationOptions,
) -> tuple[dict[int, dict[int, str]], dict[int, dict[int, str]], list[LinkComparisonRecord]]:
    """Match hyperlinks by text and report differing destinations."""

    left_occurrences = _collect_anchor_occurrences(left_paragraphs, options)
    right_occurrences = _collect_anchor_occurrences(right_paragraphs, options)

    right_by_text: dict[str, deque[AnchorOccurrence]] = defaultdict(deque)
    for occurrence in right_occurrences:
        right_by_text[occurrence.text].append(occurrence)

    left_statuses: dict[int, dict[int, str]] = defaultdict(dict)
    right_statuses: dict[int, dict[int, str]] = defaultdict(dict)
    records: list[LinkComparisonRecord] = []

    for left_occurrence in left_occurrences:
        candidates = right_by_text.get(left_occurrence.text)
        if not candidates:
            continue
        right_occurrence = candidates.popleft()
        raw_changed = left_occurrence.href != right_occurrence.href
        normalized_changed = (
            left_occurrence.normalized_href != right_occurrence.normalized_href
        )
        changed = raw_changed or normalized_changed
        if changed:
            left_statuses[left_occurrence.paragraph_index][left_occurrence.token_index] = "link-href-changed"
            right_statuses[right_occurrence.paragraph_index][right_occurrence.token_index] = "link-href-changed"
        records.append(
            LinkComparisonRecord(
                text=left_occurrence.text,
                left_href=left_occurrence.href,
                right_href=right_occurrence.href,
                left_paragraph=left_occurrence.paragraph_index,
                right_paragraph=right_occurrence.paragraph_index,
                changed=changed,
            )
        )

    return (
        {index: dict(statuses) for index, statuses in left_statuses.items()},
        {index: dict(statuses) for index, statuses in right_statuses.items()},
        records,
    )
