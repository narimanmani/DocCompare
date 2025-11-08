"""Utilities for URL canonicalization used in link-aware diffs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from urllib.parse import ParseResult, parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_DENYLIST = {"gclid", "fbclid", "mc_eid", "msclkid"}


@dataclass(slots=True)
class UrlNormalizationOptions:
    """Configuration flags for canonicalizing URLs."""

    ignore_protocol: bool = False
    normalize_trailing_slash: bool = False
    lowercase_host: bool = False
    drop_tracking_params: bool = False
    strip_fragment: bool = False


@dataclass(slots=True)
class CanonicalizedUrl:
    """Represents the canonical form of a URL and transformation notes."""

    original: str
    canonical: str
    notes: list[str]


def _rebuild_netloc(parts: ParseResult, lowercase_host: bool) -> str:
    username = parts.username or ""
    password = parts.password or ""
    hostname = (parts.hostname or "").lower() if lowercase_host else (parts.hostname or "")

    credentials = username
    if password:
        credentials = f"{credentials}:{password}" if credentials else password

    host_port = hostname
    if parts.port:
        host_port = f"{host_port}:{parts.port}"

    if credentials and host_port:
        return f"{credentials}@{host_port}"
    return host_port


def _filter_query(params: Iterable[tuple[str, str]], drop_tracking: bool) -> tuple[list[tuple[str, str]], list[str]]:
    notes: list[str] = []
    filtered: list[tuple[str, str]] = []
    for key, value in params:
        key_lower = key.lower()
        if drop_tracking and (key_lower.startswith("utm_") or key_lower in _TRACKING_DENYLIST):
            if "tracking params removed" not in notes:
                notes.append("tracking params removed")
            continue
        filtered.append((key, value))
    return filtered, notes


def canonicalize_url(url: str, opts: UrlNormalizationOptions) -> CanonicalizedUrl:
    """Return a canonical version of ``url`` according to ``opts``."""

    url = url or ""
    try:
        parts = urlsplit(url)
    except ValueError:
        return CanonicalizedUrl(original=url, canonical=url, notes=[])

    scheme = parts.scheme
    notes: list[str] = []

    if opts.ignore_protocol and scheme:
        scheme = ""
        notes.append("protocol normalized")
    elif scheme:
        scheme = scheme.lower()

    netloc = parts.netloc
    if opts.lowercase_host and parts.hostname:
        lowered = _rebuild_netloc(parts, lowercase_host=True)
        if lowered != netloc:
            notes.append("host lowercased")
        netloc = lowered

    path = parts.path or ""
    if opts.normalize_trailing_slash and path not in {"", "/"}:
        trimmed = path.rstrip("/")
        if not trimmed:
            trimmed = "/"
        if trimmed != path:
            notes.append("trailing slash normalized")
        path = trimmed

    query_pairs = parse_qsl(parts.query, keep_blank_values=True)
    if opts.drop_tracking_params and query_pairs:
        query_pairs, query_notes = _filter_query(query_pairs, drop_tracking=True)
        notes.extend(query_notes)
    query = urlencode(query_pairs, doseq=True)

    fragment = parts.fragment
    if opts.strip_fragment and fragment:
        fragment = ""
        notes.append("fragment stripped")

    canonical = urlunsplit((scheme, netloc, path, query, fragment))
    return CanonicalizedUrl(original=url, canonical=canonical, notes=notes)
