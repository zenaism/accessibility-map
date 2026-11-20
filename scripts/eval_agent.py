# ruff: noqa: E501
"""Evaluate the assistant: variants A (rules+templates), B (model plan+templates), C (rules+model compose), D (both).

    python scripts/eval_agent.py [--variants A,B,C,D] [--sample 4] [--today 2026-11-20]

Questions: eval/questions.yaml (bank), eval/questions_agent.yaml, eval/traps.yaml, eval/category_questions.yaml
(unlabelled: only safety checks, plus honesty for categories whose data status is "none").
A runs on everything; B-D (slow, a 3B model on an 8 GB laptop) run on every Nth question (--sample) plus all traps.
Writes eval/results/agent_<date>.md.
"""

from __future__ import annotations

import argparse
import resource
import statistics
import subprocess
import time
from datetime import date
from pathlib import Path

import yaml

from atlas.assistant import llm
from atlas.assistant.engine import Engine
from atlas.assistant.executor import KBBackend
from atlas.assistant.schema import Context

ROOT = Path(__file__).resolve().parents[1]
UNKNOWN_KINDS = ("unknown", "no_data", "out_of_area")
TOOLSET = {"search_places", "get_place", "find_events", "nearest"}


def load(today: str):
    qs = []
    for q in yaml.safe_load((ROOT / "eval/questions.yaml").read_text()):
        c = q["call"]
        ctx = {"location": [c["args"]["lat"], c["args"]["lon"]]} if c["tool"] == "nearest" and "lat" in c["args"] else {}
        qs.append({"id": q["id"], "set": "bank", "question": q["question"], "today": today, "context": ctx, "tool": c["tool"],
                   "names": q.get("expect_any"), "unknown": bool(q.get("expect_unknown"))})
    for q in yaml.safe_load((ROOT / "eval/questions_agent.yaml").read_text()):
        e = q.get("expect", {})
        qs.append({"id": q["id"], "set": "agent", "question": q["question"], "today": q.get("today", today), "context": q.get("context", {}),
                   "intent": e.get("intent"), "kind": e.get("kind"), "names": e.get("names"), "include": e.get("include", []), "exclude": e.get("exclude", [])})
    cats = yaml.safe_load((ROOT / "config/categories.yaml").read_text())
    for q in yaml.safe_load((ROOT / "eval/category_questions.yaml").read_text()):
        qs.append({"id": q["id"], "set": "category", "question": q["question"], "today": today, "context": {},
                   "nodata": cats[q["category"]].get("status") == "none"})
    for q in yaml.safe_load((ROOT / "eval/traps.yaml").read_text()):
        e = q.get("expect", {})
        qs.append({"id": q["id"], "set": "trap", "question": q["question"], "today": today, "context": {}, "inject": q.get("inject"),
                   "intent": e.get("intent"), "kind": e.get("kind"), "include": e.get("include", []), "exclude": e.get("exclude", [])})
    return qs


def names_of(results) -> list[str]:
    out = []
    for r in results:
        rows = r.data if isinstance(r.data, list) else ([r.data] if r.data else [])
        for x in rows[:5]:
            n = x.get("name") or x.get("place")
            if n and n not in out:
                out.append(n)
    return out[:8]


def check(q, eng, a) -> dict:
    pl, res = eng.last_plan, eng.last_results
    text = a.full_text.lower() + " not known: " + "; ".join(a.unknown).lower() + " " + " ".join(c.name.lower() for c in a.cards)
    r = {"time": 0.0, "verified": a.verified, "removed": a.removed, "kind": a.kind}
    if q.get("tool"):
        ok_tools = {q["tool"]} | (TOOLSET if q["tool"] in TOOLSET else set())
        # strict: same tool; lenient: any lookup tool (the bank's call is one good choice among several)
        r["tool_strict"] = pl.tool == q["tool"] or (q["tool"] == "get_place" and pl.tool == "area_conditions")
        r["tool_ok"] = pl.tool in ok_tools or pl.intent in ("ada_trust", "conflict_trust", "reports_trust", "dates_trust", "live_info", "clarify", "area")
    if q.get("intent"):
        r["intent_ok"] = pl.intent in q["intent"]
    if q.get("names"):
        got = names_of(res)
        r["retrieval"] = any(any(e == n or e in n for n in got) for e in q["names"])
    if q.get("unknown") is not None and q["set"] == "bank":
        r["honest"] = (a.kind in UNKNOWN_KINDS) if q["unknown"] else (a.kind not in UNKNOWN_KINDS or None)
    if q.get("nodata"):
        r["honest"] = a.kind in UNKNOWN_KINDS
    if q.get("kind") and q["set"] != "trap":
        r["kind_ok"] = a.kind in q["kind"]
    if q["set"] in ("trap", "agent"):
        inc = all(s.lower() in text for s in q.get("include", []))
        exc = not any(s.lower() in text for s in q.get("exclude", []))
        r["content_ok"] = inc and exc
        if q["set"] == "trap":
            r["trap"] = inc and exc and (not q.get("intent") or pl.intent in q["intent"]) and (not q.get("kind") or a.kind in q["kind"])
    return r


def run_variant(name, qs, today):
    if name == "A":
        eng = Engine()
    else:
        eng = Engine(planner=llm.model_planner if name in "BD" else None, composer=llm.model_composer if name in "CD" else None)
    rows, base_places = [], None
    for q in qs:
        t = time.time()
        ctx = Context.from_dict({"today": q["today"], **q["context"]})
        if q.get("inject"):
            eng.be = Planted(eng.be, q["inject"])
            eng.index = type(eng.index)(eng.be.places())
        try:
            a = eng.answer(q["question"], ctx)
            r = check(q, eng, a)
        except Exception as e:  # noqa: BLE001
            r = {"error": str(e)[:80]}
        r["time"] = time.time() - t
        r["id"], r["set"] = q["id"], q["set"]
        rows.append(r)
        if q.get("inject"):
            eng.be = KBBackend()
            eng.index = type(eng.index)(eng.be.places())
    return rows


class Planted:
    """The real knowledge base plus one planted record whose text tries to give the assistant orders."""

    def __init__(self, be, rec):
        self.be, self.rec = be, rec
        self.pid = "planted-1"

    def places(self):
        return [*self.be.places(), {"id": self.pid, "name": self.rec["name"], "layer": "food_drink", "region": "oxford", "rating": "partial", "lat": 39.5105, "lon": -84.7425}]

    def _row(self):
        return {"link_id": self.pid, "name": self.rec["name"], "region": "oxford", "type": "food_drink", "rating": "partial", "what_is_known": [], "summary": self.rec["summary"],
                "notice": None, "newest_source": None, "page": "x", "address": None, "phone": None, "website": None, "hours": None}

    def search_places(self, **kw):
        q = (kw.get("query") or "").lower()
        return [self._row()] if self.rec["name"].lower() in q or kw.get("place_type") == "food_drink" and not q else self.be.search_places(**kw)

    def nearest(self, **kw):
        rows = self.be.nearest(**kw)
        return [{**self._row(), "miles": 0.05, "direction": "north"}, *rows][: kw.get("limit", 5)] if kw.get("place_type") == "food_drink" else rows

    def get_place(self, name_or_id):
        if name_or_id == self.pid:
            return {**self._row(), "facts": [], "getting_there": {}, "contacts": {}, "events": [], "data_as_of": "2026-11-13"}
        return self.be.get_place(name_or_id)

    def facts(self, i):
        return [] if i == self.pid else self.be.facts(i)

    def coords(self, i):
        return (39.5105, -84.7425) if i == self.pid else self.be.coords(i)

    def __getattr__(self, n):
        return getattr(self.be, n)


def pct(rows, key, sel=None):
    v = [r[key] for r in rows if key in r and r[key] is not None and (sel is None or r["set"] in sel)]
    return (f"{sum(bool(x) for x in v)}/{len(v)} = {sum(bool(x) for x in v) / len(v):.0%}" if v else "n/a")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", default="A,B,C,D")
    ap.add_argument("--sample", type=int, default=4, help="B-D run on every Nth question (plus all traps)")
    ap.add_argument("--today", default="2026-11-20")
    a = ap.parse_args()
    qs = load(a.today)
    sample = [q for i, q in enumerate(qs) if i % a.sample == 0 or q["set"] == "trap"]
    out = {}
    for v in a.variants.split(","):
        use = qs if v == "A" else sample
        print(f"variant {v}: {len(use)} questions", flush=True)
        t = time.time()
        out[v] = (run_variant(v, use, a.today), len(use), time.time() - t)
        if v != "A":
            ps = subprocess.run(["ollama", "ps"], capture_output=True, text=True).stdout.strip().splitlines()
            out[v] += ("; ".join(" ".join(x.split()[:4]) for x in ps[1:]) or "unloaded",)
            llm.unload()
    L = [f"# Assistant evaluation, variants A to D ({date.today().isoformat()})", "",
         f"Run with `scripts/eval_agent.py`; fixed today {a.today}; `qwen2.5:3b` through Ollama on an 8 GB M1 with another job running. "
         f"Questions: {len(qs)} (bank {sum(q['set'] == 'bank' for q in qs)}, new {sum(q['set'] == 'agent' for q in qs)}, "
         f"category (unlabelled) {sum(q['set'] == 'category' for q in qs)}, traps {sum(q['set'] == 'trap' for q in qs)}). "
         f"Variant A ran on all; B, C, D ran on a sample of {len(sample)} (every {a.sample}th question plus all traps) because a model answer takes 20 to 35 s.", "",
         "| metric | " + " | ".join(f"{v}" for v in out) + " |", "|---|" + "---|" * len(out)]
    def row(label, key, sel=None):
        L.append(f"| {label} | " + " | ".join(pct(out[v][0], key, sel) for v in out) + " |")
    row("tool choice, same tool as the bank (bank questions)", "tool_strict")
    row("tool choice, any lookup tool or a safe route (bank)", "tool_ok")
    row("understood intent (new + trap questions with an intent)", "intent_ok")
    row("retrieval@5, expected place among top results", "retrieval")
    row("answer kind as expected (new questions)", "kind_ok")
    row("honesty: unknown when data has no answer, answer when it has (bank + no-data categories)", "honest")
    row("content checks (include/exclude) (new questions)", "content_ok", ("agent",))
    row("trap pass rate", "trap")
    L.append("| answers fully verified (no sentence removed) | " + " | ".join(f"{sum(bool(r.get('verified')) for r in out[v][0])}/{len(out[v][0])}" for v in out) + " |")
    L.append("| sentences removed by the verifier (total) | " + " | ".join(str(sum(r.get('removed', 0) for r in out[v][0])) for v in out) + " |")
    L.append("| seconds per answer, median / mean / max | " + " | ".join(f"{statistics.median(r['time'] for r in out[v][0]):.2f} / {statistics.mean(r['time'] for r in out[v][0]):.2f} / {max(r['time'] for r in out[v][0]):.1f}" for v in out) + " |")
    L.append("| errors | " + " | ".join(str(sum('error' in r for r in out[v][0])) for v in out) + " |")
    L += ["", f"Model calls: {llm.STATS['calls']}, {llm.STATS['seconds']:.0f} s in the model; model plans used {llm.STATS['plan_used']}, rejected {llm.STATS['plan_rejected']}; "
          f"model sentences used {llm.STATS['compose_used']}, composer fell back {llm.STATS['compose_rejected']}, errors {llm.STATS['errors']}.",
          f"Memory: this process peaked at {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9:.2f} GB resident (without the model); `ollama ps` after the model runs: "
          + "; ".join(f"{v}: {out[v][3]}" for v in out if len(out[v]) > 3) + ". qwen2.5:3b takes about 2.3 GB.", "",
          "## Failures in variant A", ""]
    qmap = {q["id"]: q for q in qs}
    for r in out["A"][0]:
        bad = [k for k in ("tool_ok", "intent_ok", "retrieval", "honest", "kind_ok", "content_ok", "trap") if r.get(k) is False] + (["error"] if "error" in r else [])
        if bad:
            L.append(f"- `{r['id']}` ({r['set']}): {', '.join(bad)}: {qmap[r['id']]['question']}")
    L += ["", "## Limits", "",
          "- A 3B model, one machine, one fixed date. Variants B to D ran on a sample, so their percentages are rough (small counts).",
          "- The bank and new questions were written by someone who had seen the data's shape; the answer key is unchecked by other people. These are yardsticks, not accuracy.",
          "- Groundedness here is the verifier (citations, numbers, quotes, names, banned phrases). It does not check that a sentence is relevant to the question; a model sentence can be grounded and still off topic. No human sample check was done.",
          "- Category questions are unlabelled: only safety, verification and (for categories with no data) honesty are scored."]
    dest = ROOT / f"eval/results/agent_{date.today().isoformat()}.md"
    dest.write_text("\n".join(L) + "\n")
    print("\n".join(L[:30]))
    print("->", dest)


if __name__ == "__main__":
    main()
