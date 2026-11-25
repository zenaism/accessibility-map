# ruff: noqa: E501
"""Write tests/js/assistant_golden.json: for each case in eval/golden_cases.yaml, the plan and answer the
Python assistant gives. The JavaScript port (tests/js/assistant.test.js) must reproduce it exactly.

    python scripts/make_assistant_golden.py
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from atlas.assistant.engine import Engine
from atlas.assistant.schema import Context

ROOT = Path(__file__).resolve().parents[1]


def view(a, plan) -> dict:
    """The parts of an answer the user sees, in a stable shape both languages produce."""
    return {
        "kind": a.kind,
        "headline": [s.text for s in a.headline],
        "details": [s.text for s in a.details],
        "cards": [
            {
                "place_id": c.place_id,
                "name": c.name,
                "rating": c.rating,
                "distance_text": c.distance_text,
                "direction": c.direction,
                "phone": c.phone,
                "event": c.event,
                "confidence": c.confidence,
                "lead": c.lead,
                "facts": [[f.label, f.value, f.detail, f.source, f.date] for f in c.facts],
            }
            for c in a.cards
        ],
        "unknown": a.unknown,
        "call": a.call,
        "actions": a.actions,
        "as_of": a.as_of,
        "sources": [s.url for s in a.sources],
        "verified": a.verified,
        "removed": a.removed,
        "confidence": a.confidence,
        "followups": a.followups,
        "plan": plan.to_dict(),
    }


def main() -> None:
    eng = Engine()
    cases = yaml.safe_load((ROOT / "eval/golden_cases.yaml").read_text())
    out = []
    for c in cases:
        ctx = {k: v for k, v in c.items() if k != "q"}
        a = eng.answer(c["q"], Context.from_dict(ctx))
        out.append({"q": c["q"], "context": ctx, "expected": view(a, eng.last_plan)})
    dest = ROOT / "tests/js/assistant_golden.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=0, sort_keys=True))
    bad = [c["q"] for c, o in zip(cases, out, strict=True) if o["expected"]["removed"]]
    print(
        f"{len(out)} cases -> {dest.relative_to(ROOT)} ({dest.stat().st_size // 1024} KB); verifier removed sentences in {len(bad)}: {bad}"
    )


if __name__ == "__main__":
    main()
