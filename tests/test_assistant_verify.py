"""The verifier removes anything that is not tied to a record."""

from atlas.assistant.schema import Answer, Context, Plan, Sentence, ToolResult
from atlas.assistant.verify import verify

CTX = Context(today="2026-11-20")
ROW = {
    "link_id": "lib-1", "name": "Main Library", "region": "oxford", "type": "culture", "rating": "accessible",
    "miles": 0.08, "direction": "north", "phone": "+15135550100", "hours": None, "summary": "Public library.",
    "facts": [{"attribute": "Step-free entrance", "value": "yes", "detail": "ramp at the north door",
               "quote": "The north entrance has a ramp.", "source": "https://library.example.org/access", "date": "2026-10-02"}],
}
RESULTS = [ToolResult("nearest", {"lat": 1, "lon": 2}, [ROW])]
PLAN = Plan("nearest", tool="nearest", args={"lat": 1, "lon": 2})


def run(*sentences: Sentence, kind="answer"):
    a = Answer(kind=kind, headline=list(sentences[:2]), details=list(sentences[2:]), as_of="2026-11-13")
    return verify(a, RESULTS, PLAN, CTX, "Where is the nearest accessible restroom?")


def S(text, refs=("lib-1",), kind="claim", derived=()):
    return Sentence(text, list(refs), kind, list(derived))


def rules_broken(*sentences):
    return [i.rule for i in run(*sentences)[1]]


def test_good_sentence_is_kept():
    a, issues = run(S("Main Library is about 400 feet north, and it has a ramp."), S("It is open.", kind="meta"))
    assert not issues and a.verified and len(a.headline) == 2


def test_unknown_record_is_removed():
    assert "unknown_record" in rules_broken(S("Elm Cafe is closest.", refs=("nope-9",)), S("Fine.", kind="meta"))


def test_claim_without_citation_is_removed():
    assert "no_citation" in rules_broken(S("Main Library has a ramp.", refs=()), S("Fine.", kind="meta"))


def test_number_not_in_results_is_removed():
    assert "number_not_in_results" in rules_broken(S("Main Library opens at 9 am and closes at 5 pm."), S("Ok.", kind="meta"))


def test_invented_hours_are_removed():
    # the record has no hours at all, so any time of day is invented
    assert "number_not_in_results" in rules_broken(S("Main Library is open until 8 pm."), S("Ok.", kind="meta"))


def test_distances_computed_from_miles_are_allowed():
    assert not rules_broken(S("It is about 400 feet north."), S("Ok.", kind="meta"))  # 0.08 miles = 422 ft -> 400
    assert "number_not_in_results" in rules_broken(S("It is about 900 feet north."), S("Ok.", kind="meta"))


def test_quote_must_appear_word_for_word():
    assert not rules_broken(S('The library says "The north entrance has a ramp."'), S("Ok.", kind="meta"))
    assert "quote_not_in_record" in rules_broken(S('The library says "All doors are automatic."'), S("Ok.", kind="meta"))


def test_banned_phrases_are_removed():
    for bad in ("Main Library is ADA compliant.", "Main Library is safe for wheelchairs.", "It is guaranteed to be open."):
        assert "banned_phrase" in rules_broken(S(bad), S("Ok.", kind="meta")), bad


def test_only_a_disclaimer_may_say_ada_compliant():
    assert not rules_broken(S("I can't say whether it is ADA compliant.", refs=(), kind="disclaimer"), S("Ok.", kind="meta"))


def test_invented_name_is_removed():
    assert "name_not_in_results" in rules_broken(S("The Riverside Annex has a ramp."), S("Ok.", kind="meta"))


def test_everything_removed_becomes_i_dont_know():
    a, issues = run(S("Main Library is ADA compliant."), S("It opens at 9 am."))
    assert issues and a.kind == "unknown" and "don't know" in a.text and not a.cards and not a.verified


def test_card_for_unknown_record_is_dropped():
    from atlas.assistant.schema import Card

    a = Answer(headline=[S("Ok.", kind="meta")], cards=[Card("ghost", "Ghost Hall", "culture", "accessible")])
    a, issues = verify(a, RESULTS, PLAN, CTX, "q")
    assert not a.cards and issues[0].section == "card"
