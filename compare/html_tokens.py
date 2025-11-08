"""Utilities for turning HTML into structured text and link tokens."""
from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Iterable, Iterator, List, Literal, Sequence

try:  # pragma: no cover - optional dependency shim
    from bs4 import BeautifulSoup, NavigableString, Tag  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - executed when bs4 unavailable
    BeautifulSoup = None  # type: ignore
    NavigableString = str  # type: ignore
    Tag = object  # type: ignore


TokenType = Literal["text", "anchor"]


@dataclass(slots=True)
class Token:
    """Represents a text or anchor token extracted from HTML."""

    type: TokenType
    text: str
    href: str | None = None
    attrs: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        data: dict[str, object] = {"type": self.type, "text": self.text}
        if self.type == "anchor":
            data["href"] = self.href or ""
            data["attrs"] = dict(self.attrs)
        return data


@dataclass(slots=True)
class Paragraph:
    """A paragraph represented as a sequence of tokens."""

    tokens: list[Token]

    @property
    def text(self) -> str:
        return " ".join(token.text for token in self.tokens).strip()

    def as_dict(self) -> list[dict[str, object]]:
        return [token.as_dict() for token in self.tokens]


_BLOCK_TAGS = {
    "p",
    "li",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "blockquote",
    "pre",
}

_ANCHOR_ATTRS = ("title", "target", "rel")


def _normalize_text(text: str) -> str:
    return " ".join(text.split())


def _iter_tokens(node: Tag) -> Iterator[Token]:
    for child in getattr(node, "children", []):
        if BeautifulSoup is not None and isinstance(child, NavigableString):
            text = _normalize_text(str(child))
            if text:
                yield Token(type="text", text=text)
        elif BeautifulSoup is not None and isinstance(child, Tag):
            if child.name == "a":
                yield _anchor_token(child)
            else:
                yield from _iter_tokens(child)


def _anchor_token(tag: Tag) -> Token:
    text = _normalize_text(tag.get_text(" ", strip=True))
    attrs: dict[str, str] = {}
    for attr in _ANCHOR_ATTRS:
        if attr in tag.attrs and tag.attrs[attr]:
            value = tag.attrs[attr]
            if isinstance(value, list):
                attrs[attr] = " ".join(str(item) for item in value)
            else:
                attrs[attr] = str(value)
    href = tag.get("href") or ""
    return Token(type="anchor", text=text, href=href, attrs=attrs)


def _is_meaningful(paragraph: Sequence[Token]) -> bool:
    if not paragraph:
        return False
    if any(token.type == "anchor" for token in paragraph):
        return True
    return any(token.text.strip() for token in paragraph)


class _FallbackHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._blocks: list[list[Token]] = []
        self._anchors: list[dict[str, object]] = []
        self.paragraphs: list[Paragraph] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _BLOCK_TAGS:
            self._blocks.append([])
        elif tag == "a" and self._blocks:
            attr_map = {key: value or "" for key, value in attrs}
            self._anchors.append({"attrs": attr_map, "text_parts": []})

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._anchors and self._blocks:
            info = self._anchors.pop()
            text = _normalize_text(" ".join(info["text_parts"]))
            attrs = {}
            for attr in _ANCHOR_ATTRS:
                value = info["attrs"].get(attr)
                if value:
                    attrs[attr] = value
            href = info["attrs"].get("href", "")
            self._blocks[-1].append(Token(type="anchor", text=text, href=href, attrs=attrs))
        elif tag in _BLOCK_TAGS and self._blocks:
            tokens = self._blocks.pop()
            if _is_meaningful(tokens):
                self.paragraphs.append(Paragraph(tokens=tokens))

    def handle_data(self, data: str) -> None:
        text = _normalize_text(data)
        if not text:
            return
        if self._anchors:
            self._anchors[-1]["text_parts"].append(text)
        elif self._blocks:
            self._blocks[-1].append(Token(type="text", text=text))

    def close(self) -> None:
        super().close()
        while self._blocks:
            tokens = self._blocks.pop()
            if _is_meaningful(tokens):
                self.paragraphs.append(Paragraph(tokens=tokens))


def _fallback_paragraphs_from_html(html: str) -> list[Paragraph]:
    parser = _FallbackHTMLParser()
    parser.feed(html)
    parser.close()
    return parser.paragraphs


def paragraphs_from_html(html: str) -> list[Paragraph]:
    """Parse HTML into a list of Paragraph instances."""

    if BeautifulSoup is None:  # pragma: no cover - exercised in dependency-free environments
        return _fallback_paragraphs_from_html(html)

    soup = BeautifulSoup(html, "lxml")
    container: Tag | None = soup.body if soup.body else soup
    tokens: List[Paragraph] = []

    if not container:
        return []

    for block in container.find_all(_BLOCK_TAGS):
        paragraph_tokens = list(_iter_tokens(block))
        if _is_meaningful(paragraph_tokens):
            tokens.append(Paragraph(tokens=paragraph_tokens))

    if tokens:
        return tokens

    text = _normalize_text(container.get_text(" ", strip=True))
    if text:
        return [Paragraph(tokens=[Token(type="text", text=text)])]
    return []


def paragraphs_from_text(paragraphs: Iterable[str]) -> list[Paragraph]:
    """Convert plain text paragraphs into Paragraph objects."""

    return [
        Paragraph(tokens=[Token(type="text", text=_normalize_text(paragraph))])
        for paragraph in paragraphs
        if paragraph.strip()
    ]
