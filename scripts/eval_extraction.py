"""Compare the automatic extractor with the 261 facts read earlier (data/extracted/venue_facts.jsonl).

    python scripts/eval_extraction.py [--llm]

Reports, per attribute: how many silver facts the extractor also finds in the same document (recall), how often the
value agrees, and how many extra facts it proposes (not wrong, only unlabelled: a sample is printed to judge by eye).
The silver facts are not perfect truth (they were read by a model and not checked by a person), so these numbers are
a yardstick, not a verdict.
"""

from __future__ import annotations

import argparse
import sys

import pandas as pd

from atlas.core import PROCESSED
from atlas.extract import pipeline

ap = argparse.ArgumentParser()
ap.add_argument("--sample", type=int, default=12)
a = ap.parse_args()

sil = pipeline.silver()
auto = []
for (src, region), grp in sil.groupby([sil.doc_id.str.split(":").str[0], "region"]):
    f = PROCESSED / region / f"{src}.docs.parquet"
    if not f.exists():
        continue
    docs = pd.read_parquet(f)
    docs = docs[docs.doc_id.isin(grp.doc_id.unique())]
    auto.append(pipeline.extract_docs(docs, src, region))
auto = pd.concat(auto, ignore_index=True)
auto = auto[auto.quote_verified]

s_pairs = sil.groupby(["doc_id", "attribute"]).value.agg(lambda v: set(v)).reset_index()
a_pairs = auto.groupby(["doc_id", "attribute"]).value.agg(lambda v: set(v)).reset_index()
m = s_pairs.merge(a_pairs, on=["doc_id", "attribute"], how="left", suffixes=("_s", "_a"))
m["found"] = m.value_a.notna()
m["agree"] = [bool(s & v) if isinstance(v, set) else False for s, v in zip(m.value_s, m.value_a, strict=True)]
extra = a_pairs.merge(s_pairs, on=["doc_id", "attribute"], how="left", indicator=True)
extra = extra[extra._merge == "left_only"]

print(
    f"silver (document, attribute) pairs: {len(m)}  | found by the extractor: {m.found.sum()} ({m.found.mean():.0%})"
)
print(
    f"value agrees on found pairs: {m[m.found].agree.mean():.0%}  | extra pairs not in silver: {len(extra)}"
)
t = m.groupby("attribute").agg(silver=("found", "size"), found=("found", "sum"), agree=("agree", "sum"))
t["recall"] = (t.found / t.silver).round(2)
print(t.sort_values("silver", ascending=False).to_string())
print("\nsample of extra facts (judge by eye):")
ex = auto.merge(extra[["doc_id", "attribute"]], on=["doc_id", "attribute"]).sample(
    min(a.sample, len(extra)), random_state=1
)
for r in ex.itertuples():
    print(f"- [{r.attribute}={r.value}] {r.evidence_quote[:150]}")
sys.exit(0)
