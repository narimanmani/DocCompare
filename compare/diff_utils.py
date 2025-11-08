"""Utilities for building human-readable diffs between paragraph lists."""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, List, Sequence

from diff_match_patch import diff_match_patch


@dataclass(slots=True)
class DiffComputationResult:
    """Represents the outcome of a diff computation."""

    html: str
    summary: dict[str, float]
    paragraphs: list[dict[str, object]]

    def to_json(self) -> dict[str, object]:
        """Return a JSON-serializable structure."""
        return {
            "summary": self.summary,
            "paragraphs": self.paragraphs,
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
            processed = re.sub(r"[^\w\s]", "", processed)
        if self.ignore_whitespace:
            processed = re.sub(r"\s+", " ", processed).strip()
        return processed


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


def build_diff(paragraphs_a: Sequence[str], paragraphs_b: Sequence[str], options: DiffOptions) -> DiffComputationResult:
    """Build a diff between two paragraph sequences."""

    normalized_a = [options.normalize(p) for p in paragraphs_a]
    normalized_b = [options.normalize(p) for p in paragraphs_b]

    matcher = SequenceMatcher(a=normalized_a, b=normalized_b, autojunk=False)
    rows: list[str] = []
    details: list[dict[str, object]] = []

    totals = {"insertions": 0, "deletions": 0, "replacements": 0}
    total_paragraphs = max(len(paragraphs_a), len(paragraphs_b)) or 1

    for index, (tag, i1, i2, j1, j2) in enumerate(matcher.get_opcodes()):
        anchor = f"para-{index}"
        if tag == "equal":
            for offset, paragraph in enumerate(paragraphs_a[i1:i2], start=0):
                original = html.escape(paragraph)
                rows.append(
                    f"<tr id='{anchor}-{offset}'><td>{original}</td><td>{original}</td></tr>"
                )
                details.append(
                    {
                        "anchor": f"{anchor}-{offset}",
                        "type": "equal",
                        "left": paragraph,
                        "right": paragraph,
                    }
                )
        else:
            block_a = "\n".join(paragraphs_a[i1:i2])
            block_b = "\n".join(paragraphs_b[j1:j2])
            html_a, html_b, stats = _word_diff(block_a, block_b)
            totals["insertions"] += stats["insertions"]
            totals["deletions"] += stats["deletions"]
            totals["replacements"] += stats["replacements"]
            rows.append(
                f"<tr id='{anchor}' class='diff-{tag}'><td>{html_a}</td><td>{html_b}</td></tr>"
            )
            details.append(
                {
                    "anchor": anchor,
                    "type": tag,
                    "left": block_a,
                    "right": block_b,
                }
            )

    change_total = totals["insertions"] + totals["deletions"]
    percent_changed = (change_total / (total_paragraphs or 1)) * 100

    summary = {
        "insertions": totals["insertions"],
        "deletions": totals["deletions"],
        "replacements": totals["replacements"],
        "percent_changed": round(percent_changed, 2),
    }

    table_html = """
    <table class="diff-table">
        <thead>
            <tr><th>Document A</th><th>Document B</th></tr>
        </thead>
        <tbody>
    """
    table_html += "".join(rows)
    table_html += "</tbody></table>"

    return DiffComputationResult(html=table_html, summary=summary, paragraphs=details)
