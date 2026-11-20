"""The executor on a small synthetic knowledge base (so the results do not depend on today's data)."""

import pytest

from atlas.assistant.executor import execute
from atlas.assistant.planner import Index, plan
from atlas.assistant.schema import Context

from .assistant_fixtures import TODAY, use_small_kb


@pytest.fixture
def kb(monkeypatch, tmp_path):
    be = use_small_kb(monkeypatch, tmp_path)
    return be, Index(be.places())


def run(kb, text, **ctx):
    be, index = kb
    c = Context(today=ctx.pop("today", TODAY), **ctx)
    pl = plan(text, c, index)
    return pl, execute(pl, c, be)


def titles(results):
    return [e["title"] for e in results[0].data]


def test_past_events_are_never_returned(kb):
    pl, res = run(kb, "what events are on in Oxford this month")
    assert "Story Hour" not in titles(res)  # 14 Nov is before today (20 Nov)
    assert titles(res) == ["Sensory Saturday", "Audio Described Film"]
    # the same question asked on the day of the old event does show it
    pl, res = run(kb, "what events are on in Oxford this month", today="2026-11-14")
    assert "Story Hour" in titles(res)


def test_event_access_filter_and_disability_focus(kb):
    pl, res = run(kb, "any audio described shows in december", today="2026-11-20")
    assert pl.args["access"] == ["audio_description"]
    assert res[0].data == []  # Audio Described Film is on 28 Nov, outside December
    pl, res = run(kb, "audio described shows this month")
    assert titles(res) == ["Audio Described Film"]


def test_empty_events_also_looks_for_the_next_one(kb):
    pl, res = run(kb, "any events tomorrow in Oxford")  # nothing on 21 Nov in this synthetic set except Sensory Saturday
    assert titles(res) == ["Sensory Saturday"]
    pl, res = run(kb, "any events on Monday in Oxford")
    assert res[0].data == [] and res[1].meta["role"] == "next_events"
    assert res[1].data[0]["title"] == "Audio Described Film"
    assert res[0].meta["as_of"] == "2026-11-13"


def test_nearest_with_a_location_sorts_by_distance_and_names_direction(kb):
    pl, res = run(kb, "closest accessible restroom", location=[39.5100, -84.7420])
    rows = res[0].data
    assert rows[0]["link_id"] == "lib-1" and rows[0]["direction"] and rows[0]["miles"] < 0.1
    assert {r["link_id"] for r in rows} >= {"lib-1", "rr-1"}


def test_need_falls_back_from_step_free_to_listed_and_says_so(kb):
    pl, res = run(kb, "find a cafe with no steps near uptown oxford")
    assert pl.need == "step_free_entrance"
    assert res[0].meta["fallback_need"] == "listed_wheelchair_accessible"
    assert [r["link_id"] for r in res[0].data] == ["cafe-1"]


def test_get_place_returns_facts_with_evidence_and_only_future_events(kb):
    pl, res = run(kb, "tell me about Main Library")
    p = res[0].data
    assert p["facts"][0]["quote"] and p["facts"][0]["source"] and p["facts"][0]["date"]
    assert [e["title"] for e in p["events"]] == ["Sensory Saturday", "Audio Described Film"]


def test_unknown_things_return_empty_not_made_up(kb):
    pl, res = run(kb, "Where is the waterfall?")
    assert res[0].data == []
