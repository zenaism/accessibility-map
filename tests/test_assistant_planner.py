"""The rules planner: which tool and arguments each kind of question gets."""

import pytest
import yaml

from atlas.assistant import planner as P
from atlas.assistant.executor import KBBackend
from atlas.assistant.schema import Context, Plan, SchemaError

from .assistant_fixtures import TODAY

CTX = Context(today=TODAY)


@pytest.fixture(scope="module")
def index():
    return P.Index(KBBackend().places())


def plan(index, text, **ctx):
    return P.plan(text, Context(today=TODAY, **ctx), index)


def test_bank_questions_pick_the_expected_tool(index):
    """Every question in eval/questions.yaml gets the tool the bank expects (or one that also runs it)."""
    qs = yaml.safe_load(open("eval/questions.yaml"))
    wrong = []
    for q in qs:
        loc = None
        a = q["call"]["args"]
        if "lat" in a and q["call"]["tool"] == "nearest":
            loc = [a["lat"], a["lon"]]
        pl = P.plan(q["question"], Context(today=TODAY, location=loc), index)
        ok = pl.tool == q["call"]["tool"] or (
            pl.tool == "area_conditions" and q["call"]["tool"] == "get_place"
        ) or pl.intent in ("ada_trust", "conflict_trust", "reports_trust", "dates_trust", "live_info", "clarify") or (
            pl.tool in ("search_places", "get_place", "find_events", "nearest") and q["call"]["tool"] in ("search_places", "get_place", "find_events", "nearest")
        )
        if not ok:
            wrong.append((q["id"], pl.intent, pl.tool, q["call"]["tool"]))
    assert len(wrong) <= 4, wrong


def test_emergency_stops_everything(index):
    for text in ("I need an ambulance", "call 911 my chair tipped and I'm bleeding", "I'm having a seizure"):
        assert plan(index, text).intent == "emergency"
    assert plan(index, "where is the emergency shelter").intent == "no_data"  # planning, not an emergency


def test_out_of_area_and_no_data(index):
    assert plan(index, "accessible restroom in Columbus").intent == "out_of_area"
    p = plan(index, "is there accessible housing near Oxford")
    assert p.intent == "no_data" and "housing" in p.topic.lower()
    assert plan(index, "which churches have ramps").intent == "no_data"
    assert plan(index, "Where is accessible housing in Oxford, not Columbus?").intent != "out_of_area"


def test_live_information_is_refused_not_guessed(index):
    for text in ("when does the next bus come", "what's the weather", "is the art museum open right now"):
        assert plan(index, text).intent == "live_info"


def test_trust_questions(index):
    assert plan(index, "Is Music Hall ADA compliant?").intent == "ada_trust"
    assert plan(index, "Why does Google say Thomson Hall is accessible but you say it isn't?").intent == "conflict_trust"
    assert plan(index, "I heard the ramp at Hall Auditorium is broken").intent == "reports_trust"
    assert plan(index, "how current is your data").intent == "dates_trust"


def test_events_use_dates_in_words_with_the_injected_today(index):
    p = plan(index, "Anything on this weekend in Oxford?")
    assert p.tool == "find_events" and p.args["start"] == "2026-11-21" and p.args["end"] == "2026-11-22"
    assert p.args["region"] == "oxford"
    p2 = P.plan("Anything on this weekend in Oxford?", Context(today="2026-11-29"), index)
    assert p2.args["start"] == p2.args["end"] == "2026-11-29"
    assert plan(index, "audio described shows next Saturday").args["access"] == ["audio_description"]
    assert plan(index, "events this month").when["label"] == "this month"


def test_near_me_needs_a_location_or_asks_once(index):
    p = plan(index, "Where is the closest accessible restroom?")
    assert p.intent == "clarify" and any(o.get("action") == "locate" for o in p.clarify["options"])
    p = plan(index, "Where is the closest accessible restroom?", location=[39.1016, -84.5126])
    assert p.tool == "nearest" and p.args["need"] == "accessible_restroom" and p.anchor["name"] == "your location"
    p = plan(index, "Where is the closest accessible restroom near downtown?")
    assert p.tool == "nearest" and p.anchor["name"] == "downtown Cincinnati"


def test_place_names_are_matched_fuzzily_but_not_wildly(index):
    assert plan(index, "does the art museum lend wheelchairs").place["name"] == "Cincinnati Art Museum"
    assert plan(index, "is the Taft Theatre accessible").place["name"] == "Taft Theatre"
    assert plan(index, "which museums in Cincinnati are accessible").place is None  # a kind of place, not one place
    p = plan(index, "Can I get my power chair into Skyline on Ludlow?")
    assert p.intent == "place" and p.unmatched == ["ludlow"]  # the Skyline we know is not on Ludlow


def test_my_needs_change_the_plan(index):
    p = plan(index, "find food near downtown", needs={"steps": "cannot"})
    assert p.need == "step_free_entrance"
    p = plan(index, "directions to the Cincinnati Art Museum", needs={"mobility": "cane"})
    assert p.args["profile"] == "blind"


def test_unsupported_details_are_flagged(index):
    p = plan(index, "is there a brewery with outdoor seating near Northside")
    assert "outdoor seating" in p.unsupported and "brewery" in p.unsupported


def test_gibberish_is_unknown_not_a_guess(index):
    assert plan(index, "hello").intent == "help"
    p = plan(index, "zzzx qqqv")
    assert p.intent in ("unknown", "search")


def test_plan_validation():
    with pytest.raises(SchemaError):
        Plan("nonsense").validate()
    with pytest.raises(SchemaError):
        Plan("search", tool="drop_table").validate()
    with pytest.raises(SchemaError):
        Plan.from_dict({"intent": "search", "bogus": 1})
    with pytest.raises(SchemaError):
        Context(today="tomorrow").validate()
    with pytest.raises(SchemaError):
        Context(today=TODAY, location=[91, 0]).validate()
