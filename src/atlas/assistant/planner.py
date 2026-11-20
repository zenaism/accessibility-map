"""Rules planner: question + context -> Plan. No model, no network, deterministic.

The JavaScript port (src/atlas/web/assistant/planner.js) follows the same steps in the same order and
reads the same vocabulary (rules.py); golden tests keep the two identical. The steps:

  1 emergency words            -> call 911, stop
  2 help / greeting            -> what I can do
  3 trust questions            -> ADA, conflicting sources, reports from people, how old is the data
  4 out of area                -> "I only cover Cincinnati and Oxford for now"
  5 categories with no data    -> honest "I don't have that yet"
  6 live information           -> bus times, weather, "open now": a snapshot cannot say
  7 events / route / area      -> by words, with dates in words
  8 places by need and type    -> near a named place or area, near the user, or by region
  9 a named place              -> everything known about it
 10 content words              -> search; nothing found becomes "I don't know"
"""

from __future__ import annotations

import math
import re

from . import rules as R
from .dates import default_range, parse_when
from .schema import Context, Plan

_TOKEN = re.compile(r"[a-z0-9]+(?:['\-][a-z0-9]+)*")


def norm(s: str) -> str:
    s = str(s or "").lower().replace("’", "'").replace("mt.", "mt").replace("st.", "st")
    return " ".join(_TOKEN.findall(s))


def tokens(s: str) -> list[str]:
    return norm(s).split(" ") if norm(s) else []


def has(t: str, phrase: str) -> bool:
    return f" {norm(phrase)} " in f" {t} "


def has_any(t: str, phrases) -> str | None:
    for p in phrases:
        if has(t, p):
            return p
    return None


def stem(w: str) -> str:
    w = re.sub(r"'s$", "", w)
    return w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w


def lev(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def tok_match(q: str, n: str) -> bool:
    if q == n:
        return True
    if min(len(q), len(n)) < 7:
        return False
    return lev(q, n) <= (2 if min(len(q), len(n)) >= 10 else 1)


RATING_ORDER = {"accessible": 0, "partial": 1, "not_accessible": 2, "unknown": 3}


class Index:
    """The place names the planner can recognise (id, name, layer, region, rating, lat, lon)."""

    def __init__(self, places: list[dict]):
        self.places = places
        self.generic = {stem(w) for w in tokens(" ".join(R.GENERIC_NAME_WORDS))} | {
            stem(w) for _, words in R.TYPE_WORDS for w in tokens(" ".join(words))
        }
        self.by_id = {p["id"]: p for p in places}
        self.entries = []
        self.all_tokens: set[str] = set()
        df: dict[str, int] = {}
        for p in places:
            self.all_tokens |= {stem(w) for w in tokens(p["name"])}
            if p["layer"] == "restroom":
                continue
            main = re.split(r"[,(]", p["name"])[0]
            toks = list(
                dict.fromkeys(
                    stem(w)
                    for w in tokens(main)
                    if stem(w) not in self.generic and len(w) > 1 and not w.isdigit()
                )
            )
            for w in toks:
                df[w] = df.get(w, 0) + 1
            if toks:
                self.entries.append((p, toks, {stem(w) for w in tokens(main)}))
        self.weight = {w: 1 / math.log(2 + n) for w, n in df.items()}
        self.alias = [(norm(a), norm(b)) for a, b in R.ALIASES]
        self.by_name = {norm(p["name"]): p for p in places if p["layer"] != "restroom"}

    def resolve(self, t: str, region: str | None = None) -> tuple[dict, float] | None:
        """Best place named in the (normalised) text and how completely its name is covered."""
        for a, full in self.alias:
            if has(t, a) and full in self.by_name:
                return self.by_name[full], 1.0
        q = list(dict.fromkeys(stem(w) for w in t.split(" ") if w))
        qset = set(q)
        best = None
        for p, toks, all_toks in self.entries:
            matched = [n for n in toks if any(tok_match(w, n) for w in q)]
            if not matched:
                continue
            total = sum(self.weight[n] for n in toks)
            got = sum(self.weight[n] for n in matched)
            cov = got / total
            if cov < 0.5 or (len(matched) < 2 and got < 0.45 and cov < 0.99):
                continue
            generic_hits = len(all_toks & qset & self.generic)
            key = (
                -round(cov, 6),
                0 if (region is None or p["region"] == region) else 1,
                -len(matched),
                -generic_hits,
                RATING_ORDER.get(p["rating"], 3),
                len(p["name"]),
                p["name"],
            )
            if best is None or key < best[0]:
                best = (key, p, cov)
        return (best[1], best[2]) if best else None


def detect_region(t: str) -> str | None:
    if has(t, "oxford"):
        return "oxford"
    if has(t, "cincinnati") or has(t, "cincy"):
        return "cincinnati"
    for region in R.REGION_KEYS:
        if has_any(t, R.REGION_WORDS[region]):
            return region
    return None


def detect_area(t: str) -> dict | None:
    """Longest named area in the text ("uptown oxford" before "uptown")."""
    hit = None
    for k, v in R.AREAS.items():
        if has(t, k) and (hit is None or len(norm(k)) > len(norm(hit[0]))):
            hit = (k, v)
    return hit[1] if hit else None


def first_need(t: str) -> str | None:
    for need, words in R.NEED_WORDS:
        if has_any(t, words):
            return need
    return None


def first_type(t: str) -> str | None:
    for typ, words in R.TYPE_WORDS:
        if has_any(t, words):
            return typ
    return None


def content_words(t: str, extra=()) -> list[str]:
    skip = set(tokens(" ".join(R.STOP))) | set(extra)
    return [w for w in t.split(" ") if w and w not in skip and len(w) > 1]


def _anchor_place(p: dict) -> dict | None:
    if p.get("lat") is None:
        return None
    return {"name": p["name"], "lat": p["lat"], "lon": p["lon"]}


_CAPS = re.compile(r"[A-Z][a-zA-Z']+")


def capitalized(text: str) -> list[str]:
    """Capitalised words that are not the first word of a sentence."""
    out = []
    for m in _CAPS.finditer(text):
        before = text[: m.start()].rstrip()
        if before == "" or before[-1] in ".?!":
            continue
        out.append(m.group(0))
    return out


def unmatched_names(text: str, index: Index, area_words: set[str]) -> list[str]:
    """Capitalised names in the question that no place, area or region word explains."""
    known = index.all_tokens | area_words | set(tokens(" ".join(R.MONTHS_DAYS + R.KNOWN_CAPS)))
    out = []
    for w in capitalized(text):
        tk = stem(norm(w))
        if tk and tk not in known and tk not in index.generic and len(tk) > 2 and tk not in out:
            out.append(tk)
    return out


def _area_word_set() -> set[str]:
    words = set()
    for k in R.AREAS:
        words |= {stem(w) for w in tokens(k)}
    for ws in R.REGION_WORDS.values():
        for k in ws:
            words |= {stem(w) for w in tokens(k)}
    return words


def _strip_phrases(t: str, phrases) -> str:
    out = f" {t} "
    for p in sorted(phrases, key=lambda x: -len(x)):
        out = out.replace(f" {norm(p)} ", " ")
    return " ".join(out.split())


def plan(text: str, ctx: Context, index: Index) -> Plan:
    pl = _plan(text, ctx, index)
    if pl.intent in ("nearest", "search", "place", "events", "area"):
        t = norm(text)
        pl.unsupported = [p for p in R.UNSUPPORTED if has(t, p)]
    return pl


def _plan(text: str, ctx: Context, index: Index) -> Plan:
    ctx.validate()
    t = norm(text)
    region = detect_region(t) or ctx.region

    # 1 emergency
    if has_any(t, R.EMERGENCY) or (has(t, R.EMERGENCY_SOFT) and not has_any(t, R.EMERGENCY_SOFT_NOT)):
        return Plan("emergency")
    # 2 help (short greetings and "what can you do")
    if has_any(t, R.HELP) and len(t.split(" ")) <= 8 and not first_need(t) and not first_type(t):
        return Plan("help")

    # the place the question names (areas and region words are not places)
    t_places = _strip_phrases(t, [*R.AREAS.keys(), "oxford", "cincinnati", "cincy"])
    hit = index.resolve(t_places, region)
    named, cov = (hit[0], hit[1]) if hit else (None, 0.0)
    place_ref = {"id": named["id"], "name": named["name"]} if named else None
    area_words = _area_word_set()
    unmatched = unmatched_names(text, index, area_words) if named else []

    # 3 trust
    for intent in ("ada_trust", "conflict_trust", "reports_trust", "dates_trust"):
        if has_any(t, R.TRUST[intent]):
            if intent == "dates_trust" and has_any(t, R.EVENT_STRONG):
                break
            pl = Plan(intent, region=region, place=place_ref)
            if named:
                pl.tool, pl.args = "get_place", {"name_or_id": named["id"]}
            return pl
    # 4 out of area
    other = has_any(t, R.OTHER_PLACES)
    if other and not (has(t, "oxford") or has(t, "cincinnati") or has(t, "cincy")):
        return Plan("out_of_area", topic=other.title())
    # 5 categories with no data
    for cat in R.NO_DATA:
        if has_any(t, cat["words"]) and not named:
            return Plan("no_data", topic=cat["label"], region=region)
    # 6 live information
    if has_any(t, R.LIVE_INFO):
        return Plan("live_info", region=region, topic=has_any(t, R.LIVE_INFO), place=place_ref,
                    tool="get_place" if named else None, args={"name_or_id": named["id"]} if named else {})

    when = parse_when(text, ctx.today)
    area = detect_area(t)
    need = first_need(t)
    t_type = _strip_phrases(t, [named["name"]] + [w for w in tokens(named["name"])]) if named else t
    ptype = first_type(t_type)
    access = [k for k, words in R.EVENT_ACCESS.items() if has_any(t, words)]
    if has_any(t, R.EVENT_ACCESS_ALL):
        access = ["audio_description", "asl", "sensory_friendly"]
    qfirst = next((q for phrases, q in R.QUERY_MAP[: R.QUERY_FIRST] if has_any(t, phrases)), None)
    if qfirst and not named:
        return Plan("search", tool="search_places", args={"query": qfirst, **({"region": region} if region else {}), "limit": 5}, region=region)

    # 7a events
    strong = has_any(t, R.EVENT_STRONG)
    weak = has_any(t, R.EVENT_WORDS)
    if strong or (weak and not named and (when or not (need or ptype))):
        words = content_words(t, R.EVENT_FILLER)
        ev_named = named if cov >= 0.99 else None
        if ev_named:
            drop = {stem(x) for x in tokens(ev_named["name"])}
            words = [w for w in words if stem(w) not in drop]
        words = [w for w in words if stem(w) not in area_words]
        w = when or default_range(ctx.today)
        args = {"start": w["start"], "end": w["end"]}
        if region:
            args["region"] = region
        if access:
            args["access"] = access
        if has_any(t, R.EVENT_DISABILITY) and not has_any(t, R.EVENT_ACCESS_ALL):
            args["disability_focused"] = True
        if ev_named:
            args["link_id"] = ev_named["id"]
        elif words and not access:
            args["query"] = " ".join(words[:3])
        return Plan("events", tool="find_events", args=args, region=region, when=when, access=access,
                    place=place_ref if ev_named else None)

    # 7b route
    if has_any(t, R.ROUTE_WORDS):
        if not named:
            return Plan("clarify", region=region, clarify={"question": "Which place do you want to go to?", "options": []})
        blind = ctx.needs.get("mobility") in ("cane", "guide") or "screen_reader" in (ctx.needs.get("rely") or [])
        args = {"to": named["id"], "profile": "blind" if blind else "wheelchair"}
        if ctx.location:
            args["from_lat"], args["from_lon"] = ctx.location[0], ctx.location[1]
        return Plan("route", tool="accessible_route", args=args, region=region or named["region"], place=place_ref)

    # 7c conditions around a point: slopes, stairs, curb ramps, open 311 reports
    if has_any(t, R.AREA_WORDS) and not (need and need not in ("step_free_entrance",)):
        if named and named.get("lat") is not None:
            return Plan("area", tool="area_conditions",
                        args={"lat": named["lat"], "lon": named["lon"], "region": named["region"]},
                        anchor={"name": named["name"], "lat": named["lat"], "lon": named["lon"], "id": named["id"]},
                        place=place_ref, region=named["region"])
        a = area
        if a is None and ctx.location:
            a = {"name": "your location", "lat": ctx.location[0], "lon": ctx.location[1], "region": region}
        if a is None and region:
            a = R.AREAS["uptown oxford" if region == "oxford" else "downtown"]
        if a is None:
            return Plan("clarify", region=region, clarify={"question": "Which area do you mean?", "options": _options_where(text)})
        return Plan("area", tool="area_conditions",
                    args={"lat": a["lat"], "lon": a["lon"], "region": a.get("region") or region},
                    anchor={"name": a["name"], "lat": a["lat"], "lon": a["lon"]}, region=a.get("region") or region)

    # 8 needs and types
    near_phrase = has_any(t, R.NEAR_WORDS) or has_any(t, R.NEAR_ME)
    if (need or ptype or qfirst) and not (named and not near_phrase):
        steps = ctx.needs.get("steps") == "cannot"
        eff = need
        if (not eff or eff == "listed_wheelchair_accessible") and steps and ptype not in ("restroom",):
            eff = "step_free_entrance"
        if not eff and ptype in R.TYPE_DEFAULT_NEED:
            eff = R.TYPE_DEFAULT_NEED[ptype]
        if ptype == "restroom" and not eff:
            eff = "accessible_restroom"
        if eff == "listed_wheelchair_accessible" and ptype not in (None, "food_drink", "restroom"):
            eff = None
        use_type = None if ptype == "restroom" else ptype
        anchor = None
        if named and named.get("lat") is not None:
            anchor = {"name": named["name"], "lat": named["lat"], "lon": named["lon"]}
        if anchor is None and area:
            anchor = {"name": area["name"], "lat": area["lat"], "lon": area["lon"]}
        wants_near = bool(has_any(t, R.NEAR_ME))
        if anchor is None and ctx.location and (wants_near or region is None):
            anchor = {"name": "your location", "lat": ctx.location[0], "lon": ctx.location[1]}
        nearish = eff in ("accessible_restroom", "adult_changing_table", "accessible_parking") or use_type == "food_drink"
        if anchor is None and wants_near and region is None and nearish:
            return Plan("clarify", need=eff, place_type=use_type, region=region,
                        clarify={"question": "Where are you? I use your location only to sort places by distance.",
                                 "options": _options_where(text)})
        if anchor is not None and (eff or use_type) and not qfirst:
            return Plan("nearest", tool="nearest",
                        args={"lat": anchor["lat"], "lon": anchor["lon"], "need": eff, "place_type": use_type, "max_miles": 5.0, "limit": 5},
                        need=eff, place_type=use_type, anchor=anchor, region=region, place=place_ref)
        args = {"region": region, "place_type": use_type, "need": eff, "limit": 5}
        q = _query_map(t)
        if not q and not named:
            miss = unmatched_names(text, index, area_words)
            q = " ".join(miss) if miss else None
        if q:
            args["query"] = q
        return Plan("search", tool="search_places", args={k: v for k, v in args.items() if v is not None},
                    need=eff, place_type=use_type, region=region)

    # 9 a named place
    if named:
        return Plan("place", tool="get_place", args={"name_or_id": named["id"]}, need=need, place=place_ref,
                    region=region or named["region"], unmatched=unmatched)

    # 10 phrases that map to a fixed lookup, then names and content words
    q = _query_map(t)
    if q:
        return Plan("search", tool="search_places", args={"query": q, **({"region": region} if region else {}), "limit": 5}, region=region)
    miss = unmatched_names(text, index, area_words)
    words = miss or content_words(t)
    if words:
        return Plan("search", tool="search_places",
                    args={"query": " ".join(words[:4]), **({"region": region} if region else {}), "limit": 5},
                    region=region, topic="words")
    return Plan("unknown", region=region)


def _query_map(t: str) -> str | None:
    for phrases, query in R.QUERY_MAP:
        if has_any(t, phrases):
            return query
    return None


def _options_where(text: str) -> list[dict]:
    return [
        {"label": "Use my location", "message": text, "action": "locate"},
        {"label": "Downtown Cincinnati", "message": f"{text} near downtown Cincinnati"},
        {"label": "Uptown Oxford", "message": f"{text} near uptown Oxford"},
    ]
