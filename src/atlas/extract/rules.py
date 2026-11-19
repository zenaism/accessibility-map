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
    r"\b(some|partial(ly)?|limited|most|select(ed)?|certain|not all|only (?:the|one|some|a few)|varies|vary|may not|sometimes|few)\b",
    re.I,
)
# negation words that do not negate the fact: "at no cost", "not only", "no need to ask"
BENIGN_NO = re.compile(
    r"\bno (extra |additional |added |admission |entry )?(cost|charge|fee|fees|reservation|reservations|appointment|problem|need|"
    r"questions)\b|\bno (steps?|stairs?|barriers?|thresholds?)\b(?![- ]free)|\bnot only\b|\bwithout (a |any )?(charge|cost|fee|reservation|appointment)\b|\bcan['’]t miss\b",
    re.I,
)
CLAUSE = re.compile(r"[;:]|,?\s+(?:but|however|although|though|while|whereas)\b", re.I)
EXCEPTION = re.compile(r"\b(except|other than|besides|apart from|but for)\b[\w ,']{0,20}$", re.I)
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
            # a match may not start inside a longer word ("dis-closure" is not a closure)
            "re": re.compile("(?<![A-Za-z])(?:" + "|".join(f"(?:{p})" for p in r["any"]) + ")", re.I),
            "positive_no": bool(r.get("positive_no")),
            "skip_if": re.compile(r["skip_if"], re.I) if r.get("skip_if") else None,
        }
        for a, r in raw.items()
    }


def clean(sentence: str) -> str:
    s = MARKUP.sub(lambda m: m.group(1) or " ", sentence)
    return re.sub(r"\s+", " ", s).strip(" -–•\t")


WRAP = re.compile(
    r"(?<=[a-z,])[ \t]*\n[ \t]*(?=[a-z])"
)  # a line broken in the middle of a sentence (PDF layout)


def sentences(text: str) -> list[str]:
    text = WRAP.sub(" ", text)
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
    [
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "to",
        "in",
        "on",
        "at",
        "for",
        "with",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "it",
        "this",
        "that",
        "these",
        "those",
        "as",
        "by",
        "from",
        "not",
        "no",
        "can",
        "may",
        "will",
        "you",
        "your",
        "we",
        "our",
        "they",
        "their",
        "has",
        "have",
        "had",
        "if",
        "when",
        "which",
        "who",
        "all",
        "any",
    ]
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


def clause_of(sentence: str, match: re.Match) -> tuple[str, int, int]:
    """The clause of the sentence that holds the match, and the match position inside it."""
    start = 0
    for m in CLAUSE.finditer(sentence):
        if m.end() <= match.start():
            start = m.end()
        elif m.start() >= match.end():
            return sentence[start : m.start()], match.start() - start, match.end() - start
    return sentence[start:], match.start() - start, match.end() - start


def polarity(sentence: str, match: re.Match, positive_no: bool = False) -> str:
    """yes / limited / no from the whole clause around the matched phrase.

    A negation counts anywhere in the clause, before or after the match ("There is no step-free entrance", "The restroom is
    not accessible"). With `positive_no` a "no" inside the matched words is part of the fact ("no steps"), not a negation.
    """
    clause, a, b = clause_of(sentence, match)
    if EXCEPTION.search(clause[:a]):
        return "yes"  # "Pets are not allowed, except service animals": the exception is what is allowed
    if positive_no:
        clause = clause[:a] + " " * (b - a) + clause[b:]
    masked = BENIGN_NO.sub(" ", clause)
    if re.search(r"\bnot all\b", clause, re.I) or (HEDGE.search(clause) and not NEGATION.search(masked)):
        return "limited"
    if NEGATION.search(masked) or re.search(r"\bno longer\b", clause, re.I):
        return "no"
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
            if m and not (r["skip_if"] and r["skip_if"].search(s)):
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
