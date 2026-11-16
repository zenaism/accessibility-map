"""How likely a page is to hold accessibility information, from cheap signals (no model needed).

The words come from config/categories.yaml (`page_words`), so adding a category teaches the crawler what to look for.
Scores are 0 to 1; the crawler fetches the highest scores first (best-first), within a budget.
"""

from __future__ import annotations

import re
from functools import cache
from urllib.parse import urlsplit

from ..core import config

# path fragments that usually lead to access, visit, parking and event information, with a weight
PATH_HINTS = {
    "accessib": 0.55, "/ada": 0.45, "wheelchair": 0.5, "disab": 0.35, "plan-your-visit": 0.35, "planyourvisit": 0.35,
    "visit": 0.25, "parking": 0.35, "directions": 0.25, "getting-here": 0.25, "events": 0.2, "calendar": 0.1,
    "trail": 0.25, "map": 0.2, "guide": 0.2, "faq": 0.2, "transit": 0.2, "restroom": 0.3, "sensory": 0.3,
}  # fmt: skip
AVOID = re.compile(
    r"/(tag|tags|author|category|feed|wp-json|comments?|archive|press|careers?|jobs|donate|shop|store)(/|$)",
    re.I,
)
PROBE_PATHS = [
    "/accessibility", "/ada", "/visit", "/plan-your-visit", "/parking", "/directions", "/events", "/faq", "/visitor-information",
]  # fmt: skip


@cache
def keywords() -> tuple[str, ...]:
    words = {w.lower() for c in config("categories").values() for w in c.get("page_words", [])}
    return tuple(sorted(words, key=len, reverse=True))


def _hits(text: str) -> int:
    t = text.lower().replace("-", " ").replace("_", " ")
    return sum(1 for w in keywords() if w in t)


def score_url(url: str, anchor: str = "", parent: float = 0.0) -> float:
    """Score before fetching: words in the address and link text, path hints, and how relevant the linking page was."""
    path = urlsplit(url).path.lower()
    s = 0.15 * min(_hits(path), 3) + 0.2 * min(_hits(anchor), 3)
    s += max((w for k, w in PATH_HINTS.items() if k in path), default=0.0)
    if path.endswith((".pdf", ".docx")) and (_hits(path) or _hits(anchor)):
        s += 0.2  # an access guide as a document is worth more than a blog post
    if AVOID.search(path):
        s -= 0.3
    return round(max(0.0, min(1.0, s + 0.3 * parent)), 3)


def score_text(text: str) -> float:
    """Score after fetching: how many of our words appear, scaled by how long the page is."""
    if not text:
        return 0.0
    words = max(len(text.split()), 1)
    return round(min(1.0, _hits(text) * 1000 / words / 6), 3)


LISTING = re.compile(
    r"/(page|p)/\d+|[?&]page=\d+|/category/|/directory|/listings?(/|$)|/browse|/all(/|$)", re.I
)
LISTING_WORDS = ("next", "older", "more", "load more", "view all", "see all")


def is_listing(url: str, anchor: str = "") -> bool:
    """Directory, category and pagination pages: they are the way to the individual entries."""
    return bool(LISTING.search(url)) or anchor.strip().lower() in LISTING_WORDS


def priority(score: float, boost: int = 0) -> int:
    return int(score * 100) + boost
