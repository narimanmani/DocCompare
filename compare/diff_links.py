"""Link-aware diff helpers integrated with the broader diff pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Dict, Iterable, List, Tuple

from .html_tokens import Paragraph, Token
from .url_utils import CanonicalizedUrl, UrlNormalizationOptions, canonicalize_url


@dataclass(slots=True)
class AnchorInfo:
    """Information about an anchor token within a paragraph."""

    index: int
    token: Token
    canonical: CanonicalizedUrl


@dataclass(slots=True)
class LinkDiffRecord:
    """Structured representation of a single link change."""

    type: str
    para_id: str
    before: dict[str, str] | None
    after: dict[str, str] | None
    notes: list[str]

    def as_dict(self) -> dict[str, object]:
        data: dict[str, object] = {"type": self.type, "paraId": self.para_id, "notes": self.notes}
        if self.before is not None:
            data["before"] = self.before
        if self.after is not None:
            data["after"] = self.after
        return data


LinkStatusMap = Dict[int, str]
LinkCounters = Dict[str, int]


def _gather_anchors(paragraph: Paragraph, options: UrlNormalizationOptions) -> list[AnchorInfo]:
    infos: list[AnchorInfo] = []
    for index, token in enumerate(paragraph.tokens):
        if token.type != "anchor":
            continue
        canonical = canonicalize_url(token.href or "", options)
        if not (token.href or "").strip():
            if "missing href" not in canonical.notes:
                canonical.notes.append("missing href")
        if not (token.text or "").strip():
            if "missing text" not in canonical.notes:
                canonical.notes.append("missing text")
        infos.append(
            AnchorInfo(
                index=index,
                token=token,
                canonical=canonical,
            )
        )
    return infos


def _payload(token: Token) -> dict[str, str]:
    return {"text": token.text, "href": token.href or ""}


def _merge_notes(left: CanonicalizedUrl | None, right: CanonicalizedUrl | None) -> list[str]:
    notes: list[str] = []
    for source in (left, right):
        if not source:
            continue
        for note in source.notes:
            if note not in notes:
                notes.append(note)
    return notes


def _classify_pair(
    para_id: str,
    left: AnchorInfo,
    right: AnchorInfo,
    counters: LinkCounters,
    records: List[LinkDiffRecord],
    left_status: LinkStatusMap,
    right_status: LinkStatusMap,
) -> None:
    raw_left = left.token.href or ""
    raw_right = right.token.href or ""
    canonical_changed = left.canonical.canonical != right.canonical.canonical
    href_changed = canonical_changed or raw_left != raw_right
    text_changed = left.token.text != right.token.text

    if not href_changed and not text_changed:
        return

    if href_changed and text_changed:
        change_type = "link-replaced"
        counters["links_changed_href"] += 1
        counters["links_changed_text"] += 1
    elif href_changed:
        change_type = "link-href-changed"
        counters["links_changed_href"] += 1
    else:
        change_type = "link-text-changed"
        counters["links_changed_text"] += 1

    notes = _merge_notes(left.canonical, right.canonical)
    records.append(
        LinkDiffRecord(
            type=change_type,
            para_id=para_id,
            before=_payload(left.token),
            after=_payload(right.token),
            notes=notes,
        )
    )
    left_status[left.index] = change_type
    right_status[right.index] = change_type


def diff_paragraph_links(
    para_id: str,
    left: Paragraph,
    right: Paragraph,
    options: UrlNormalizationOptions,
) -> tuple[LinkStatusMap, LinkStatusMap, list[LinkDiffRecord], LinkCounters]:
    """Return per-anchor statuses, structured records, and counters for a paragraph."""

    left_infos = _gather_anchors(left, options)
    right_infos = _gather_anchors(right, options)

    counters: LinkCounters = {
        "links_added": 0,
        "links_removed": 0,
        "links_changed_text": 0,
        "links_changed_href": 0,
    }
    records: list[LinkDiffRecord] = []
    left_status: LinkStatusMap = {}
    right_status: LinkStatusMap = {}

    if not left_infos and not right_infos:
        return left_status, right_status, records, counters

    left_keys = [info.canonical.canonical for info in left_infos]
    right_keys = [info.canonical.canonical for info in right_infos]
    matcher = SequenceMatcher(a=left_keys, b=right_keys, autojunk=False)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        left_segment = left_infos[i1:i2]
        right_segment = right_infos[j1:j2]

        if tag == "equal":
            for l_info, r_info in zip(left_segment, right_segment):
                _classify_pair(para_id, l_info, r_info, counters, records, left_status, right_status)
        elif tag == "replace":
            for l_info, r_info in zip(left_segment, right_segment):
                _classify_pair(para_id, l_info, r_info, counters, records, left_status, right_status)
            if len(left_segment) > len(right_segment):
                for extra in left_segment[len(right_segment) :]:
                    counters["links_removed"] += 1
                    records.append(
                        LinkDiffRecord(
                            type="link-removed",
                            para_id=para_id,
                            before=_payload(extra.token),
                            after=None,
                            notes=extra.canonical.notes,
                        )
                    )
                    left_status[extra.index] = "link-removed"
            elif len(right_segment) > len(left_segment):
                for extra in right_segment[len(left_segment) :]:
                    counters["links_added"] += 1
                    records.append(
                        LinkDiffRecord(
                            type="link-added",
                            para_id=para_id,
                            before=None,
                            after=_payload(extra.token),
                            notes=extra.canonical.notes,
                        )
                    )
                    right_status[extra.index] = "link-added"
        elif tag == "delete":
            for extra in left_segment:
                counters["links_removed"] += 1
                records.append(
                    LinkDiffRecord(
                        type="link-removed",
                        para_id=para_id,
                        before=_payload(extra.token),
                        after=None,
                        notes=extra.canonical.notes,
                    )
                )
                left_status[extra.index] = "link-removed"
        elif tag == "insert":
            for extra in right_segment:
                counters["links_added"] += 1
                records.append(
                    LinkDiffRecord(
                        type="link-added",
                        para_id=para_id,
                        before=None,
                        after=_payload(extra.token),
                        notes=extra.canonical.notes,
                    )
                )
                right_status[extra.index] = "link-added"

    return left_status, right_status, records, counters
