"""Run the extractor over a source's documents and write facts with their provenance.

    python -m atlas.cli extract <source> [--region R] [--llm]     ->  data/processed/<region>/<source>.facts.parquet

Every fact has: the verbatim quote (checked against the document), the section it sits in, how it was found
(method, extractor version, model) and a confidence, so a later run with a better model adds rows instead of overwriting.
"""

from __future__ import annotations

import json
import re

import pandas as pd

from ..core import PROCESSED, ROOT, now
from . import llm, rules

VERSION = "rules-1"
BASE_CONFIDENCE = 0.5  # a rule match on its own: believable, not confirmed


def norm(text: str) -> str:
    """Text with markup and spacing removed, for comparing a quote with its document."""
    return re.sub(r"\s+", " ", re.sub(r"[#*_`>|]|\[|\]\([^)]*\)", " ", text)).strip().lower()


def verify_quote(quote: str, text: str) -> bool:
    return norm(quote) in norm(text)


def docs_file(source: str, region: str):
    return PROCESSED / region / f"{source}.docs.parquet"


MAX_DISCOVER = 20  # sentences per document sent to the model to look for facts the rules missed


def _row(d, source, region, c_attr, value, detail, quote, section, trigger, method, model, confidence):
    return {
        "doc_id": d.doc_id, "source": source, "region": region, "url": d.url, "place": (getattr(d, "place_name", None) or d.title or "").strip(),
        "place_id": getattr(d, "place_id", None),
        "section": section, "attribute": c_attr, "value": value, "detail": detail, "evidence_quote": quote,
        "trigger": trigger, "method": method, "extractor": VERSION, "model": model,
        "prompt_version": llm.PROMPT_VERSION if model else None, "confidence": confidence, "extracted_at": now(),
    }  # fmt: skip


def extract_docs(docs: pd.DataFrame, source: str, region: str, use_llm: bool = False) -> pd.DataFrame:
    """Facts from documents. With use_llm the local model confirms or rejects each rule-proposed sentence (rejected
    ones are dropped) and reads the other access-related sentences for facts the rules missed."""
    rows = []
    for d in docs.itertuples():
        text = d.text or ""
        sections = json.loads(d.sections) if getattr(d, "sections", None) else []
        cands = rules.find_in_doc(sections, text)
        matched = {c.quote for c in cands}
        for c in cands:
            if not use_llm:
                rows.append(
                    _row(
                        d,
                        source,
                        region,
                        c.attribute,
                        c.value,
                        "",
                        c.quote,
                        c.section,
                        c.trigger,
                        "rules",
                        None,
                        BASE_CONFIDENCE,
                    )
                )
                continue
            v = llm.verify(c.quote, c.attribute, c.value)
            if v.get(
                "error"
            ):  # the model did not answer (Ollama down): this is a rules fact, not a model-checked one
                rows.append(_row(d, source, region, c.attribute, c.value, "", c.quote, c.section, c.trigger, "rules", None, BASE_CONFIDENCE))  # fmt: skip
                continue
            if v.get("states_fact") is False:
                continue  # the model says it is a headline, a title or a general statement
            agree = v.get("value") == c.value
            rows.append(_row(d, source, region, c.attribute, v.get("value", c.value), v.get("detail", ""), c.quote, c.section,
                             c.trigger, "rules+llm", llm.MODEL, 0.8 if agree and v.get("states_fact") else 0.6))  # fmt: skip
        if use_llm:
            extra = [
                s for s in (sn for sn in _access_sentences(sections, text)) if s["sentence"] not in matched
            ][:MAX_DISCOVER]
            for s in extra:
                for f in llm.discover(s["sentence"]):
                    rows.append(_row(d, source, region, f["attribute"], f["value"], f.get("detail", ""), s["sentence"], s["section"],
                                     "", "llm", llm.MODEL, 0.55))  # fmt: skip
    df = pd.DataFrame(rows)
    if len(df):
        df["quote_verified"] = [
            verify_quote(q, t)
            for q, t in zip(
                df.evidence_quote,
                df.doc_id.map(dict(zip(docs.doc_id, docs.text.fillna(""), strict=True))),
                strict=True,
            )
        ]
        df = df.drop_duplicates(["doc_id", "attribute", "evidence_quote"])
    return df


def _access_sentences(sections: list[dict], text: str) -> list[dict]:
    """Sentences that mention what wheelchair users ask about (the crawler's own keyword list), with their section."""
    from ..crawler import relevance

    words = relevance.keywords()
    out = []
    for b in sections or [{"path": "", "text": text}]:
        for s in rules.sentences(b["text"]):
            if any(w in s.lower() for w in words):
                out.append({"section": b["path"], "sentence": s})
    return out


def run(source: str, region: str, use_llm: bool = False) -> pd.DataFrame:
    f = docs_file(source, region)
    docs = pd.read_parquet(f)
    facts = extract_docs(docs, source, region, use_llm)
    if len(facts):
        facts = facts[facts.quote_verified].reset_index(
            drop=True
        )  # a fact whose quote is not in the document is dropped
        facts.to_parquet(f.with_name(f"{source}.facts.parquet"), index=False)
    return facts


def silver() -> pd.DataFrame:
    """The 261 facts read earlier by Claude (every quote machine-checked): an answer key for evaluation."""
    return pd.read_json(ROOT / "data/extracted/venue_facts.jsonl", lines=True)
