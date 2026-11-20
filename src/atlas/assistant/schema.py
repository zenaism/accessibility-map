"""Plain dataclasses with explicit validation (no pydantic: it is not installed here).

Everything the pipeline passes around is one of these, and every one can round-trip through
`to_dict` / `from_dict`, so the same shapes are used by the tests, the local server and the browser
(the JavaScript port builds the same dictionaries).

Pipeline: Context + question -> Plan -> ToolResult[] -> Answer -> verified Answer.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date

INTENTS = (
    "emergency",
    "help",
    "ada_trust",
    "dates_trust",
    "conflict_trust",
    "reports_trust",
    "out_of_area",
    "no_data",
    "live_info",
    "events",
    "route",
    "area",
    "nearest",
    "search",
    "place",
    "unknown",
    "clarify",
)
TOOLS = ("search_places", "nearest", "get_place", "find_events", "area_conditions", "accessible_route")
ANSWER_KINDS = ("answer", "unknown", "emergency", "clarify", "out_of_area", "no_data", "help", "error")
SENTENCE_KINDS = ("claim", "meta", "disclaimer")
ACTION_TYPES = ("route_to", "show_on_map", "call", "report", "open_link")


class SchemaError(ValueError):
    """A dictionary does not have the shape a schema requires."""


def _need(cond: bool, msg: str) -> None:
    if not cond:
        raise SchemaError(msg)


def _is_date(s) -> bool:
    try:
        date.fromisoformat(str(s))
        return True
    except ValueError:
        return False


@dataclass
class Context:
    """What the browser (or terminal) knows about this question."""

    today: str  # YYYY-MM-DD, injected for tests, the device clock in the browser
    region: str | None = None
    location: list | None = None  # [lat, lon], used only by tools, never logged
    needs: dict = field(default_factory=dict)  # {"mobility", "steps", "rely": []}
    plain: bool = False
    data_as_of: str | None = None

    def validate(self) -> Context:
        _need(_is_date(self.today), f"today must be YYYY-MM-DD, got {self.today!r}")
        _need(self.region in (None, "cincinnati", "oxford"), f"unknown region {self.region!r}")
        if self.location is not None:
            _need(
                isinstance(self.location, (list, tuple))
                and len(self.location) == 2
                and all(isinstance(v, (int, float)) for v in self.location)
                and -90 <= self.location[0] <= 90
                and -180 <= self.location[1] <= 180,
                "location must be [lat, lon]",
            )
        _need(isinstance(self.needs, dict), "needs must be an object")
        return self

    @classmethod
    def from_dict(cls, d: dict) -> Context:
        d = d or {}
        known = {k: d[k] for k in ("today", "region", "location", "needs", "plain", "data_as_of") if k in d}
        known.setdefault("today", date.today().isoformat())
        known["needs"] = known.get("needs") or {}
        return cls(**known).validate()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Plan:
    """What to do for a question: one tool call (or none) plus how to word the answer."""

    intent: str
    tool: str | None = None
    args: dict = field(default_factory=dict)
    need: str | None = None
    place_type: str | None = None
    place: dict | None = None  # {"id", "name"} when the question names a place
    region: str | None = None
    when: dict | None = None  # {"label", "start", "end"}
    anchor: dict | None = None  # {"name", "lat", "lon"} the point "near" refers to
    clarify: dict | None = None  # {"question", "options": [{"label", "message"}]}
    topic: str | None = None  # no-data category label, trust topic, out-of-area place
    access: list = field(default_factory=list)  # event access kinds asked for
    unmatched: list = field(default_factory=list)  # names in the question that are not in the data
    unsupported: list = field(default_factory=list)  # asked about, but our data has no such field
    source: str = "rules"  # rules | model

    def validate(self) -> Plan:
        _need(self.intent in INTENTS, f"unknown intent {self.intent!r}")
        _need(self.tool in (None, *TOOLS), f"unknown tool {self.tool!r}")
        _need(isinstance(self.args, dict), "args must be an object")
        _need(self.region in (None, "cincinnati", "oxford"), f"unknown region {self.region!r}")
        if self.when:
            _need(
                _is_date(self.when.get("start")) and _is_date(self.when.get("end")),
                "when needs ISO start and end",
            )
            _need(self.when["start"] <= self.when["end"], "when start is after end")
        if self.clarify:
            _need(bool(self.clarify.get("question")), "clarify needs a question")
        if self.tool:
            _need(
                self.intent in ("events", "route", "area", "nearest", "search", "place", "ada_trust")
                or self.intent.endswith("_trust"),
                f"intent {self.intent!r} cannot run a tool",
            )
        return self

    @classmethod
    def from_dict(cls, d: dict) -> Plan:
        _need(isinstance(d, dict), "plan must be an object")
        names = set(cls.__dataclass_fields__)
        extra = set(d) - names
        _need(not extra, f"unknown plan fields {sorted(extra)}")
        _need("intent" in d, "plan needs an intent")
        return cls(**d).validate()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ToolResult:
    tool: str
    args: dict
    data: object  # list[dict] | dict | None, exactly what the tool returned
    meta: dict = field(default_factory=dict)  # e.g. {"fallback_need": ...}, {"role": "next_events"}

    def to_dict(self) -> dict:
        return {"tool": self.tool, "args": self.args, "data": self.data, "meta": self.meta}


@dataclass
class Source:
    url: str
    date: str = ""
    quote: str = ""
    label: str = ""  # plain-words description of the source

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Fact:
    label: str
    value: str
    detail: str = ""
    quote: str = ""
    source: str = ""
    date: str = ""
    place_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Card:
    place_id: str
    name: str
    type: str
    rating: str
    facts: list = field(default_factory=list)  # list[Fact]
    sources: list = field(default_factory=list)  # list[Source]
    miles: float | None = None
    direction: str | None = None
    distance_text: str | None = None
    phone: str | None = None
    note: str | None = None
    lat: float | None = None
    lon: float | None = None
    event: dict | None = None  # {"title", "start", "when_text", "url", "access"} for event cards

    def to_dict(self) -> dict:
        d = asdict(self)
        d["facts"] = [f if isinstance(f, dict) else f.to_dict() for f in self.facts]
        d["sources"] = [s if isinstance(s, dict) else s.to_dict() for s in self.sources]
        return d


@dataclass
class Sentence:
    """One sentence of the answer with the records it relies on (so it can be checked)."""

    text: str
    refs: list = field(default_factory=list)  # place ids / "fact:<place>:<n>" the sentence leans on
    kind: str = "claim"  # claim | meta | disclaimer
    derived: list = field(default_factory=list)  # numbers/dates computed from results, e.g. "400"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Answer:
    kind: str = "answer"
    headline: list = field(default_factory=list)  # list[Sentence]: the main answer, at most two
    details: list = field(default_factory=list)  # list[Sentence]: behind "More detail"
    cards: list = field(default_factory=list)  # list[Card]
    unknown: list = field(default_factory=list)  # what we could not find
    call: dict | None = None  # {"name", "phone"}
    actions: list = field(default_factory=list)  # [{"type", ...}]
    sources: list = field(default_factory=list)  # list[Source]
    clarify: dict | None = None
    as_of: str | None = None
    notes: list = field(default_factory=list)  # standing wording ("not checked on site")
    verified: bool = False
    removed: int = 0  # sentences the verifier removed
    plan: dict | None = None
    engine: str = "rules"

    def validate(self) -> Answer:
        _need(self.kind in ANSWER_KINDS, f"unknown answer kind {self.kind!r}")
        _need(len(self.headline) <= 2, "the main answer is at most two sentences")
        for s in [*self.headline, *self.details]:
            _need(s.kind in SENTENCE_KINDS, f"unknown sentence kind {s.kind!r}")
        for a in self.actions:
            _need(a.get("type") in ACTION_TYPES, f"unknown action {a.get('type')!r}")
        return self

    @property
    def text(self) -> str:
        return " ".join(s.text for s in self.headline)

    @property
    def full_text(self) -> str:
        return " ".join(s.text for s in [*self.headline, *self.details])

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "headline": [s.to_dict() for s in self.headline],
            "details": [s.to_dict() for s in self.details],
            "cards": [c.to_dict() for c in self.cards],
            "unknown": list(self.unknown),
            "call": self.call,
            "actions": list(self.actions),
            "sources": [s.to_dict() for s in self.sources],
            "clarify": self.clarify,
            "as_of": self.as_of,
            "notes": list(self.notes),
            "verified": self.verified,
            "removed": self.removed,
            "plan": self.plan,
            "engine": self.engine,
        }
