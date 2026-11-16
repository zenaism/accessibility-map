"""URL handling: one canonical form per page, scope rules, and guards against crawler traps."""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

TRACKING = re.compile(r"^(utm_.*|fbclid|gclid|mc_cid|mc_eid|igshid|_ga|ref|source|share)$", re.I)
INDEX_FILES = re.compile(r"/(index|default|home)\.(html?|php|aspx?)$", re.I)
DOC_EXT = (
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".csv",
    ".ics",
    ".json",
    ".geojson",
    ".kml",
)
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif")
SKIP_EXT = (
    ".zip", ".gz", ".tar", ".rar", ".7z", ".exe", ".dmg", ".iso", ".mp3", ".mp4", ".mov", ".avi", ".wmv",
    ".webm", ".css", ".js", ".woff", ".woff2", ".ttf", ".eot", ".svg", ".ico", ".xml", ".rss",
)  # fmt: skip
CALENDAR = re.compile(r"/(19|20)\d{2}/(0?[1-9]|1[0-2])(/\d{1,2})?(/|$)|[?&](date|month|year|day)=", re.I)
ACTION_PATHS = re.compile(
    r"/(login|logout|signin|signup|register|cart|checkout|wp-admin|wp-login|account|search)(/|$|\?)", re.I
)


def normalize(url: str, base: str | None = None) -> str | None:
    """Canonical form, or None for anything that is not a fetchable http(s) page address."""
    try:
        u = urljoin(base, url) if base else url
        p = urlsplit(u.strip())
        if p.scheme.lower() not in ("http", "https") or not p.hostname:
            return None
        host = p.hostname.lower().rstrip(".")
        port = f":{p.port}" if p.port and p.port not in (80, 443) else ""
        path = re.sub(r"/{2,}", "/", p.path or "/")
        path = INDEX_FILES.sub("/", path)
        query = sorted((k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not TRACKING.match(k))
        return urlunsplit((p.scheme.lower(), host + port, path, urlencode(query), ""))
    except ValueError:
        return None


def host_key(url_or_host: str) -> str:
    """Host without 'www.' and port, so www.example.org and example.org count as one site."""
    h = urlsplit(url_or_host if "//" in url_or_host else f"//{url_or_host}").hostname or ""
    return h.lower().removeprefix("www.")


def in_scope(url: str, hosts: set[str]) -> bool:
    return host_key(url) in hosts


def extension(url: str) -> str:
    path = urlsplit(url).path.lower()
    m = re.search(r"\.[a-z0-9]{2,5}$", path)
    return m.group(0) if m else ""


def kind(url: str) -> str:
    """page | document | image | skip, from the address alone."""
    e = extension(url)
    return "document" if e in DOC_EXT else "image" if e in IMG_EXT else "skip" if e in SKIP_EXT else "page"


def section(url: str) -> str:
    """First path segment: the unit of the per-section budget, so one big blog cannot starve the visit pages."""
    seg = [s for s in urlsplit(url).path.split("/") if s]
    return seg[0].lower() if seg else ""


def family_key(url: str) -> str:
    """First folder and path depth: pages of one kind on a site (all /restaurant/<name>/ pages) share a family."""
    segs = [s for s in urlsplit(url).path.split("/") if s]
    return f"{host_key(url)}/{segs[0].lower() if segs else ''}/{len(segs)}"


def pattern_key(url: str) -> str:
    """The URL with digits and query values blanked: URLs that differ only in a number or id share a key."""
    p = urlsplit(url)
    path = re.sub(r"\d+", "#", p.path)
    keys = ",".join(sorted({k for k, _ in parse_qsl(p.query, keep_blank_values=True)}))
    return f"{host_key(url)}{path}?{keys}"


LANGS = set(
    [
        "es",
        "am",
        "fr",
        "de",
        "it",
        "pt",
        "ru",
        "zh",
        "ko",
        "ja",
        "vi",
        "ar",
        "hi",
        "bn",
        "ur",
        "so",
        "ti",
        "ht",
        "pl",
        "tl",
        "uk",
        "fa",
        "tr",
        "he",
        "el",
        "nl",
        "sv",
        "no",
        "da",
        "fi",
        "cs",
        "hu",
        "ro",
        "th",
        "id",
        "ms",
        "sw",
        "ne",
        "my",
        "km",
        "lo",
    ]
)
LANG_PREFIX = re.compile(r"^/([a-z]{2})(?:-[a-z]{2,4})?(?:/|$)", re.I)


def language_prefix(url: str) -> str | None:
    """'es' for https://site/es/page (a translation copy under a language folder), else None."""
    m = LANG_PREFIX.match(urlsplit(url).path)
    return m.group(1).lower() if m and m.group(1).lower() in LANGS else None


def trap_reason(url: str, max_depth: int = 8, max_len: int = 300, strict: bool = True) -> str | None:
    """Why a URL looks like a crawler trap (calendar, endless parameters, repeated folders), else None."""
    p = urlsplit(url)
    segs = [s for s in p.path.split("/") if s]
    if len(url) > max_len:
        return "very long address"
    # Files legitimately live in deep folders (/sites/default/files/dc/sites/odr/...): depth and repetition only guard pages
    if strict and len(segs) > max_depth:
        return "path too deep"
    if strict and any(segs[i : i + 2] == segs[i + 2 : i + 4] for i in range(len(segs) - 3)):
        return "repeating folders"
    if CALENDAR.search(url):
        return "calendar or date archive"
    if len(parse_qsl(p.query)) > 4:
        return "too many parameters"
    if ACTION_PATHS.search(p.path + ("?" + p.query if p.query else "")):
        return "action page (login, cart, search)"
    return None
