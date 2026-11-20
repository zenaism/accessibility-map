"""The whole pipeline on the real knowledge base: every bank question gets a verified, short, sourced answer."""

import pytest
import yaml

from atlas.assistant.engine import Engine, events
from atlas.assistant.schema import Answer, Context, Sentence

from .assistant_fixtures import TODAY


@pytest.fixture(scope="module")
def eng():
    return Engine()


def test_all_bank_questions_give_verified_answers(eng):
    qs = yaml.safe_load(open("eval/questions.yaml"))
    for q in qs:
        a = eng.answer(q["question"], Context(today=TODAY))
        assert isinstance(a, Answer) and a.headline, q["id"]
        assert not eng.last_issues, (q["id"], [i.to_dict() for i in eng.last_issues])
        assert len(a.headline) <= 2


def test_every_card_fact_has_a_source_or_is_a_map_tag(eng):
    a = eng.answer("closest accessible restroom near downtown", Context(today=TODAY))
    for c in a.cards:
        for f in c.facts:
            assert f.source, (c.name, f.label)


def test_event_stream_shape(eng):
    evs = list(events(eng.answer("what is on this weekend in Oxford", Context(today=TODAY))))
    kinds = [e["type"] for e in evs]
    assert kinds[0] == "text" and kinds[-1] == "done" and "card" in kinds and "meta" in kinds
    assert evs[-1]["verified"] is True
    assert "parts" in evs[0] and all("card" in e for e in evs if e["type"] == "card")


def test_location_is_used_by_tools_but_never_echoed(eng):
    ans = eng.answer("closest accessible restroom", Context(today=TODAY, location=[39.1016, -84.5126]))
    assert ans.cards[0].miles is not None and ans.cards[0].direction  # the tools used it
    stream = str(list(events(ans)))
    assert "39.1016" not in stream and "-84.5126" not in stream


def test_a_failing_model_falls_back_to_rules(eng):
    def boom(*a, **k):
        raise RuntimeError("model down")

    e = Engine(planner=boom, composer=boom)
    a = e.answer("does the Art Museum lend wheelchairs", Context(today=TODAY))
    assert a.verified and "Cincinnati Art Museum" in a.text


def test_a_composer_that_lies_is_overruled_by_the_verifier(eng):
    def liar(pl, results, ctx, as_of, template):
        template.headline = [
            Sentence("Everything there is ADA compliant and open until 11 pm.", [results[0].data[0]["link_id"]] if isinstance(results[0].data, list) else [], "claim"),
            Sentence("Totally safe for wheelchairs.", [], "claim"),
        ]
        return template

    e = Engine(composer=liar)
    a = e.answer("closest accessible restroom near downtown", Context(today=TODAY))
    assert "ADA compliant" not in a.full_text and "11 pm" not in a.full_text
    assert a.kind == "unknown" and "don't know" in a.text and not a.verified and a.removed == 2
