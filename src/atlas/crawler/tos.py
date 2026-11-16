"""Terms-of-use check: a site whose terms forbid automated access is not crawled (docs/compliance.md).

The crawler fetches a site's usual terms pages, and `forbids_bots` looks for wording that prohibits robots, scraping or
automated collection. A match stops the crawl of that site and lists it in `tos_report.json` so a person can ask for permission.
A site the lab has permission for goes into the spec's `tos_allow` list; known-bad sites go into `tos_restricted`.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

TERMS_PATHS = [
    "/terms",
    "/terms-of-use",
    "/terms-of-service",
    "/terms-and-conditions",
    "/legal",
    "/legal/terms",
]
TERMS_URL = re.compile(r"/(terms|tos|legal|conditions|user-agreement|website-use|site-use)([-_/.]|$)", re.I)
ACTION = r"(?:scrap\w+|crawl\w*|spider\w*|robots?|bots?|data[- ]min\w+|harvest\w*|automated (?:means|tools?|access|queries|collection|systems?)|screen[- ]scrap\w+)"
PROHIBIT = r"(?:may not|must not|shall not|not (?:to|permitted|allowed)|prohibit\w*|forbid\w*|unauthori[sz]ed|without (?:our |prior |express |written )+(?:consent|permission)|no )"
# a prohibition and an automated-access word in the same sentence
SENTENCE = re.compile(rf"[^.\n]*(?:{PROHIBIT}[^.\n]*{ACTION}|{ACTION}[^.\n]*{PROHIBIT})[^.\n]*", re.I)
SAFE = re.compile(r"robots-file|search engine", re.I)  # "you may not ignore our robots.txt" is not a ban


def is_terms_url(url: str) -> bool:
    return bool(TERMS_URL.search(urlsplit(url).path))


def forbids_bots(text: str) -> str | None:
    """The first sentence that forbids automated access, or None."""
    for m in SENTENCE.finditer(
        re.sub(r"robots\.txt", "robots-file", text, flags=re.I)
    ):  # the dot is not a sentence end
        s = " ".join(m.group(0).split())
        if len(s) <= 500 and not SAFE.search(s):
            return s
    return None
