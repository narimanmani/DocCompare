"""Utilities for building human-readable diffs between paragraph lists."""
from __future__ import annotations

import html
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, List, Sequence

from diff_match_patch import diff_match_patch

from .diff_links import diff_paragraph_links
from .html_tokens import Paragraph, Token
from .url_utils import UrlNormalizationOptions


@dataclass(slots=True)
class DiffComputationResult:
    """Represents the outcome of a diff computation."""

    html: str
    summary: dict[str, float | int]
    paragraphs: list[dict[str, object]]
    link_changes: list[dict[str, object]]

    def to_json(self) -> dict[str, object]:
        """Return a JSON-serializable structure."""
        return {
            "summary": self.summary,
            "paragraphs": self.paragraphs,
            "linkChanges": self.link_changes,
        }


@dataclass(slots=True)
class DiffOptions:
    """Subset of options needed for diff computation."""

    ignore_case: bool
    ignore_punctuation: bool
    ignore_whitespace: bool

    def normalize(self, text: str) -> str:
        """Normalize text according to the selected options."""

        processed = text
        if self.ignore_case:
            processed = processed.lower()
        if self.ignore_punctuation:
            processed = _strip_punctuation(processed)
        if self.ignore_whitespace:
            processed = _normalize_whitespace(processed)
        return processed


def _strip_punctuation(text: str) -> str:
    import re

    return re.sub(r"[^\w\s]", "", text)


def _normalize_whitespace(text: str) -> str:
    import re

    return re.sub(r"\s+", " ", text).strip()



_DIFF_PANEL_META: dict[str, tuple[str, str, str]] = {
    "equal": ("No change", "⏸", "Content matches in both documents."),
    "replace": ("Edited", "✏️", "Wording changed between documents."),
    "delete": ("Removed", "➖", "Missing from Document B."),
    "insert": ("Added", "➕", "New in Document B."),
    "default": ("Change", "✱", "Review this difference between the documents."),
}


def _render_diff_panel(panel_id: str, tag: str, left_html: str, right_html: str) -> str:
    """Render a diff block that places both versions side-by-side."""

    label, icon, description = _DIFF_PANEL_META.get(tag, _DIFF_PANEL_META["default"])
    safe_id = html.escape(panel_id, quote=True)
    icon_markup = html.escape(icon)
    label_markup = html.escape(label)
    description_markup = html.escape(description)
    return f"""
<section id='{safe_id}' class='diff-panel diff-panel--{tag}'>
    <header class='diff-panel__header'>
        <div class='diff-panel__meta'>
            <span class='diff-panel__icon' aria-hidden='true'>{icon_markup}</span>
            <div class='diff-panel__text'>
                <span class='diff-panel__label'>{label_markup}</span>
                <span class='diff-panel__description'>{description_markup}</span>
            </div>
        </div>
        <a class='diff-panel__anchor' href='#{safe_id}' aria-label='Copy link to this change'>¶</a>
    </header>
    <div class='diff-panel__columns'>
        <div class='diff-panel__column diff-panel__column--left'>
            <span class='diff-panel__column-title'>Document A</span>
            {left_html}
        </div>
        <div class='diff-panel__column diff-panel__column--right'>
            <span class='diff-panel__column-title'>Document B</span>
            {right_html}
        </div>
    </div>
</section>
""".strip()


def _word_diff(original_a: str, original_b: str) -> tuple[str, str, dict[str, int]]:
    """Return HTML fragments highlighting word-level changes."""

    dmp = diff_match_patch()
    dmp.Diff_Timeout = 0
    diffs = dmp.diff_main(original_a, original_b)
    dmp.diff_cleanupSemantic(diffs)

    html_a: List[str] = []
    html_b: List[str] = []
    stats = {"insertions": 0, "deletions": 0, "replacements": 0}

    for op, data in diffs:
        escaped = html.escape(data)
        if op == diff_match_patch.DIFF_EQUAL:
            html_a.append(escaped)
            html_b.append(escaped)
        elif op == diff_match_patch.DIFF_DELETE:
            html_a.append(f"<span class='diff-del'>{escaped}</span>")
            stats["deletions"] += len(data.split()) or 1
        elif op == diff_match_patch.DIFF_INSERT:
            html_b.append(f"<span class='diff-ins'>{escaped}</span>")
            stats["insertions"] += len(data.split()) or 1
        else:  # pragma: no cover - defensive
            stats["replacements"] += len(data.split()) or 1
    stats["replacements"] = min(stats["insertions"], stats["deletions"])
    return "".join(html_a), "".join(html_b), stats


def _paragraph_to_diff_string(paragraph: Paragraph) -> tuple[str, dict[str, tuple[int, Token]]]:
    placeholders: dict[str, tuple[int, Token]] = {}
    parts: list[str] = []
    for index, token in enumerate(paragraph.tokens):
        if token.type == "anchor":
            placeholder = f"[[ANCHOR-{index}]]"
            placeholders[placeholder] = (index, token)
            parts.append(placeholder)
        else:
            parts.append(token.text)
    return " ".join(part for part in parts if part), placeholders


def _render_anchor(token: Token, status: str | None, side: str) -> str:
    classes = ["diff-link"]
    if status:
        classes.append(status)
        classes.append(f"{status}-{side}")
    href = html.escape(token.href or "#")
    text = html.escape(token.text or (token.href or ""))
    title = html.escape(token.href or token.text or "")
    attrs = [f"class=\"{' '.join(classes)}\""]
    if href:
        attrs.append(f"href=\"{href}\"")
    if title:
        attrs.append(f"title=\"{title}\"")
    icon = ""
    if status in {"link-href-changed", "link-text-changed", "link-replaced"}:
        icon = "<span class='diff-link-icon' aria-hidden='true'>🔗</span>"
    inner_text = f"<span class='diff-link-text'>{text}</span>"
    return f"<a {' '.join(attrs)}>{icon}{inner_text}</a>"


def _inject_anchors(
    html_fragment: str,
    placeholders: dict[str, tuple[int, Token]],
    statuses: dict[int, str],
    side: str,
) -> str:
    result = html_fragment
    for placeholder, (index, token) in placeholders.items():
        markup = _render_anchor(token, statuses.get(index), side)
        result = result.replace(placeholder, markup)
    return result


def _render_plain_paragraph(paragraph: Paragraph, side: str) -> str:
    text, placeholders = _paragraph_to_diff_string(paragraph)
    escaped = html.escape(text)
    return _inject_anchors(escaped, placeholders, {}, side)


def _merge_paragraphs(paragraphs: Sequence[Paragraph]) -> Paragraph:
    if not paragraphs:
        return Paragraph(tokens=[])
    if len(paragraphs) == 1:
        return paragraphs[0]
    tokens: list[Token] = []
    for paragraph in paragraphs:
        tokens.extend(paragraph.tokens)
    return Paragraph(tokens=tokens)



def build_diff(
    paragraphs_a: Sequence[Paragraph],
    paragraphs_b: Sequence[Paragraph],
    options: DiffOptions,
    url_options: UrlNormalizationOptions,
) -> DiffComputationResult:
    """Build a diff between two paragraph sequences."""

    normalized_a = [options.normalize(p.text) for p in paragraphs_a]
    normalized_b = [options.normalize(p.text) for p in paragraphs_b]

    matcher = SequenceMatcher(a=normalized_a, b=normalized_b, autojunk=False)
    panels: list[str] = []
    details: list[dict[str, object]] = []
    link_records: list[dict[str, object]] = []

    totals = {"insertions": 0, "deletions": 0, "replacements": 0}
    link_totals = {
        "links_added": 0,
        "links_removed": 0,
        "links_changed_text": 0,
        "links_changed_href": 0,
    }
    total_paragraphs = max(len(paragraphs_a), len(paragraphs_b)) or 1

    for index, (tag, i1, i2, j1, j2) in enumerate(matcher.get_opcodes()):
        anchor = f"para-{index}"
        if tag == "equal":
            for offset, paragraph in enumerate(paragraphs_a[i1:i2]):
                counterpart = paragraphs_b[j1 + offset]
                row_id = f"{anchor}-{offset}"

                left_status, right_status, paragraph_records, counters = diff_paragraph_links(
                    row_id, paragraph, counterpart, url_options
                )
                for key, value in counters.items():
                    link_totals[key] += value
                link_records.extend(record.as_dict() for record in paragraph_records)

                left_string, left_placeholders = _paragraph_to_diff_string(paragraph)
                right_string, right_placeholders = _paragraph_to_diff_string(counterpart)

                html_left = _inject_anchors(
                    html.escape(left_string), left_placeholders, left_status, "left"
                )
                html_right = _inject_anchors(
                    html.escape(right_string), right_placeholders, right_status, "right"
                )

                panels.append(_render_diff_panel(row_id, "equal", html_left, html_right))
                details.append(
                    {
                        "anchor": row_id,
                        "type": "equal",
                        "left": paragraph.text,
                        "right": counterpart.text,
                        "links": [record.as_dict() for record in paragraph_records],
                    }
                )
        else:
            merged_left = _merge_paragraphs(paragraphs_a[i1:i2])
            merged_right = _merge_paragraphs(paragraphs_b[j1:j2])
            left_status, right_status, paragraph_records, counters = diff_paragraph_links(
                anchor, merged_left, merged_right, url_options
            )
            for key, value in counters.items():
                link_totals[key] += value
            link_records.extend(record.as_dict() for record in paragraph_records)

            left_string, left_placeholders = _paragraph_to_diff_string(merged_left)
            right_string, right_placeholders = _paragraph_to_diff_string(merged_right)
            html_left, html_right, stats = _word_diff(left_string, right_string)
            totals["insertions"] += stats["insertions"]
            totals["deletions"] += stats["deletions"]
            totals["replacements"] += stats["replacements"]

            html_left = _inject_anchors(html_left, left_placeholders, left_status, "left")
            html_right = _inject_anchors(html_right, right_placeholders, right_status, "right")

            panels.append(_render_diff_panel(anchor, tag, html_left, html_right))
            details.append(
                {
                    "anchor": anchor,
                    "type": tag,
                    "left": merged_left.text,
                    "right": merged_right.text,
                    "links": [record.as_dict() for record in paragraph_records],
                }
            )

    change_total = totals["insertions"] + totals["deletions"]
    percent_changed = (change_total / (total_paragraphs or 1)) * 100

    summary: dict[str, float | int] = {
        "insertions": totals["insertions"],
        "deletions": totals["deletions"],
        "replacements": totals["replacements"],
        "percent_changed": round(percent_changed, 2),
        **link_totals,
    }

    diff_markup: list[str] = [
        "<div class='diff-view'>",
        "<div class='diff-view__legend' aria-hidden='true'><span>Document A</span><span>Document B</span></div>",
    ]
    diff_markup.extend(panels)
    diff_markup.append("</div>")
    html_output = "\n".join(diff_markup)

    return DiffComputationResult(
        html=html_output,
        summary=summary,
        paragraphs=details,
        link_changes=link_records,
    )
