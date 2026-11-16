"""Rule-based fact finding: free, instant, and the baseline any model must beat.

A rule only proposes: a sentence that matches an attribute's patterns becomes a candidate with a value guessed from
the words around the match (yes, limited, no). The quote is the sentence itself, so it is verbatim by construction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache

import yaml

from ..core import ROOT

SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"“(])|\n+|\s\|\s|•|·")
NEGATION = re.compile(
    r"\b(not|no|isn['’]t|aren['’]t|cannot|can['’]t|unable|inaccessible|without|lacks?|lacking|unavailable|never|n['’]t)\b",
    re.I,
)
HEDGE = re.compile(
    r"\b(some|partial(ly)?|limited|most|many|select(ed)?|certain|except|only|not all|varies|vary|may not|sometimes|few)\b",
    re.I,
)
MARKUP = re.compile(r"[#*_`>|]+|\[(.*?)\]\(.*?\)")
MIN_LEN, MAX_LEN = 20, 450


@dataclass
class Candidate:
    attribute: str
    value: str
    quote: str
    section: str
    trigger: str
    detail: str = ""


@cache
def rules() -> dict[str, dict]:
    raw = yaml.safe_load((ROOT / "config" / "fact_rules.yaml").read_text())
    return {
        a: {
            "re": re.compile("|".join(f"(?:{p})" for p in r["any"]), re.I),
            "positive_no": bool(r.get("positive_no")),
        }
        for a, r in raw.items()
    }


def clean(sentence: str) -> str:
    s = MARKUP.sub(lambda m: m.group(1) or " ", sentence)
    return re.sub(r"\s+", " ", s).strip(" -–•\t")


def sentences(text: str) -> list[str]:
    return [s for s in (clean(x) for x in SENTENCE.split(text)) if MIN_LEN <= len(s) <= MAX_LEN]


def polarity(sentence: str, match: re.Match, positive_no: bool = False) -> str:
    """yes / limited / no from the words just before and after the matched phrase."""
    before = sentence[max(0, match.start() - 60) : match.start()]
    after = sentence[match.end() : match.end() + 40]
    window = before + " " + after
    if not positive_no and NEGATION.search(before[-35:]):
        return "no"
    if re.search(
        r"\b(is|are) (currently )?(not|unavailable)\b|\bnot (available|offered|provided)\b|\bno longer\b",
        after,
        re.I,
    ):
        return "no"
    if HEDGE.search(window):
        return "limited"
    return "yes"


def find(text: str, section_path: str = "") -> list[Candidate]:
    """Candidate facts in one block of text; one per (sentence, attribute)."""
    out = []
    for s in sentences(text):
        for attr, r in rules().items():
            m = r["re"].search(s)
            if m:
                out.append(Candidate(attr, polarity(s, m, r["positive_no"]), s, section_path, m.group(0)))
    return out


def find_in_doc(sections: list[dict], text: str) -> list[Candidate]:
    """Candidates in a document: section by section when it has sections, else the whole text."""
    blocks = sections or [{"path": "", "text": text}]
    seen, out = set(), []
    for b in blocks:
        for c in find(b["text"], b["path"]):
            key = (c.attribute, c.quote)
            if key not in seen:
                seen.add(key)
                out.append(c)
    return out
