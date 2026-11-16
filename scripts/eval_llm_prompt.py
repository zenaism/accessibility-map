"""Measure the model stage on a labelled mini-set built from the earlier facts (and a few headlines that are not facts).

    python scripts/eval_llm_prompt.py [--n 30]

Positives: sentences the earlier reading accepted as facts. Negatives: headline-like fragments. Reports how many positives
the model keeps with the right value, and how many negatives it rejects, plus the time per call.
"""

import argparse
import time

from atlas.extract import llm, pipeline

NEG = [
    ("Sensory-Friendly Santa", "sensory_friendly"),
    ("Cincinnati State’s Interpreter Training Program", "asl_interpretation"),
    ("Top 10 ADA Accessible Features In Cincy Parks", "listed_accessible"),
    ("Adult changing tables", "adult_changing_table"),
    ("New Braille and tactile elements", "braille"),
    ("Accessibility Services Office Directory", "accessibility_contact"),
]
ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=30)
a = ap.parse_args()
sil = pipeline.silver()
sil = sil[sil.evidence_quote.str.len().between(30, 300) & sil.value.isin(["yes", "limited", "no"])].sample(a.n, random_state=3)
ok = keep = right = 0
t0 = time.time()
for r in sil.itertuples():
    v = llm.verify(r.evidence_quote, r.attribute, "yes")
    keep += bool(v.get("states_fact"))
    right += bool(v.get("states_fact")) and v.get("value") == r.value
rej = 0
for s, attr in NEG:
    rej += v.get("states_fact") is False if (v := llm.verify(s, attr, "yes")) else 0
print(f"positives kept: {keep}/{len(sil)}  | value also right: {right}/{len(sil)}  | headlines rejected: {rej}/{len(NEG)}")
print(f"{(time.time() - t0) / (len(sil) + len(NEG)):.1f} s per call")
