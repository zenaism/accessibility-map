# ruff: noqa: E501
"""The four-step pipeline: plan -> run tools -> compose -> verify, and its event stream.

    eng = Engine()                       # rules planner + template composer (variant A)
    ans = eng.answer("Where is the closest accessible restroom?", ctx)
    for ev in events(ans): ...           # text / detail / card / action / unknown / sources / clarify / done

The model variants (llm.py) plug in through `planner` and `composer`; both are validated and fall back.
"""

from __future__ import annotations

from . import composer as C
from . import planner as P
from .executor import KBBackend, execute
from .schema import Answer, Context, Plan
from .verify import verify

REGION_NAMES = "Cincinnati and Oxford"


class Engine:
    def __init__(self, backend=None, planner=None, composer=None):
        self.be = backend or KBBackend()
        self.index = P.Index(self.be.places())
        self.planner = planner  # callable(text, ctx, index) -> Plan, or None for rules
        self.composer = composer  # callable(plan, results, ctx, as_of) -> Answer, or None for templates

    def plan(self, text: str, ctx: Context) -> Plan:
        pl = None
        if self.planner:
            try:
                pl = self.planner(text, ctx, self.index)
            except Exception:  # noqa: BLE001  a model failure must never break an answer
                pl = None
        return pl or P.plan(text, ctx, self.index)

    def answer(self, text: str, ctx: Context | dict | None = None) -> Answer:
        ctx = ctx if isinstance(ctx, Context) else Context.from_dict(ctx or {})
        ctx.validate()
        pl = self.plan(text, ctx)
        results = execute(pl, ctx, self.be)
        as_of = self.be.as_of()
        ans = C.compose(pl, results, ctx, as_of)
        if self.composer and pl.intent in ("nearest", "search", "place", "events", "area", "route"):
            try:
                alt = self.composer(pl, results, ctx, as_of, ans)
                if alt is not None:
                    ans = alt
            except Exception:  # noqa: BLE001
                pass
        ans, issues = verify(ans, results, pl, ctx, text)
        ans.engine = "model" if (self.planner or self.composer) else "rules"
        ans.validate()
        self.last_issues, self.last_results, self.last_plan = issues, results, pl
        return ans


def events(a: Answer):
    """The event stream the chat component receives (see assistant_build_spec.md section 4):
    clarify, text {delta, parts, kind}, detail {items}, card {card}, action {action, ...}, call {name, phone},
    unknown {about, call}, sources {items}, meta, done {verified, removed}. Errors are {type: "error", message}."""
    if a.clarify:
        yield {"type": "clarify", **a.clarify}
    yield {
        "type": "text",
        "kind": a.kind,
        "delta": " ".join(s.text for s in a.headline),
        "parts": [s.text for s in a.headline],
    }
    if a.details:
        yield {"type": "detail", "items": [s.text for s in a.details]}
    for c in a.cards:
        yield {"type": "card", "card": c.to_dict()}
    for act in a.actions:
        yield {"type": "action", "action": act["type"], **{k: v for k, v in act.items() if k != "type"}}
    if a.call:
        yield {"type": "call", **a.call}
    if a.unknown or a.kind in ("unknown", "no_data", "out_of_area"):
        yield {"type": "unknown", "about": list(a.unknown), "call": a.call}
    if a.sources:
        yield {"type": "sources", "items": [s.to_dict() for s in a.sources]}
    yield {"type": "meta", "as_of": a.as_of, "notes": a.notes, "plan": a.plan, "engine": a.engine}
    yield {"type": "done", "verified": a.verified, "removed": a.removed}
