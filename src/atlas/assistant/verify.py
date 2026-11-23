"""The verifier: deterministic checks that keep every sentence tied to a record. No model.

A sentence is kept only if
  1 every record it cites (`refs`) exists in the tool results;
  2 a claim cites at least one record (meta sentences are fixed text such as "I don't know");
  3 it holds no banned phrase ("ADA compliant", "safe", "guaranteed"...; only a disclaimer may
    say "ADA compliant", to refuse it);
  4 every number in it appears in the results, the question, the resolved dates, or was computed
    and declared by the composer (`derived`), allowing 12-hour clock times;
  5 every quoted string appears word for word in a record;
  6 every capitalised name in it appears in the results, the question or the known names.
Sentences that fail are removed. If nothing is left of the main answer, the answer becomes
"I don't know". The JavaScript port (verify.js) must give the same verdicts.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from . import rules as R
from .planner import capitalized, norm, stem, tokens
from .schema import Answer, Context, Plan, Sentence, ToolResult

_NUM = re.compile(r"\d+(?:\.\d+)?")
CONSTANT_NUMBERS = {"911", "8.33", "30"}


@dataclass
class Issue:
    section: str  # headline | details | card
    index: int
    rule: str
    text: str

    def to_dict(self) -> dict:
        return {"section": self.section, "index": self.index, "rule": self.rule, "text": self.text}


def _n(x: str) -> str:
    return x.lstrip("0") or "0" if "." not in x else x


def numbers(text: str) -> set[str]:
    return {_n(x) for x in _NUM.findall(text)}


def _record_ids(results: list[ToolResult]) -> set[str]:
    ids = set()
    for r in results:
        ids.add(f"tool:{r.tool}")
        rows = r.data if isinstance(r.data, list) else ([r.data] if isinstance(r.data, dict) else [])
        for x in rows:
            for k in ("link_id", "id"):
                if isinstance(x, dict) and x.get(k):
                    ids.add(x[k])
            if isinstance(x, dict):
                for e in x.get("events") or []:
                    if e.get("link_id"):
                        ids.add(e["link_id"])
    return ids


def _blob(results: list[ToolResult]) -> str:
    return json.dumps([r.data for r in results], ensure_ascii=False).lower()


def _quotes(results: list[ToolResult]) -> str:
    return " ".join(
        norm(x)
        for x in re.findall(
            r'"((?:quote|detail|summary|notice|title|arrival|text)": "(?:[^"\\]|\\.)*")', _blob(results)
        )
    )


def _derived_from_results(results) -> set[str]:
    """Numbers the composer computes from results: distances in feet or miles, percentages."""
    from .composer import rhu

    out = set()

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k == "miles" and isinstance(v, (int, float)):
                    out.add(str(max(50, rhu(v * 5280 / 50) * 50)))
                    out.add(f"{rhu(v * 10) / 10:.1f}")
                if k == "share_steeper_than_ramp" and isinstance(v, (int, float)):
                    out.add(str(rhu(v * 100)))
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk([r.data for r in results])
    out.add(str(sum(1 for r in results for _ in (r.data if isinstance(r.data, list) else []))))
    return out


def allowed_numbers(
    results, plan: Plan | None, question: str, derived: list[str], as_of: str | None
) -> set[str]:
    base = numbers(_blob(results)) | numbers(question) | set(CONSTANT_NUMBERS) | {_n(d) for d in derived}
    base |= {_n(d) for d in _derived_from_results(results)}
    if plan and plan.when:
        base |= numbers(plan.when["start"] + " " + plan.when["end"])
    if as_of:
        base |= numbers(as_of)
    for x in list(base):
        if x.isdigit() and 13 <= int(x) <= 23:
            base.add(str(int(x) - 12))
    return base


def _subtokens(text: str) -> set[str]:
    out = set()
    for w in tokens(text):
        out.add(stem(w))
        out |= {stem(x) for x in re.split(r"[-']", w) if x}
    return out


def known_name_tokens(results, question: str, plan_text: str = "") -> set[str]:
    out = _subtokens(_blob(results)) | _subtokens(question) | _subtokens(plan_text)
    out |= {stem(w) for w in tokens(" ".join(R.MONTHS_DAYS + R.KNOWN_CAPS + list(R.REGION_KEYS)))}
    out |= {stem(w) for _, label in R.SOURCE_KINDS for w in tokens(label)}
    out |= {
        stem(w) for w in tokens(" ".join(R.NEED_LABELS.values()) + " " + " ".join(R.TYPE_LABELS.values()))
    }
    return out


def check_sentence(
    s: Sentence, results, ids: set[str], nums: set[str], names: set[str], quotes: str
) -> str | None:
    """The first rule the sentence breaks, or None."""
    for r in s.refs:
        if r not in ids:
            return "unknown_record"
    if s.kind == "claim" and not s.refs:
        return "no_citation"
    t = norm(s.text)
    if s.kind != "disclaimer":
        for b in R.BANNED:
            if f" {norm(b)} " in f" {t} ":
                return "banned_phrase"
    if s.kind != "disclaimer":
        for b in R.BANNED_WORDS:
            if f" {b} " in f" {t} ":
                return "banned_phrase"
    if s.kind == "meta" or s.kind == "disclaimer":
        return None
    if re.search(r"[a-z]+_[a-z]+", s.text):
        return "internal_identifier"
    for x in numbers(s.text):
        if x not in nums:
            return "number_not_in_results"
    for q in re.findall(r"[\"“]([^\"”]{3,})[\"”]", s.text):
        if norm(q) not in quotes:
            return "quote_not_in_record"
    for w in capitalized(s.text, ".?!:;("):
        k = stem(norm(w))
        if k and k not in names and len(k) > 1:
            return "name_not_in_results"
    return None


def verify(
    a: Answer, results: list[ToolResult], plan: Plan | None, ctx: Context, question: str = ""
) -> tuple[Answer, list[Issue]]:
    ids = _record_ids(results)
    derived = [d for s in [*a.headline, *a.details] for d in s.derived]
    nums = allowed_numbers(results, plan, question, derived, a.as_of)
    names = known_name_tokens(
        results, question, json.dumps(plan.to_dict(), ensure_ascii=False) if plan else ""
    )
    quotes = _quotes(results)
    issues: list[Issue] = []
    for section in ("headline", "details"):
        keep = []
        for i, s in enumerate(getattr(a, section)):
            bad = check_sentence(s, results, ids, nums, names, quotes)
            if bad:
                issues.append(Issue(section, i, bad, s.text))
            else:
                keep.append(s)
        setattr(a, section, keep)
    for i, c in enumerate(a.cards):
        if c.place_id not in ids:
            issues.append(Issue("card", i, "unknown_record", c.name))
    a.cards = [c for c in a.cards if c.place_id in ids]
    a.removed = len(issues)
    if not a.headline and a.kind not in ("emergency",):
        a.kind = "unknown"
        a.headline = [
            Sentence("I'm not sure I can answer that reliably, so I'd rather say I don't know.", [], "meta"),
            Sentence("Please call the place or check its own website.", [], "meta"),
        ]
        a.cards, a.details = [], []
    a.verified = not issues
    return a, issues
