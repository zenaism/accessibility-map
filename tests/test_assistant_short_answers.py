# ruff: noqa: E501
"""Short answers ("short answer B"): one-sentence headline, a confidence line, the nearest confirmed place first,
three follow-up chips, and nothing lost (whatever is not in the headline is behind "More").

Runs the real pipeline over the real knowledge base with every golden case and every question in eval/."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pytest
import yaml

from atlas.assistant import composer as C
from atlas.assistant.engine import Engine, events
from atlas.assistant.schema import Answer, Card, Context, Fact, Plan, Sentence

from .assistant_fixtures import TODAY

ROOT = Path(__file__).resolve().parents[1]
FOUNTAIN = [39.1016, -84.5126]


def _questions() -> list[tuple[str, dict]]:
    out = []
    for g in json.loads((ROOT / "tests/js/assistant_golden.json").read_text()):
        out.append((g["q"], g["context"]))
    for f in ("questions.yaml", "golden_cases.yaml", "category_questions.yaml"):
        for q in yaml.safe_load((ROOT / "eval" / f).read_text()):
            text = q.get("question") or q.get("q")
            ctx = {k: v for k, v in q.items() if k in ("today", "region", "location", "plain")}
            ctx.setdefault("today", TODAY)
            out.append((text, ctx))
    seen, uniq = set(), []
    for q, c in out:
        key = (q, json.dumps(c, sort_keys=True))
        if key not in seen:
            seen.add(key)
            uniq.append((q, c))
    return uniq


QUESTIONS = _questions()


@pytest.fixture(scope="module")
def eng():
    from atlas.core import ROOT

    if not (ROOT / "data" / "processed" / "cincinnati" / "slope_3dep_local.entities.parquet").exists():
        pytest.skip("processed data is not in this checkout (the area questions need it)")
    return Engine()


@pytest.fixture(scope="module")
def runs(eng):
    """(question, context, answer after shortening, answer with shortening switched off)."""
    out = []
    real = C.shorten
    for q, ctx in QUESTIONS:
        after = eng.answer(q, Context.from_dict(ctx))
        C.shorten = lambda a: a
        try:
            before = eng.answer(q, Context.from_dict(ctx))
        finally:
            C.shorten = real
        out.append((q, ctx, after, before))
    return out


def words(text: str) -> int:
    return len(text.split())


def toks(text: str) -> Counter:
    return Counter(re.sub(r"[^a-z0-9]", "", w.lower()) for w in text.split() if re.sub(r"[^a-z0-9]", "", w))


def test_the_question_sets_are_real(runs):
    assert len(runs) >= 140


def test_headline_is_one_short_sentence(runs):
    for q, _ctx, a, _b in runs:
        text = a.text
        assert 0 < words(text) <= 25, (q, text)
        if a.kind in ("unknown", "no_data", "out_of_area"):
            assert len(a.headline) <= 2, q
        else:
            assert len(a.headline) == 1, (q, text)
            assert len(C.split_sentences(a.headline[0].text)) == 1, (q, text)
        a.validate()


def test_every_answer_has_a_confidence_line_and_three_chips(runs):
    for q, _ctx, a, _b in runs:
        assert a.confidence.strip(), q
        assert len(a.followups) == 3, (q, a.followups)
        for chip in a.followups:
            assert set(chip) == {"label", "message"}, q
            assert 0 < len(chip["label"]) <= 28 and chip["message"].strip(), (q, chip)
        assert len({c["message"] for c in a.followups}) == 3, q
        for c in a.cards:
            assert c.confidence.strip(), q
            assert c.confidence.split(" · ")[0] in ("Confirmed", "Old record", "Reported", "Not known"), (
                q,
                c.confidence,
            )


def test_lead_is_the_nearest_confirmed_card(runs):
    for q, _ctx, a, _b in runs:
        if a.cards:
            assert [c.lead for c in a.cards] == [True] + [False] * (len(a.cards) - 1), q
        if a.kind != "answer" or not a.cards or a.cards[0].event:
            continue
        intent = a.plan["intent"]
        conf = [c for c in a.cards if c.confidence.startswith("Confirmed")]
        if conf:
            assert a.cards[0].confidence.startswith("Confirmed"), (q, [c.confidence for c in a.cards])
            if intent in ("nearest", "search"):
                assert a.confidence == a.cards[0].confidence, q
                near = [c.miles for c in conf if c.miles is not None]
                if a.cards[0].miles is not None and near:
                    assert a.cards[0].miles <= min(near) + 1e-9, (q, [(c.name, c.miles) for c in a.cards])
        elif intent in ("nearest", "search"):
            assert "confirm" not in a.text.lower(), (q, a.text)
        if intent in ("nearest", "search"):
            rest = [c.miles for c in a.cards[1:] if c.miles is not None]
            assert rest == sorted(rest), (q, rest)


def test_closer_unconfirmed_cards_carry_a_note(runs):
    for q, _ctx, a, _b in runs:
        if a.kind != "answer" or a.plan["intent"] != "nearest" or not a.cards:
            continue
        lead = a.cards[0].miles
        for c in a.cards[1:]:
            if (
                lead is not None
                and c.miles is not None
                and c.miles < lead
                and not c.confidence.startswith(("Confirmed", "Reported"))
            ):
                assert c.note and "Closer, but" in c.note, (q, c.name, c.confidence)


def test_nothing_is_lost_by_shortening(runs):
    for q, _ctx, a, b in runs:
        assert toks(b.full_text) == toks(a.full_text), (q, b.full_text, a.full_text)
        assert [c.place_id for c in a.cards] == [c.place_id for c in b.cards], q
        # the old details are still there, after the sentences that moved in front of them
        assert a.details[len(a.details) - len(b.details) :] == b.details, q
        for s in a.details[: len(a.details) - len(b.details)]:
            assert s.text.strip() and (s.refs or s.kind != "claim"), (q, s)
        assert a.unknown == b.unknown and a.sources == b.sources and a.actions == b.actions, q


def test_the_verifier_still_passes(runs):
    for q, _ctx, a, b in runs:
        if b.verified:
            assert a.verified and a.removed == 0, (q, a.removed)
        assert a.removed <= b.removed, q


def test_followup_chips_plan_to_a_sensible_question(eng, runs):
    ctx = Context(today=TODAY, location=FOUNTAIN)
    cache: dict[str, str] = {}
    bad = []
    for q, _ctx, a, _b in runs:
        for chip in a.followups:
            m = chip["message"]
            if m not in cache:
                cache[m] = eng.plan(m, ctx).intent
            if cache[m] in ("clarify", "unknown", "out_of_area", "no_data"):
                bad.append((q, chip, cache[m]))
        done = C.answered_category(Plan.from_dict(a.plan)) if a.kind == "answer" else None
        prefixes = {
            "restroom": ("Restroom at", "Restroom near me"),
            "parking": ("Parking at", "Accessible parking"),
            "entrance": ("Entrance at",),
            "events": ("Events",),
        }.get(done or "")
        if prefixes:
            assert not any(c["label"].startswith(prefixes) for c in a.followups), (q, a.followups)
    assert not bad, bad[:5]


def test_event_stream_has_followups_and_confidence(eng):
    a = eng.answer("Where is the closest accessible restroom?", Context(today=TODAY, location=FOUNTAIN))
    evs = list(events(a))
    kinds = [e["type"] for e in evs]
    assert "followups" in kinds and kinds.index("followups") > max(
        i for i, k in enumerate(kinds) if k == "card"
    )
    assert kinds.index("followups") < (kinds.index("action") if "action" in kinds else len(kinds))
    meta = next(e for e in evs if e["type"] == "meta")
    assert meta["confidence"] == a.confidence and a.confidence
    card = next(e for e in evs if e["type"] == "card")["card"]
    assert card["lead"] is True and card["confidence"]
    assert len(next(e for e in evs if e["type"] == "followups")["items"]) == 3


# ------------------------------------------------------------------ shorten() ----


def head(*texts, kind="answer", details=()):
    return Answer(
        kind=kind,
        headline=[Sentence(t, ["p1"], "claim", ["3"]) for t in texts],
        details=[Sentence(d, [], "meta") for d in details],
    )


def test_initials_do_not_split_a_sentence():
    t = "Manuel D. & Rhoda Mayerson JCC has accessible parking on record."
    assert C.split_sentences(t) == [t]
    assert C.split_sentences("Mt. Adams is steep. It has stairs.") == [
        "Mt. Adams is steep.",
        "It has stairs.",
    ]
    a = C.shorten(head(t))
    assert a.headline[0].text == t and not a.details


def test_a_sentence_holding_two_sentences_is_split_and_the_rest_moves_to_details():
    a = C.shorten(
        head(
            "I found 2 events in the next 30 days. The first is Story Hour, Saturday 21 November, at the JCC.",
            details=["Old detail."],
        )
    )
    assert [s.text for s in a.headline] == ["I found 2 events in the next 30 days."]
    assert [s.text for s in a.details] == [
        "The first is Story Hour, Saturday 21 November, at the JCC.",
        "Old detail.",
    ]
    assert a.details[0].refs == ["p1"] and a.details[0].derived == ["3"] and a.details[0].kind == "claim"


def test_a_long_sentence_is_cut_at_a_comma_and_the_rest_is_kept():
    long = (
        "The closest place I found with an accessible restroom is the Cincinnati Museum Center at Union Terminal, "
        "about 1200 feet northeast of Fountain Square and also close to the Riverfront Transit Center, which has more."
    )
    assert words(long) > 25
    a = C.shorten(head(long))
    h = a.headline[0].text
    assert words(h) <= 25 and h.endswith("Union Terminal.")
    assert a.details[0].text.startswith("About 1200 feet") and a.details[0].text.endswith("has more.")
    assert toks(long) == toks(a.full_text)


def test_a_long_sentence_without_commas_is_cut_at_word_25():
    long = " ".join(f"word{i}" for i in range(1, 41)) + "."
    a = C.shorten(head(long))
    assert words(a.headline[0].text) == 25 and a.headline[0].text.endswith("word25.")
    assert a.details[0].text.startswith("Word26") and a.details[0].text.endswith("word40.")


def test_unknown_kind_may_keep_two_short_sentences():
    a = C.shorten(head("I don't know.", "There is nothing about that in my data.", kind="unknown"))
    assert len(a.headline) == 2 and not a.details
    a = C.shorten(
        head(
            "I don't have a place with an accessible restroom near the Cincinnati Museum Center yet.",
            "I don't know, and I would rather say so than guess.",
            kind="no_data",
        )
    )
    assert len(a.headline) == 1 and a.details[0].text.startswith("I don't know, and")


def test_shorten_is_safe_to_run_twice():
    a = C.shorten(head("One sentence here. Two sentence there."))
    d = [s.text for s in a.details]
    C.shorten(a)
    assert [s.text for s in a.details] == d


# ------------------------------------------------------------- confidence ----


def card(rating, facts, type_="restroom"):
    return Card(
        "x", "X", type_, rating, [Fact("Accessible restroom", v, "", "", src, d, "x") for v, src, d in facts]
    )


def test_confidence_lines():
    today = "2026-11-20"
    ok = card("accessible", [("yes", "https://www.example.org/a", "2026-10-02")])
    assert C.card_confidence(ok, "accessible_restroom", today) == "Confirmed · example.org, Oct 2026"
    old = card("accessible", [("yes", "https://www.example.org/a", "2016-05-01")])
    assert (
        C.card_confidence(old, "accessible_restroom", today)
        == "Old record · example.org, 2016. May be out of date."
    )
    part = card("partial", [("no", "https://a.org/x", "2026-09")])
    assert C.card_confidence(part, "accessible_restroom", today) == "Reported · a.org, Sep 2026"
    osm = card("unknown", [("unknown", "https://www.openstreetmap.org/node/1", "")])
    assert (
        C.card_confidence(osm, "accessible_restroom", today)
        == "Not known · OpenStreetMap lists the place, with no access details"
    )
    assert C.card_confidence(card("unknown", []), None, today) == "Not known · no access details in our data"


def test_chip_labels_are_short_and_keep_the_full_name_in_the_message():
    assert C.place_label("Parking at", "Aronoff Center for the Arts") == "Parking at Aronoff Center"
    assert C.place_label("Entrance at", "Manuel D. & Rhoda Mayerson JCC") == "Entrance at Manuel D."
    assert len(C.place_label("Restroom at", "Extraordinarily Long-Named Institute")) <= 28
    a = Answer(kind="answer", cards=[Card("x", "Aronoff Center for the Arts", "venue", "accessible")])
    pl = Plan(intent="place", need="accessible_restroom")
    chips = C.make_followups(a, pl)
    assert chips[0] == {
        "label": "Parking at Aronoff Center",
        "message": "Does Aronoff Center for the Arts have accessible parking?",
    }
    assert len(chips) == 3


def test_closer_note_uses_the_real_year_and_need_words():
    old = card("accessible", [("yes", "https://www.example.org/a", "2016-05-01")])
    old.confidence = C.card_confidence(old, "accessible_restroom", "2026-11-20")
    assert (
        C.closer_note(old, "accessible_restroom", None)
        == "Closer, but the restroom record is from 2016 and may be out of date."
    )
    unk = card("unknown", [])
    unk.confidence = C.card_confidence(unk, None, "2026-11-20")
    assert C.closer_note(unk, "accessible_parking", None) == "Closer, but I have no parking details for it."


def test_model_composed_answers_get_the_same_limits(monkeypatch, tmp_path):
    from atlas.assistant import tools

    from .assistant_fixtures import use_small_kb

    be = use_small_kb(monkeypatch, tmp_path)
    long = "Main Library has an accessible restroom, " + "and a very long description " * 8 + "that goes on."

    def talker(pl, results, ctx, as_of, template):
        template.headline = [
            Sentence(long, [template.cards[0].place_id], "claim"),
            Sentence("Another sentence.", [], "meta"),
        ]
        return template

    eng = Engine(backend=be, composer=talker)
    a = eng.answer("does Main Library have an accessible restroom", Context(today=TODAY))
    assert len(a.headline) == 1 and words(a.text) <= 25 and a.confidence and len(a.followups) == 3
    assert "Another sentence." in a.full_text and tools  # nothing dropped, only moved
