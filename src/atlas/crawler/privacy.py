"""Remove personal data from crawled text before it is stored in the documents table (docs/compliance.md).

Kept: role addresses (info@, accessibility@, ada@ ...) and business phone numbers, which are public contact points for a place
and are the kind of fact the assistant needs. Removed: personal-looking email addresses (name@...) and phone numbers marked
as cell, mobile, home or personal. Raw page files stay on the researcher's machine and are not published.
"""

from __future__ import annotations

import json
import re

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
ROLE = re.compile(
    r"^(info|contact|hello|help|support|admin|office|ada\w*|access\w*|disab\w*|events?|reservations?|"
    r"customer\w*|service\w*|webmaster|reception|front\w*|visit\w*|tours?|tickets?|box\w*|parking|transit|feedback|inquir\w*|"
    r"media|press|sales|booking|concierge|guest\w*)([._-]\w+)?$",
    re.I,
)
PERSONAL_PHONE = re.compile(
    r"(?i)\b(?:cell|mobile|home|personal|private)\b[^\n]{0,20}?(?:\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})"
)


def _email(m: re.Match) -> str:
    return m.group(0) if ROLE.match(m.group(0).split("@")[0]) else "[email removed]"


def scrub(text: str) -> str:
    text = EMAIL.sub(_email, text)
    return PERSONAL_PHONE.sub("[phone removed]", text)


def scrub_json(s: str) -> str:
    """The nested JSON columns (sections, tables, snippets ...): scrub every string inside."""

    def walk(x):
        if isinstance(x, str):
            return scrub(x)
        if isinstance(x, list):
            return [walk(i) for i in x]
        if isinstance(x, dict):
            return {k: walk(v) for k, v in x.items()}
        return x

    try:
        return json.dumps(walk(json.loads(s)), ensure_ascii=False)
    except ValueError:
        return scrub(s)


def scrub_row(row: dict) -> dict:
    for k in ("title", "text"):
        if isinstance(row.get(k), str):
            row[k] = scrub(row[k])
    for k in ("sections", "tables", "structured", "access_snippets", "description"):
        if isinstance(row.get(k), str):
            row[k] = scrub_json(row[k])
    return row
