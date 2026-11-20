# ruff: noqa: E501
"""Runs the tool call a Plan asks for (plus the small follow-ups every answer needs) and returns the
records. No model is involved. Results carry their evidence (facts with source, date and quote).

The backend is a small object with the tool functions, so the same executor logic runs on the DuckDB
tools here and, ported, on the exported JSON in the browser.
"""

from __future__ import annotations

from datetime import date, timedelta

from . import tools as T
from .schema import Context, Plan, ToolResult

FALLBACK_NEED = {"step_free_entrance": "listed_wheelchair_accessible"}
RESTROOM_NEEDS = ("accessible_restroom", "adult_changing_table")
NOT_PUBLIC = ("private", "no")  # OpenStreetMap access values for a restroom the public may not use


class KBBackend:
    """The real tools over the DuckDB knowledge base (src/atlas/assistant/tools.py)."""

    def __init__(self):
        self._places = None
        self._coords = None

    def coords(self, link_id: str):
        if self._coords is None:
            self._coords = {p["id"]: (p["lat"], p["lon"]) for p in self.places()}
        return self._coords.get(link_id, (None, None))

    def places(self) -> list[dict]:
        if self._places is None:
            con = T._con()
            cur = con.execute(
                "SELECT link_id AS id, name, layer, region, rating, lat, lon FROM places ORDER BY link_id"
            )
            cols = [d[0] for d in cur.description]
            self._places = [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]
        return self._places

    def as_of(self) -> str | None:
        r = T._con().execute("SELECT max(generated) FROM places").fetchone()
        return r[0] if r else None

    def facts(self, link_id: str) -> list[dict]:
        cur = T._con().execute(
            "SELECT attribute, value, detail, quote, source, date FROM facts WHERE link_id = ? ORDER BY rowid",
            [link_id],
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]

    def search_places(self, **kw):
        return T.search_places(**kw)

    def nearest(self, **kw):
        return T.nearest(**kw)

    def get_place(self, name_or_id: str):
        return T.get_place(name_or_id)

    def find_events(self, **kw):
        return T.find_events(**kw)

    def area_conditions(self, lat, lon, region=None):
        return T.area_conditions(lat, lon, region=region)

    def accessible_route(self, **kw):
        return T.accessible_route(**kw)


def _plus_days(iso: str, n: int) -> str:
    return (date.fromisoformat(iso) + timedelta(days=n)).isoformat()


def _enrich(rows: list[dict], be) -> list[dict]:
    for r in rows:
        r["facts"] = be.facts(r["link_id"])
        r["lat"], r["lon"] = be.coords(r["link_id"])
    return rows


def _events(be, args: dict, today: str) -> list[dict]:
    rows = be.find_events(**{**args, "limit": args.get("limit", 10)})
    return [e for e in rows if e["start"][:10] >= today]


def _fetch(fn, a: dict, be) -> tuple[list[dict], dict]:
    """Run a place tool; for restroom needs skip restrooms OpenStreetMap marks as not open to the public."""
    limit = a.get("limit", 5)
    if a.get("need") not in RESTROOM_NEEDS:
        return _enrich(fn(**a), be), {}
    rows = _enrich(fn(**{**a, "limit": limit * 4}), be)
    keep = [
        r
        for r in rows
        if not any(f["attribute"] == "access" and f["value"] in NOT_PUBLIC for f in r["facts"])
    ]
    removed = len(rows[: limit * 4]) - len(keep)
    return keep[:limit], ({"private_removed": removed} if removed else {})


def execute(pl: Plan, ctx: Context, be) -> list[ToolResult]:
    out: list[ToolResult] = []
    a = dict(pl.args)
    if pl.tool in ("search_places", "nearest"):
        fn = be.search_places if pl.tool == "search_places" else be.nearest
        rows, meta = _fetch(fn, a, be)
        if not rows and a.get("need") in FALLBACK_NEED:
            a2 = {**a, "need": FALLBACK_NEED[a["need"]]}
            rows, meta2 = _fetch(fn, a2, be)
            if rows:
                meta = {**meta2, "fallback_need": a2["need"], "wanted": a["need"]}
        out.append(ToolResult(pl.tool, a, rows, meta))
    elif pl.tool == "get_place":
        p = be.get_place(a["name_or_id"])
        if p is not None:
            p["events"] = _events(
                be,
                {"link_id": p["link_id"], "start": ctx.today, "end": _plus_days(ctx.today, 365)},
                ctx.today,
            )
        if p is not None:
            p["lat"], p["lon"] = be.coords(p["link_id"])
        out.append(ToolResult("get_place", a, p))
    elif pl.tool == "find_events":
        rows = _events(be, a, ctx.today)
        meta = {"as_of": be.as_of()}
        out.append(ToolResult("find_events", a, rows, meta))
        if not rows:
            nxt = {k: v for k, v in a.items() if k not in ("start", "end")}
            nxt.update(start=_plus_days(a["end"], 1), end=_plus_days(a["end"], 365), limit=3)
            rows2 = _events(be, nxt, ctx.today)
            out.append(ToolResult("find_events", nxt, rows2, {"role": "next_events", "as_of": be.as_of()}))
    elif pl.tool == "area_conditions":
        out.append(ToolResult("area_conditions", a, be.area_conditions(a["lat"], a["lon"], a.get("region"))))
        if pl.anchor and pl.anchor.get("id"):
            out.append(
                ToolResult("get_place", {"name_or_id": pl.anchor["id"]}, be.get_place(pl.anchor["id"]))
            )
    elif pl.tool == "accessible_route":
        route = be.accessible_route(**a)
        if route:
            route.pop("line", None)
        out.append(ToolResult("accessible_route", a, route))
        out.append(ToolResult("get_place", {"name_or_id": a["to"]}, be.get_place(a["to"])))
    return out
