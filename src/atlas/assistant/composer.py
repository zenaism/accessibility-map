# ruff: noqa: E501
"""Template composer: tool results -> Answer. Fixed sentence templates, filled from records only.

Every sentence names the records it leans on (`refs`) so the verifier can check it. Wording rules:
short sentences, the main answer in the first two, details behind "More detail", "not checked on site"
for computed facts, a source and date for every fact, and "I don't know" when the data has no answer.
The JavaScript port (composer.js) is checked against this file with golden cases, so keep both in step.
"""

from __future__ import annotations

import math
import re

from . import rules as R
from .dates import MONTHS, range_text, when_text
from .schema import Answer, Card, Context, Fact, Plan, Sentence, Source, ToolResult
from .tools import NEEDS, POSITIVE

MAX_CARDS = 3


def rhu(x: float) -> int:
    return math.floor(x + 0.5)


def S(text: str, refs=None, kind: str = "claim", derived=None) -> Sentence:
    return Sentence(text, list(refs or []), kind, list(derived or []))


def clip(s: str, n: int = 90) -> str:
    s = " ".join(str(s).split())
    if len(s) <= n:
        return s
    cut = s[:n]
    i = cut.rfind(" ")
    return (cut[:i] if i > n // 2 else cut).rstrip(" ,;:.") + "…"


def full_date(iso: str | None) -> str:
    """13 November 2026"""
    if not iso or len(iso) < 10:
        return iso or ""
    from .dates import MONTHS

    return f"{int(iso[8:10])} {MONTHS[int(iso[5:7]) - 1].title()} {iso[:4]}"


def month_year(d: str) -> str:
    from .dates import MONTHS

    if len(d) >= 10:
        return f"{int(d[8:10])} {MONTHS[int(d[5:7]) - 1][:3].title()} {d[:4]}"
    if len(d) >= 7:
        return f"{MONTHS[int(d[5:7]) - 1][:3].title()} {d[:4]}"
    return d


def source_words(url: str) -> str:
    u = str(url or "").lower()
    for host, words in R.SOURCE_KINDS:
        if host in u:
            return words
    m = re.match(r"https?://(?:www\.)?([^/]+)", u)
    return f"the website {m.group(1)}" if m else "a listed source"


def age_words(d: str, today: str) -> str:
    if not d:
        return "no date given"
    out = month_year(d)
    if d[:4].isdigit() and int(today[:4]) - int(d[:4]) >= 2:
        out += f" (old: from {d[:4]})"
    return out


def distance_text(miles: float | None) -> str | None:
    if miles is None:
        return None
    if miles < 0.19:
        return f"about {max(50, rhu(miles * 5280 / 50) * 50)} feet"
    return f"about {rhu(miles * 10) / 10:.1f} miles"


def fmt_phone(p: str | None) -> str | None:
    if not p:
        return p
    d = re.sub(r"\D", "", p)
    if len(d) == 11 and d[0] == "1":
        d = d[1:]
    return f"({d[:3]}) {d[3:6]}-{d[6:]}" if len(d) == 10 else p


def join_or(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " or " + items[-1]


def need_label(need: str | None) -> str:
    return R.NEED_LABELS.get(need or "", "")


def fact_label(attr: str) -> str:
    return R.FACT_LABELS.get(attr, attr)


def fact_text(f: dict) -> str:
    label, v, d = fact_label(f["attribute"]), str(f["value"]), clip(f.get("detail") or "")
    if v in R.VALUE_WORDS:
        return f"{label}: {v}" + (f" ({d})" if d else "")
    return f"{label}: {v}" + (f" ({d})" if d else "")


def positive(f: dict) -> bool:
    return str(f["value"]).split(";")[-1].strip() in POSITIVE


def pick_facts(facts: list[dict], need: str | None, k: int = 4) -> list[dict]:
    attrs = set((NEEDS.get(need or "") or {}).get("facts") or [])
    rel = [f for f in facts if f["attribute"] in attrs and positive(f)]
    rel = [f for f in rel if f.get("quote")] + [f for f in rel if not f.get("quote")]
    if not rel:
        rest = [f for f in facts if f["attribute"] not in R.NOISE_FACTS]
        rest = [f for f in rest if f.get("quote")] + [f for f in rest if not f.get("quote")]
        rest = sorted(
            rest,
            key=lambda f: R.FACT_PRIORITY.index(f["attribute"]) if f["attribute"] in R.FACT_PRIORITY else 99,
        )
        rel = rest or facts
    return rel[:k]


def to_fact(f: dict, pid: str) -> Fact:
    return Fact(
        fact_label(f["attribute"]),
        str(f["value"]),
        f.get("detail") or "",
        f.get("quote") or "",
        f.get("source") or "",
        f.get("date") or "",
        pid,
    )


# ------------------------------------------------ short answers: confidence, shortening, chips ----
MAX_WORDS = 25
LONG_OK = ("unknown", "no_data", "out_of_area")  # these may keep two short sentences
ABBREVIATIONS = {"mt", "st", "dr", "ave", "jr", "sr", "no", "vs", "ft", "inc", "co", "mr", "mrs", "ms"}


def host_of(url: str) -> str:
    m = re.match(r"https?://(?:www\.)?([^/]+)", str(url or "").lower())
    return m.group(1) if m else ""


def date_short(d: str) -> str:
    """Oct 2026 (or just 2016 when only the year is known)."""
    if len(d) >= 7 and d[4] == "-" and d[5:7].isdigit() and 1 <= int(d[5:7]) <= 12:
        return f"{MONTHS[int(d[5:7]) - 1][:3].title()} {d[:4]}"
    return d[:4]


def is_old(d: str, today: str) -> bool:
    return bool(d[:4].isdigit() and int(today[:4]) - int(d[:4]) >= 2)


def card_confidence(card: Card, need: str | None, today: str) -> str:
    spec = NEEDS.get(need or "") or {}
    attrs = {fact_label(a) for a in spec.get("facts") or []}
    layer_ok = bool(spec.get("restroom_layer")) and card.type == R.TYPE_LABELS["restroom"]

    def pos(f) -> bool:
        return str(f.value).split(";")[-1].strip() in POSITIVE

    general = not need or need == "listed_wheelchair_accessible"
    positives = [f for f in card.facts if pos(f) and (not need or f.label in attrs or layer_ok)]
    if general and card.rating != "accessible":
        positives = []  # a partly accessible place is "reported", not "confirmed", by one positive fact

    def newest(fs):
        best = None
        for f in fs:
            if f.date and (best is None or f.date > best.date):
                best = f
        return best

    def line(best, fresh_word: str) -> str:
        host = host_of(best.source) or "a listed source"
        if is_old(best.date, today):
            return f"Old record · {host}, {best.date[:4]}. May be out of date."
        return f"{fresh_word} · {host}, {date_short(best.date)}"

    if positives:
        best = newest(positives)
        if best:
            return line(best, "Confirmed")
        return f"Reported · {host_of(positives[0].source) or 'a listed source'}, no date"
    if card.rating == "unknown":
        hosts = {host_of(f.source) for f in card.facts if f.source}
        if hosts and hosts == {"openstreetmap.org"}:
            return "Not known · OpenStreetMap lists the place, with no access details"
        return "Not known · no access details in our data"
    best = newest(card.facts)
    if best:
        return line(best, "Reported")
    src = next((f.source for f in card.facts if f.source), "")
    if src:
        return f"Reported · {host_of(src) or 'a listed source'}, no date"
    return "Not known · no access details in our data"


def _newest_year(card: Card) -> str:
    ds = [f.date for f in card.facts if f.date]
    return max(ds)[:4] if ds else ""


def need_word(need: str | None, place_type: str | None = None) -> str:
    lab = need_label(need) or R.TYPE_LABELS.get(place_type or "", "") or "access"
    lab = re.sub(r"^(an|a) ", "", lab)
    return re.sub(r"^accessible ", "", lab)


def closer_note(card: Card, need: str | None, place_type: str | None) -> str | None:
    w = need_word(need, place_type)
    if card.confidence.startswith("Old record"):
        return f"Closer, but the {w} record is from {_newest_year(card)} and may be out of date."
    if card.confidence.startswith("Not known"):
        return f"Closer, but I have no {w} details for it."
    return None


def _wc(text: str) -> int:
    return len(text.split())


def _is_boundary(w: str, nxt: str) -> bool:
    if not w or w[-1] not in ".!?" or not nxt or not ("A" <= nxt[0] <= "Z"):
        return False
    if w[-1] == ".":
        base = w.rstrip(".!?").lower()
        if len(base) == 1 or base in ABBREVIATIONS:
            return False  # an initial ("D.") or an abbreviation ("Mt."), not the end of a sentence
    return True


def split_sentences(text: str) -> list[str]:
    words = text.split(" ")
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        if i + 1 < len(words) and _is_boundary(w, words[i + 1]):
            out.append(" ".join(cur))
            cur = []
    if cur:
        out.append(" ".join(cur))
    return out


def _balanced(words: list[str]) -> bool:
    t = " ".join(words)
    return t.count("(") == t.count(")")


def _upper_first(t: str) -> str:
    for i, ch in enumerate(t):
        if ch.isalpha():
            return t[:i] + ch.upper() + t[i + 1 :]
    return t


def cut_sentence(text: str, limit: int = MAX_WORDS) -> tuple[str, str]:
    """(kept, rest): kept has at most `limit` words and ends with a full stop; rest is "" when nothing was cut."""
    words = text.split()
    if len(words) <= limit:
        return text, ""
    n = 0
    for k in range(limit, 2, -1):
        if (words[k - 1].endswith(",") or words[k].startswith("(")) and _balanced(words[:k]):
            n = k
            break
    if not n:
        n = next((k for k in range(limit, 2, -1) if _balanced(words[:k])), limit)
    head = " ".join(words[:n]).rstrip(",;:")
    if head[-1] not in ".!?":
        head += "."
    rest = _upper_first(" ".join(words[n:]).lstrip(",;: "))
    if rest[-1] not in ".!?…":
        rest += "."
    return head, rest


def shorten(a: Answer) -> Answer:
    """The main answer is one sentence of at most 25 words (two short ones for unknown / no_data / out_of_area).
    Whatever is not kept moves, in order, to the front of the details with the same refs, so nothing is lost."""
    units = []
    for s in a.headline:
        for piece in split_sentences(s.text):
            units.append(Sentence(piece, list(s.refs), s.kind, list(s.derived)))
    if not units:
        return a
    two = a.kind in LONG_OK and len(units) >= 2 and _wc(units[0].text) + _wc(units[1].text) <= MAX_WORDS
    keep, moved = (2 if two else 1), []
    kept = units[:keep]
    if not two:
        head, rest = cut_sentence(units[0].text)
        if rest:
            u = units[0]
            kept = [Sentence(head, list(u.refs), u.kind, list(u.derived))]
            moved.append(Sentence(rest, list(u.refs), u.kind, list(u.derived)))
    moved += units[keep:]
    a.headline = kept
    a.details = moved + list(a.details)
    return a


HELP_CHIPS = {
    "restroom": ("Restroom near me", "Where is the closest accessible restroom?"),
    "parking": ("Accessible parking", "Where is accessible parking near me?"),
    "food": ("Step-free food", "Find food with no steps at the door"),
    "events": ("Events this week", "What events are on this week?"),
    "trails": ("Paved trails", "What paved trails are there?"),
}
AT_PLACE = {
    "parking": ("Parking at", "Does {n} have accessible parking?"),
    "entrance": ("Entrance at", "Does {n} have a step-free entrance?"),
    "restroom": ("Restroom at", "Does {n} have an accessible restroom?"),
}
NEED_CATEGORY = {
    "accessible_restroom": "restroom",
    "accessible_parking": "parking",
    "step_free_entrance": "entrance",
}
TYPE_CATEGORY = {"restroom": "restroom", "food_drink": "food", "trail": "trails"}
MAX_LABEL = 28


def short_name(name: str) -> str:
    n = re.sub(r"\s+for the .*$", "", name.strip())
    if len(n.split()) > 1:
        n = re.sub(r"^The\s+", "", n)
    return n.strip(" ,")


def place_label(prefix: str, name: str) -> str:
    words = short_name(name).split()[:3]
    while words and words[-1].lower() in ("&", "and", "of", "the", "for", "at"):
        words.pop()
    while words:
        label = f"{prefix} {' '.join(words)}"
        if len(label) <= MAX_LABEL:
            return label
        words.pop()
    return f"{prefix} there"[:MAX_LABEL]


def answered_category(pl: Plan) -> str | None:
    if pl.intent == "events":
        return "events"
    return NEED_CATEGORY.get(pl.need or "") or TYPE_CATEGORY.get(pl.place_type or "")


def make_followups(a: Answer, pl: Plan) -> list[dict]:
    """Exactly three follow-up chips: never the need just answered; the real place named in the answer when
    there is one; the help tiles as the fallback."""
    done = answered_category(pl) if a.kind == "answer" else None
    chips, used = [], set()
    name = ""
    if a.kind == "answer" and a.cards and pl.intent != "events" and a.cards[0].type != "event":
        name = a.cards[0].name
        if a.cards[0].type == R.TYPE_LABELS["restroom"]:
            name = ""  # a bare restroom has no entrance or parking of its own to ask about
    elif a.kind == "answer" and pl.place:
        name = pl.place.get("name") or ""
    if name:
        for cat in ("parking", "entrance", "restroom"):
            if cat == done or len(chips) == 2:
                continue
            prefix, msg = AT_PLACE[cat]
            chips.append({"label": place_label(prefix, name), "message": msg.format(n=name)})
            used.add("restroom" if cat == "restroom" else cat)
    for cat in ("restroom", "parking", "food", "events", "trails"):
        if len(chips) == 3:
            break
        if cat == done or cat in used:
            continue
        label, msg = HELP_CHIPS[cat]
        chips.append({"label": label, "message": msg})
    for t in R.HELP_TILES:
        if len(chips) == 3:
            break
        if all(t["message"] != c["message"] for c in chips):
            chips.append({"label": t["label"], "message": t["message"]})
    return chips[:3]


KIND_CONFIDENCE = {
    "unknown": "Not known · nothing in our data answers this",
    "no_data": "Not known · we have no data on this topic yet",
    "out_of_area": "Not known · outside Cincinnati and Oxford",
}


def answer_confidence(a: Answer, pl: Plan) -> str:
    if a.kind in KIND_CONFIDENCE:
        return KIND_CONFIDENCE[a.kind]
    if a.kind != "answer":
        return "Guide · not a data answer"
    if pl.intent.endswith("_trust"):
        return "Guide · not a data answer"
    if pl.intent in ("route", "area"):
        return "Computed · map data, not checked on site"
    if a.cards and a.cards[0].confidence:
        return a.cards[0].confidence
    return "Guide · not a data answer"


def finish(a: Answer, pl: Plan) -> Answer:
    """Post-processing for every answer (templates and the model alike): short headline, a confidence line,
    the lead card, three follow-up chips. Safe to run twice."""
    shorten(a)
    for i, c in enumerate(a.cards):
        c.lead = i == 0
    a.confidence = answer_confidence(a, pl)
    a.followups = make_followups(a, pl)
    return a


def card_for(row: dict, need: str | None, ctx: Context, k: int = 4) -> Card:
    facts = pick_facts(row.get("facts") or [], need, k)
    seen, sources = set(), []
    for f in facts:
        key = f.get("source") or ""
        if key and key not in seen:
            seen.add(key)
            sources.append(Source(key, f.get("date") or "", f.get("quote") or "", source_words(key)))
    phone = fmt_phone(row.get("phone"))
    card = Card(
        place_id=row["link_id"],
        name=row["name"],
        type=R.TYPE_LABELS.get(row.get("type"), row.get("type") or ""),
        rating=row["rating"],
        facts=[to_fact(f, row["link_id"]) for f in facts],
        sources=sources,
        miles=row.get("miles"),
        direction=row.get("direction"),
        distance_text=distance_text(row.get("miles")),
        phone=phone,
        note=row.get("notice"),
        lat=row.get("lat"),
        lon=row.get("lon"),
    )
    card.confidence = card_confidence(card, need, ctx.today)
    return card


def event_card(e: dict, ctx: Context, as_of: str | None = None) -> Card:
    c = Card(
        place_id=e["link_id"],
        name=e["place"],
        type="event",
        rating=e["rating"],
        facts=[],
        sources=[Source(e["url"], "", "", source_words(e["url"]))] if e.get("url") else [],
        event={
            "title": e["title"],
            "start": e["start"],
            "when_text": when_text(e["start"]),
            "url": e.get("url") or "",
            "access": [R.ACCESS_WORDS.get(a, a) for a in e.get("access") or []],
        },
    )
    c.confidence = f"Reported · {host_of(e.get('url')) or 'event listing'}, {date_short(as_of or ctx.today)}"
    return c


def _ans(kind, headline, plan, ctx, **kw) -> Answer:
    a = Answer(kind=kind, headline=headline[:2], plan=plan.to_dict(), **kw)
    return a


def _sources(cards: list[Card]) -> list[Source]:
    out, seen = [], set()
    for c in cards:
        for s in c.sources:
            if s.url not in seen:
                seen.add(s.url)
                out.append(s)
    return out


def _data(results: list[ToolResult], tool: str, role: str | None = None):
    for r in results:
        if r.tool == tool and (r.meta.get("role") == role):
            return r
    return None


def _call(row: dict | None):
    return {"name": row["name"], "phone": fmt_phone(row["phone"])} if row and row.get("phone") else None


def _unsupported(pl: Plan) -> list[str]:
    return [f"I don't have information about: {w}." for w in pl.unsupported]


STANDING = "Computed from map data, not checked on site."


def compose(pl: Plan, results: list[ToolResult], ctx: Context, as_of: str | None = None) -> Answer:
    fn = {
        "emergency": _emergency,
        "help": _help,
        "ada_trust": _trust,
        "conflict_trust": _trust,
        "reports_trust": _trust,
        "dates_trust": _trust,
        "out_of_area": _out_of_area,
        "no_data": _no_data,
        "live_info": _live,
        "events": _events,
        "route": _route,
        "area": _area,
        "nearest": _list,
        "search": _list,
        "place": _place,
        "clarify": _clarify,
        "unknown": _unknown,
    }[pl.intent]
    a = fn(pl, results, ctx, as_of)
    a.plan = pl.to_dict()
    a.as_of = as_of if pl.intent not in ("emergency", "out_of_area", "help", "clarify") else None
    return finish(a, pl)


def _emergency(pl, res, ctx, as_of):
    return Answer(
        "emergency",
        [S("If this is an emergency, call 911 now.", [], "meta")],
        actions=[{"type": "call", "name": "Emergency services", "phone": "911"}],
    )


def _help(pl, res, ctx, as_of):
    lines = [
        S("I can look things up about accessible places in Cincinnati and Oxford.", [], "meta"),
        S("Each answer shows its source. I say so when I don't know.", [], "meta"),
    ]
    det = [
        S("I can answer: " + "; ".join(R.CAN_ANSWER) + ".", [], "meta"),
        S("I cannot answer: " + "; ".join(R.CANNOT_ANSWER) + ".", [], "meta"),
    ]
    return Answer("help", lines, details=det)


def _out_of_area(pl, res, ctx, as_of):
    return Answer(
        "out_of_area",
        [
            S("I only cover Cincinnati and Oxford for now.", [], "meta"),
            S(f"I can't help with {pl.topic} yet.", [], "meta"),
        ],
        unknown=[pl.topic],
    )


def _no_data(pl, res, ctx, as_of):
    topic = pl.topic.lower()
    return Answer(
        "no_data",
        [
            S(f"I don't have information about {topic} yet.", [], "meta"),
            S("I can look up restrooms, parking, places to eat, events and trails.", [], "meta"),
        ],
        details=[S("I can answer: " + "; ".join(R.CAN_ANSWER) + ".", [], "meta")],
        unknown=[pl.topic],
    )


def _unknown(pl, res, ctx, as_of):
    return Answer(
        "unknown",
        [
            S("I didn't understand that, or I don't have the data to answer it.", [], "meta"),
            S(
                "Try a button below, or ask about a restroom, parking, food, events, a trail or a place by name.",
                [],
                "meta",
            ),
        ],
        unknown=["that question"],
    )


def _clarify(pl, res, ctx, as_of):
    return Answer("clarify", [S(pl.clarify["question"], [], "meta")], clarify=pl.clarify)


def _live(pl, res, ctx, as_of):
    topic = pl.topic
    place = _data(res, "get_place")
    row = place.data if place and place.data else None
    first = S(f"I can't tell you {topic} because my information is a saved snapshot, not live.", [], "meta")
    second = S(f"It was last updated {full_date(as_of)}.", [], "meta")
    det, call = [], None
    if row:
        call = _call(row)
        if row.get("hours"):
            det.append(
                S(
                    f"The listing for {row['name']} says hours are: {row['hours']}. This may be out of date.",
                    [row["link_id"]],
                )
            )
        if call:
            det.append(S(f"To be sure, call {row['name']} at {call['phone']}.", [row["link_id"]]))
        else:
            det.append(S(f"Check with {row['name']} directly.", [row["link_id"]]))
    else:
        det.append(S("Check with the venue or agency directly for live information.", [], "meta"))
    cards = [card_for(row, None, ctx)] if row else []
    return Answer(
        "unknown",
        [first, second],
        details=det,
        cards=cards,
        call=call,
        unknown=[topic],
        sources=_sources(cards),
    )


def _trust(pl, res, ctx, as_of):
    place = _data(res, "get_place")
    row = place.data if place and place.data else None
    name = row["name"] if row else None
    cards = [card_for(row, None, ctx, 5)] if row else []
    refs = [row["link_id"]] if row else []
    det = []
    if pl.intent == "ada_trust":
        head = [
            S(
                "I can't say whether a place is ADA compliant or safe. That takes a formal survey.",
                [],
                "disclaimer",
            ),
            S(
                f"Here is what public sources say about {name}."
                if name
                else "I only collect what public sources say, with dates.",
                refs,
                "meta",
            ),
        ]
        if row:
            det.append(
                S(
                    f"Map rating for {name}: {R.RATING_TEXT[row['rating']].lower()}, from the facts on the card.",
                    refs,
                )
            )
    elif pl.intent == "conflict_trust":
        head = [
            S("Sources can disagree, so I show each source and its date.", [], "meta"),
            S(
                f"For {name}, check the card to see which source says what."
                if name
                else "Tell me which place you mean.",
                refs,
                "meta",
            ),
        ]
        if row:
            n = len({f["source"] for f in row["facts"] if f["source"]})
            det.append(
                S(
                    f"I have {n} sources for {name}. If they disagree, trust the newest and call to check.",
                    refs,
                    "claim",
                    [str(n)],
                )
            )
    elif pl.intent == "reports_trust":
        head = [
            S(
                "I can't confirm what people say on social media. I only use sources I can name and date.",
                [],
                "meta",
            ),
            S(
                f"If you saw a problem at {name}, use Report a problem so it can be checked."
                if name
                else "If you saw a problem, use Report a problem so it can be checked.",
                refs,
                "meta",
            ),
        ]
    else:
        head = [
            S(
                f"My information is a snapshot from {full_date(as_of)}. Each fact shows the date of its source.",
                [],
                "meta",
            )
        ]
        if row:
            nv = row.get("newest_source")
            head.append(
                S(
                    f"For {name}, the newest source is dated {month_year(nv)}."
                    if nv
                    else f"For {name}, I have no dated source.",
                    refs,
                )
            )
        det.append(
            S(
                "Events are refreshed more often than places. Always call ahead for anything important.",
                [],
                "meta",
            )
        )
    actions = [
        {
            "type": "report",
            "text": f"Problem with information about {name}: " if name else "Problem with information: ",
        }
    ]
    call = _call(row)
    return Answer(
        "answer", head, details=det, cards=cards, actions=actions, call=call, sources=_sources(cards)
    )


def _label_rating(r: str) -> str:
    return R.RATING_TEXT.get(r, "No accessibility rating yet")


def _evidence(row: dict, need, ctx, plain) -> tuple[Sentence | None, dict | None]:
    facts = pick_facts(row.get("facts") or [], need, 1)
    if not facts:
        return None, None
    f = facts[0]
    src = source_words(f.get("source"))
    age = age_words(f.get("date") or "", ctx.today)
    txt = f"{fact_text(f)}. Source: {src}, {age}." if not plain else f"{fact_text(f)}. Source: {src}, {age}."
    return S(txt, [row["link_id"]]), f


def _list(pl, res, ctx, as_of):
    r = res[0] if res else None
    rows = (r.data or []) if r else []
    plain = ctx.plain
    need = r.meta.get("fallback_need") if r and r.meta.get("fallback_need") else pl.need
    where = (
        f"near {pl.anchor['name']}"
        if pl.anchor and pl.anchor["name"] != "your location"
        else ("near you" if pl.anchor else "")
    )
    ask = need_label(pl.need) or R.TYPE_LABELS.get(pl.place_type or "", "")
    if not rows:
        if pl.args.get("query"):
            msg = (
                f"I don't have anything about {pl.args['query']}"
                + (f" with {ask}" if pl.need and ask else "")
                + " in my data."
            )
        elif pl.need and ask:
            msg = f"I don't have a place with {ask}" + (f" {where}" if where else "") + " in my data."
        else:
            msg = "I don't have a matching place" + (f" {where}" if where else "") + " in my data."
        head = [S(msg, [], "meta"), S("I don't know, and I would rather say so than guess.", [], "meta")]
        return Answer(
            "unknown",
            head,
            unknown=[ask or "that"] + [f"{w}" for w in pl.unsupported],
            details=[S("Try another area or another need, or call the place to ask.", [], "meta")],
        )
    # the nearest card with a confirmed, recent record leads; closer cards with old or unknown records get a note
    all_cards = [card_for(x, need, ctx) for x in rows]
    lead_i = next((i for i, c in enumerate(all_cards) if c.confidence.startswith("Confirmed")), 0)
    confirmed = all_cards[lead_i].confidence.startswith("Confirmed")
    order = [lead_i] + [i for i in range(len(rows)) if i != lead_i]
    for i in range(lead_i):
        note = closer_note(all_cards[i], pl.need, pl.place_type)
        if note:
            c = all_cards[i]
            c.note = f"{c.note}. {note}" if c.note else note
    rows = [rows[i] for i in order]
    cards = [all_cards[i] for i in order][:MAX_CARDS]
    first = rows[0]
    nm = first["name"]
    refs = [first["link_id"]]
    if pl.intent == "nearest" and first.get("miles") is not None:
        anchor_t = "you" if pl.anchor["name"] == "your location" else pl.anchor["name"]
        dist = cards[0].distance_text
        of = f"{dist} {first['direction']} of {anchor_t}"
        if confirmed:
            lead = f"The closest one I can confirm is {nm}, {of}."
        else:
            lead = (
                f"The closest place I found with {ask} is {nm}, {of}."
                if pl.need
                else f"The closest {ask or 'place'} I found is {nm}, {of}."
            )
        if pl.anchor["name"] == nm:
            lead = f"{nm} itself has {ask} on record." if pl.need else f"{nm} itself is the closest."
        if plain:
            lead = (
                f"Closest I can confirm: {nm}, {of}."
                if confirmed
                else (f"Closest with {ask}: {nm}, {of}." if pl.need else f"Closest: {nm}, {of}.")
            )
    else:
        pick = "The first I can confirm is" if confirmed else "The first is"
        if pl.need:
            lead = (
                f"{len(rows)} places have {ask} on record; {pick[0].lower() + pick[1:]} {nm}."
                if len(rows) > 1
                else f"One place has {ask} on record: {nm}."
            )
        else:
            lead = (
                f"I found {len(rows)} places that match; {pick[0].lower() + pick[1:]} {nm}."
                if len(rows) > 1
                else f"I found one place that matches: {nm}."
            )
    sents = [
        S(
            lead,
            refs,
            "claim",
            [str(len(rows))]
            + ([re.sub(r"[^0-9.]", "", cards[0].distance_text or "")] if cards[0].distance_text else []),
        )
    ]
    ev, fct = _evidence(first, need, ctx, plain)
    if r.meta.get("fallback_need"):
        sents.append(
            S(
                "No step-free entrance is on record here. These are listed as wheelchair accessible, not checked on site."
                if plain
                else "None of them has a step-free entrance on record, so these are listed as wheelchair accessible by volunteers on OpenStreetMap, not checked on site.",
                refs,
            )
        )
    elif ev:
        sents.append(ev)
    else:
        sents.append(S("I have no detailed facts for it. Call before you go.", refs))
    det = []
    if len(rows) > 1:
        names = []
        for x in rows[1:6]:
            d = distance_text(x.get("miles"))
            names.append(f"{x['name']} ({d} {x['direction']})" if d else x["name"])
        det.append(S("Also on record: " + "; ".join(names) + ".", [x["link_id"] for x in rows[1:6]]))
    if r.meta.get("fallback_need") and ev:
        det.append(ev)
    if r.meta.get("private_removed"):
        n = r.meta["private_removed"]
        det.append(
            S(
                f"I left out {n} restroom{'s' if n > 1 else ''} that OpenStreetMap marks as private.",
                ["tool:" + r.tool],
                "claim",
                [str(n)],
            )
        )
    if pl.intent == "nearest":
        det.append(S("Distances are in a straight line, not a route. Not checked on site.", [], "meta"))
    if first.get("notice"):
        det.append(S(f"Note for {nm}: {first['notice']}.", refs))
    call = _call(first)
    unk = [f"{w}" for w in pl.unsupported]
    ids = [x["link_id"] for x in rows if x.get("lat") is not None]
    actions = [{"type": "show_on_map", "ids": ids}] if ids else []
    return Answer(
        "answer",
        sents,
        details=det,
        cards=cards,
        unknown=unk,
        call=call,
        actions=actions,
        sources=_sources(cards),
    )


def _focus_sentence(row: dict, need: str | None, ctx: Context):
    """One sentence answering "does it have <need>?" from the facts, or saying it is not on record."""
    label = need_label(need)
    facts = [
        f for f in row.get("facts") or [] if f["attribute"] in set((NEEDS.get(need) or {}).get("facts") or [])
    ]
    pos = [f for f in facts if positive(f)]
    if pos:
        f = pos[0]
        return S(f"Yes, {row['name']} lists {label}.", [row["link_id"]]), f
    if facts:
        f = facts[0]
        return S(f"{row['name']} lists {label} as: {fact_text(f)}.", [row["link_id"]]), f
    return S(f"I don't have information about {label} at {row['name']}.", [row["link_id"]], "claim"), None


def _place(pl, res, ctx, as_of):
    r = _data(res, "get_place")
    row = r.data if r else None
    if row is None:
        return Answer(
            "unknown",
            [
                S("I don't have that place in my data.", [], "meta"),
                S("I don't know, and I would rather say so than guess.", [], "meta"),
            ],
            unknown=["that place"],
        )
    refs = [row["link_id"]]
    nm = row["name"]
    unk = []
    if not row.get("hours"):
        unk.append("opening hours")
    if not row.get("phone"):
        unk.append("phone number")
    unk += [f"{w}" for w in pl.unsupported]
    if pl.unmatched:
        mism = " ".join(w.title() for w in pl.unmatched)
        head = [
            S(f"I don't have {nm} on {mism} in my data.", [], "meta"),
            S(
                f"The only {nm} I know is in {row['region'].title()}, so it may not be the one you mean.",
                refs,
            ),
        ]
        cards = [card_for(row, None, ctx, 4)]
        return Answer(
            "unknown",
            head,
            cards=cards,
            unknown=[f"{nm} on {mism}"],
            call=_call(row),
            sources=_sources(cards),
        )
    if pl.need and pl.need != "listed_wheelchair_accessible":
        s1, f = _focus_sentence(row, pl.need, ctx)
        if f:
            s2 = S(
                f"{fact_text(f)}. Source: {source_words(f['source'])}, {age_words(f.get('date') or '', ctx.today)}.",
                refs,
            )
        else:
            s2 = S(f"Here is what I do know about {nm}: {_rating_line(row)}", refs)
            unk.insert(0, need_label(pl.need))
        head = [s1, s2]
        cards = [card_for(row, pl.need, ctx, 5)]
    else:
        facts = pick_facts(row.get("facts") or [], None, 1)
        s1 = S(f"{nm}: {_rating_line(row)}", refs)
        if facts:
            f = facts[0]
            s2 = S(
                f"{fact_text(f)}. Source: {source_words(f['source'])}, {age_words(f.get('date') or '', ctx.today)}.",
                refs,
            )
        else:
            s2 = S("I have no detailed facts for it yet. Call before you go.", refs)
        head = [s1, s2]
        cards = [card_for(row, None, ctx, 5)]
    det = []
    if row.get("summary"):
        det.append(S(f"About: {clip(row['summary'], 300)}", refs))
    if row.get("hours"):
        det.append(S(f"Hours listed: {row['hours']}.", refs))
    if row.get("address"):
        det.append(S(f"Address: {row['address']}.", refs))
    if row.get("notice"):
        det.append(S(f"Note: {row['notice']}.", refs))
    gt = row.get("getting_there") or {}
    if gt.get("arrival"):
        det.append(S(f"Getting there: {gt['arrival']} Computed from map data, not checked on site.", refs))
    ev = row.get("events") or []
    if ev:
        e0 = ev[0]
        det.append(S(f"Next event I have: {e0['title']}, {when_text(e0['start'])}.", refs))
    actions = [{"type": "show_on_map", "ids": refs}] if row.get("lat") is not None else []
    return Answer(
        "answer",
        head,
        details=det,
        cards=cards,
        unknown=unk,
        call=_call(row),
        actions=actions,
        sources=_sources(cards),
    )


def _rating_line(row: dict) -> str:
    base = R.RATING_TEXT.get(row["rating"], "No accessibility rating yet") + " on the map."
    nv = row.get("newest_source")
    return base + (f" Newest source: {month_year(nv)}." if nv else "")


def _events(pl, res, ctx, as_of):
    r = _data(res, "find_events")
    nxt = _data(res, "find_events", "next_events")
    rows = (r.data or []) if r else []
    w = pl.when or None
    span = range_text(w) if w else "in the next 30 days"
    label = f"{w['label']}" if w else "in the next 30 days"
    snap = S(
        f"Events data was last updated {full_date(as_of)}. It is a snapshot, so check with the venue."
        if not ctx.plain
        else f"Events data is from {full_date(as_of)}. It is a snapshot. Check with the venue.",
        ["tool:find_events"],
        "claim",
    )
    adj = join_or([R.ACCESS_ADJ.get(a, a) for a in pl.access]) + " " if pl.access else ""
    spantxt = f" ({span})" if w and w["start"] != w["end"] else ""
    if not rows:
        nrows = (nxt.data or []) if nxt else []
        head = [S(f"I found no {adj}events {label}{spantxt}.", ["tool:find_events"], "claim")]
        if nrows:
            e = nrows[0]
            head.append(
                S(
                    f"The next one I have is {e['title']}, {when_text(e['start'])}, at {e['place']}.",
                    [e["link_id"]],
                )
            )
            cards = [event_card(e, ctx, as_of) for e in nrows[:MAX_CARDS]]
            return Answer(
                "unknown",
                head,
                details=[snap],
                cards=cards,
                unknown=["events in that time"],
                sources=_sources(cards),
            )
        head.append(snap)
        return Answer("unknown", head, unknown=["events in that time"])
    e = rows[0]
    ctitle = e["title"]
    s1 = (
        f"I found {len(rows)} {adj}events {label}; the first is {ctitle}, {when_text(e['start'])}, at {e['place']}."
        if len(rows) > 1
        else f"I found one {adj}event {label}: {ctitle}, {when_text(e['start'])}, at {e['place']}."
    )
    head = [S(s1, [e["link_id"]], "claim", [str(len(rows))]), snap]
    cards = [event_card(x, ctx, as_of) for x in rows[:MAX_CARDS]]
    det = []
    for x in rows[1:8]:
        acc = ", ".join(R.ACCESS_WORDS.get(a, a) for a in x.get("access") or [])
        det.append(
            S(
                f"{x['title']}, {when_text(x['start'])}, at {x['place']}" + (f" ({acc})." if acc else "."),
                [x["link_id"]],
            )
        )
    if e.get("access"):
        det.insert(
            0,
            S(
                "Access for the first event: "
                + ", ".join(R.ACCESS_WORDS.get(a, a) for a in e["access"])
                + ".",
                [e["link_id"]],
            ),
        )
    ids = list(dict.fromkeys(x["link_id"] for x in rows))
    return Answer(
        "answer",
        head,
        details=det,
        cards=cards,
        unknown=[f"{w}" for w in pl.unsupported],
        actions=[{"type": "show_on_map", "ids": ids}],
        sources=_sources(cards),
    )


def _route(pl, res, ctx, as_of):
    r = _data(res, "accessible_route")
    p = _data(res, "get_place")
    row = p.data if p and p.data else None
    d = r.data if r else None
    nm = row["name"] if row else pl.place["name"]
    if not d:
        return Answer(
            "unknown",
            [
                S(f"I don't have a step-free route to {nm} yet.", [], "meta"),
                S("I don't know, and I would rather say so than guess.", [], "meta"),
            ],
            unknown=["a route"],
            call=_call(row),
        )
    refs = [pl.place["id"]]
    s1 = S(
        f"A step-free route to {nm} from {d['from']} is about {d['length_feet']} feet.",
        refs,
        "claim",
        [str(d["length_feet"])],
    )
    s2 = S(
        "It avoids mapped stairs and steep sections. It is computed from map data, not checked on site.",
        [],
        "meta",
    )
    det = [S(x, refs, "claim") for x in d.get("directions") or []]
    if d.get("crossings_text"):
        det.append(S(d["crossings_text"], refs))
    if d.get("compared_with_shortest"):
        det.append(S(d["compared_with_shortest"], refs))
    cards = [card_for(row, None, ctx, 3)] if row else []
    return Answer(
        "answer",
        [s1, s2],
        details=det,
        cards=cards,
        call=_call(row),
        actions=[
            {"type": "route_to", "place_id": pl.place["id"], "profile": pl.args.get("profile", "wheelchair")}
        ],
        sources=_sources(cards),
    )


def _area(pl, res, ctx, as_of):
    r = _data(res, "area_conditions")
    d = r.data if r else None
    nm = pl.anchor["name"] if pl.anchor else "that area"
    if not d or d.get("path_sections") in (None, 0):
        return Answer(
            "unknown",
            [
                S(f"I don't have path data around {nm}.", [], "meta"),
                S("I don't know, and I would rather say so than guess.", [], "meta"),
            ],
            unknown=["paths and slopes"],
        )
    T = ["tool:area_conditions"]
    pct = rhu(d["share_steeper_than_ramp"] * 100) if d.get("share_steeper_than_ramp") is not None else None
    rep = d.get("open_311_reports")
    slope = S(
        f"Around {nm}, about {pct}% of mapped path sections are steeper than a ramp (8.33%). There are {d['stairways']} mapped stairways.",
        T,
        "claim",
        [str(pct), str(d["stairways"])],
    )
    unk, det = [], []
    if pl.topic == "reports" and rep is None:
        head = [S(f"I don't have closure or construction information for {nm}.", [], "meta"), slope]
        unk.append("closures and construction")
    elif pl.topic == "reports":
        head = [
            S(
                f"Near {nm}, {len(rep)} sidewalk or curb problems are open with the city (311). Data through {full_date(d.get('311_data_through'))}.",
                T,
                "claim",
                [str(len(rep))],
            ),
            S(
                "Reports are not closures, and they are not limited to this week. Check with the city.",
                [],
                "meta",
            ),
        ]
        det.append(slope)
        for x in rep[:6]:
            det.append(
                S(f"{x['type']}, opened {full_date(x['opened'])}, priority {x['priority'].lower()}.", T)
            )
    else:
        head = [slope, S(STANDING + " Slopes are estimated from elevation data.", [], "meta")]
        if rep is not None:
            det.append(
                S(
                    f"{len(rep)} open sidewalk or curb reports to the city (311) nearby; data through {full_date(d.get('311_data_through'))}.",
                    T,
                    "claim",
                    [str(len(rep))],
                )
            )
    if d.get("nine_in_ten_sections_at_or_below_percent") is not None:
        det.append(
            S(
                f"Nine in ten path sections are at or below {d['nine_in_ten_sections_at_or_below_percent']}% grade.",
                T,
            )
        )
    if d.get("city_curb_ramps") is not None:
        det.append(
            S(
                f"The city's curb-ramp map shows {d['city_curb_ramps']} curb ramps within {d['radius_feet']} feet.",
                T,
            )
        )
    else:
        unk.append("curb ramps (no curb-ramp inventory exists for this area)")
    det.append(S(STANDING, [], "meta"))
    cards = []
    gp = _data(res, "get_place")
    if gp and gp.data:
        arr = (gp.data.get("getting_there") or {}).get("arrival")
        cards = [card_for(gp.data, None, ctx, 3)]
        if arr:
            det.append(S(f"Getting there: {arr}", [gp.data["link_id"]]))
    return Answer("answer", head, details=det, cards=cards, unknown=unk, sources=_sources(cards))
