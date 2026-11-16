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


VERB = re.compile(
    r"\b(is|are|was|were|has|have|had|be|can|may|will|must|should|offers?|provides?|includes?|features?|requires?|allows?|"
    r"located|available|welcome|open|closed|accessible|reserved|serves?|needs?|contact|call|visit|ask|request|bring|use)\b",
    re.I,
)
ACCESS_SECTION = re.compile(
    r"access|feature|amenit|service|facilit|visit|plan|ada\b|disab|inclusi|barrier|mobility", re.I
)


STOPWORDS = frozenset(
    ["the", "a", "an", "and", "or", "of", "to", "in", "on", "at", "for", "with", "is", "are", "was", "were", "be", "been", "it", "this", "that", "these", "those", "as", "by", "from", "not", "no", "can", "may", "will", "you", "your", "we", "our", "they", "their", "has", "have", "had", "if", "when", "which", "who", "all", "any"]
)


def is_english(s: str) -> bool:
    """Cheap language check: enough common English words. Sentences in other languages would otherwise become 'facts'."""
    words = re.findall(r"[a-zA-Z']+", s.lower())
    if len(words) < 4:
        return True  # too short to judge
    return sum(w in STOPWORDS for w in words) / len(words) >= 0.15


def looks_like_headline(s: str) -> bool:
    """A title or label rather than a statement: a Title Case line, or two or three words with no verb."""
    words = s.split()
    if s.rstrip()[-1:] in ".!?" and VERB.search(s):
        return False
    caps = sum(1 for w in words if w[:1].isupper())
    if len(words) >= 3 and caps / len(words) >= 0.7:
        return True  # Title Case Line, a program or event name
    return len(words) <= 3 and not VERB.search(
        s
    )  # two or three words with no verb is a label; longer bullets are kept for the model


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
        if s.endswith("?") or not is_english(s):
            continue  # a checklist question is not a statement; text in another language is not read by English rules
        if looks_like_headline(s) and not ACCESS_SECTION.search(section_path):
            continue  # a label outside an accessibility section is not a statement about a place
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
