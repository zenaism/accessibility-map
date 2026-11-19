"""Remove personal data from crawled text before it is stored in the documents table (docs/compliance.md).

Kept: role addresses (info@, accessibility@, ada@ ...) and business phone numbers, which are public contact points for a place
and are the kind of fact the assistant needs. Removed: personal-looking email addresses (name@...) and phone numbers marked
as cell, mobile, home or personal. Raw page files stay on the researcher's machine and are not published.
"""

from __future__ import annotations

import json
import re

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# A role address names a job or a service, not a person. Every part of the local name (split at . _ -) must be on this list:
# "adam@" and "help.jsmith@" are people and are removed.
ROLE_WORD = re.compile(
    r"(?:info|information|contact|hello|help|support|admin|office|events?|reservations?|customers?|service|services|"
    r"webmaster|reception|front|desk|visitors?|visit|tours?|tickets?|box|parking|transit|feedback|inquiries|inquiry|media|press|"
    r"sales|booking|concierge|guest|guests|care|team|"
    r"ada|adacoordinator|adaoffice|adainfo|adaservices?|access|accessibility|accessinfo|accessservices?|accessoffice|"
    r"disabilit(?:y|ies)|disabilityservices|disabilityoffice|disabilityaccess|\d{1,3})",
    re.I,
)
WORDS = re.compile(r"[._-]")
PHONE_NUM = r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}"
LABEL = r"(?:cell|mobile|home|personal|private)"
# "Cell: 614-555-0100", "Mobile phone 614...", and "614-555-0100 (cell)"; "Home | Contact (614)..." is a menu, not a label
PERSONAL_PHONE = re.compile(
    rf"(?i)\b{LABEL}\b(?:\s+(?:phone|number|tel\w*))?\s*[:#\-–]?\s*{PHONE_NUM}|{PHONE_NUM}\s*[\[(]?\s*{LABEL}\b[\])]?"
)
# a mail address broken over two lines (PDF layout) is joined before it is read
BROKEN_EMAIL = re.compile(r"([\w.%+-])[ \t]*\n[ \t]*(@)|(@)[ \t]*\n[ \t]*([\w-])")


def is_role(local: str) -> bool:
    parts = [p for p in WORDS.split(local) if p]
    return bool(parts) and all(ROLE_WORD.fullmatch(p) for p in parts)


def _email(m: re.Match) -> str:
    return m.group(0) if is_role(m.group(0).split("@")[0]) else "[email removed]"


def scrub(text: str) -> str:
    text = BROKEN_EMAIL.sub(
        lambda m: (m.group(1) + m.group(2)) if m.group(1) else (m.group(3) + m.group(4)), text
    )
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
    for k in ("phones", "hours"):  # lists of strings stored as JSON
        if isinstance(row.get(k), str):
            row[k] = scrub_json(row[k])
    for k in ("sections", "tables", "structured", "access_snippets", "description"):
        if isinstance(row.get(k), str):
            row[k] = scrub_json(row[k])
    return row
