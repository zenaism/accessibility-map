"""Fact extraction: rules propose, the quote is checked, and the model stage (mocked here) filters and extends."""

import json

import pandas as pd

from atlas.extract import llm, pipeline, rules


def vals(text):
    return {(c.attribute, c.value) for c in rules.find(text)}


def test_polarity_yes_no_and_limited():
    assert ("entrance_step_free", "yes") in vals("The main entrance is step-free.")
    assert ("restroom_accessible", "no") in vals("Accessible restrooms are not available on level 3.")
    assert ("elevator", "limited") in vals("Some exhibits are reachable by elevator only.")


def test_no_steps_is_a_positive_fact_for_the_entrance():
    assert ("entrance_step_free", "yes") in vals("There are no steps at the front entrance of the museum.")


def test_each_rule_finds_its_attribute():
    cases = {
        "adult_changing_table": "An adult changing table is located on the second floor.",
        "wheelchair_loan": "Wheelchairs are available to borrow at the front desk free of charge.",
        "accessible_parking": "Accessible parking is available in Lot B next to the entrance.",
        "asl_interpretation": "ASL interpreters are available with two weeks notice for all programs.",
        "braille": "Braille guides are available at the information desk for visitors.",
        "all_terrain_chair": "Visitors may reserve a free all-terrain chair for the paved trail.",
    }
    for attr, sentence in cases.items():
        assert any(a == attr for a, _ in vals(sentence)), attr


def test_headings_and_short_fragments_are_not_sentences():
    assert (
        rules.find("Braille menus") == []
    )  # too short to be a statement (headline-like text the rules let through is left to the model)
    assert rules.sentences("Hi.\n\nA proper sentence about the elevator on the first floor.") == [
        "A proper sentence about the elevator on the first floor."
    ]


def test_sections_are_kept_with_the_candidate():
    secs = [{"path": "Visit > Accessibility", "text": "The main entrance is step-free and fully accessible."}]
    c = rules.find_in_doc(secs, "")[0]
    assert c.section == "Visit > Accessibility" and c.quote.startswith("The main entrance")


def test_quote_check_ignores_markup_but_catches_invented_text():
    doc = "## Access\n\nThe **main entrance** is [step-free](http://x) for everyone."
    assert pipeline.verify_quote("The main entrance is step-free for everyone.", doc)
    assert not pipeline.verify_quote("The side entrance has a lift.", doc)


def docs_frame(text):
    return pd.DataFrame(
        [{"doc_id": "s:1", "url": "http://x/a", "title": "Museum", "text": text, "sections": json.dumps([])}]
    )


def test_rules_only_extraction_makes_facts_with_provenance():
    f = pipeline.extract_docs(
        docs_frame("The main entrance is step-free. Wheelchairs are available at no charge."), "s", "r"
    )
    assert set(f.attribute) == {"entrance_step_free", "wheelchair_loan"} and f.quote_verified.all()
    row = f[f.attribute == "entrance_step_free"].iloc[0]
    assert (
        row.method == "rules"
        and row.extractor == pipeline.VERSION
        and row.model is None
        and row.evidence_quote.endswith("step-free.")
    )


def test_model_stage_drops_rejected_facts_and_adds_discovered_ones(monkeypatch):
    text = "Cincinnati State's Interpreter Training Program is popular. The lobby has a ramp to the street and elevators."

    def verify(sentence, attribute, proposed):
        return (
            {"states_fact": False, "value": "yes", "detail": ""}
            if "Training Program" in sentence
            else {"states_fact": True, "value": "yes", "detail": "ramp"}
        )

    monkeypatch.setattr(llm, "verify", verify)
    monkeypatch.setattr(
        llm,
        "discover",
        lambda s: (
            [{"attribute": "entrance_step_free", "value": "yes", "detail": "ramp"}] if "ramp" in s else []
        ),
    )
    f = pipeline.extract_docs(docs_frame(text), "s", "r", use_llm=True)
    assert "asl_interpretation" not in set(f.attribute)  # the model said the program name is not a fact
    assert (f.method == "rules+llm").any() and f.model.dropna().eq(llm.MODEL).all()
    assert set(f[f.attribute == "elevator"].method) == {"rules+llm"}


def test_model_answers_are_cached_so_a_rerun_costs_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "CACHE", tmp_path / "c.jsonl")
    monkeypatch.setattr(llm, "_cache", None)
    calls = []
    monkeypatch.setattr(
        llm,
        "_chat",
        lambda prompt, schema, num_predict=200: (
            calls.append(prompt) or {"states_fact": True, "value": "yes", "detail": "x"}
        ),
    )
    a = llm.verify("The main entrance is step-free.", "entrance_step_free", "yes")
    b = llm.verify("The main entrance is step-free.", "entrance_step_free", "yes")
    assert a == b and len(calls) == 1
    monkeypatch.setattr(llm, "_cache", None)  # a new process reads the file
    assert llm.verify("The main entrance is step-free.", "entrance_step_free", "yes") == a and len(calls) == 1


def test_a_model_that_is_down_never_loses_the_rule_facts(monkeypatch):
    def boom(*a, **k):
        raise llm.requests.ConnectionError("down")

    monkeypatch.setattr(llm, "_chat", boom)
    monkeypatch.setattr(llm, "_cache", {})
    monkeypatch.setattr(llm, "CACHE", llm.ROOT / "data" / "cache" / "unused.jsonl")
    f = pipeline.extract_docs(docs_frame("The main entrance is step-free."), "s", "r", use_llm=True)
    assert set(f.attribute) == {
        "entrance_step_free"
    }  # unknown verdict keeps the rule's fact (confidence stays modest)


def test_config_files_agree_with_each_other():
    import yaml

    root = llm.ROOT / "config"
    attrs = yaml.safe_load((root / "attributes.yaml").read_text())
    rules_cfg = yaml.safe_load((root / "fact_rules.yaml").read_text())
    cats = yaml.safe_load((root / "categories.yaml").read_text())
    assert len(attrs) >= 90 and all(isinstance(v, str) and v for v in attrs.values())
    assert set(rules_cfg) <= set(attrs), set(rules_cfg) - set(
        attrs
    )  # every rule belongs to a defined attribute
    for cid, c in cats.items():
        assert set(c["attributes"]) <= set(attrs), (cid, set(c["attributes"]) - set(attrs))
    assert set(llm.text_attributes()) == set(rules_cfg)


def test_vision_answers_are_cached_by_image_and_model(monkeypatch, tmp_path):
    from atlas.extract import vision

    monkeypatch.setattr(vision, "CACHE", tmp_path / "v.jsonl")
    monkeypatch.setattr(vision, "_cache", None)
    calls = []
    monkeypatch.setattr(vision, "_prepare", lambda data: data)
    monkeypatch.setattr(
        vision,
        "_ask",
        lambda img: (
            calls.append(1) or {"kind": "sign", "summary": "A sign", "accessibility_items": ["ramps"]}
        ),
    )
    a, b = vision.describe(b"imagebytes"), vision.describe(b"imagebytes")
    assert a == b and len(calls) == 1 and vision.describe(b"other") and len(calls) == 2


def test_vision_failure_returns_none_not_an_error(monkeypatch):
    from atlas.extract import vision

    monkeypatch.setattr(vision, "_cache", {})
    monkeypatch.setattr(vision, "_prepare", lambda data: data)

    def boom(img):
        raise vision.requests.ConnectionError("down")

    monkeypatch.setattr(vision, "_ask", boom)
    assert vision.describe(b"anything") is None


def test_images_with_little_ocr_text_get_a_description_within_budget(monkeypatch, tmp_path):
    import sys

    from atlas.crawler import docs
    from atlas.extract import vision

    sys.path.insert(0, str(llm.ROOT))
    from tests.crawler_site import POSTER

    f = tmp_path / "poster.png"
    f.write_bytes(POSTER)
    monkeypatch.setattr(
        vision,
        "describe",
        lambda data: {
            "kind": "sign",
            "summary": "A trail map sign",
            "accessibility_items": ["accessible loop"],
        },
    )
    left = [1]
    first = docs.read_file(f, "image/png", "http://x/poster.png", [5], left)
    assert first.method == "ocr+vision" and first.description["kind"] == "sign" and left == [0]
    second = docs.read_file(f, "image/png", "http://x/poster.png", [5], left)  # budget used up
    assert second.method == "ocr" and second.description == {}


def test_questions_and_other_languages_are_not_facts():
    assert rules.find("Is there tactile signage identifying the rest rooms in the building?") == []
    assert (
        rules.find(
            "Pagkatapos dumaan sa ADA faregate, gumawa ng isang malawak na kaliwang U-Turn sa elevator na kumokonekta."
        )
        == []
    )
    assert rules.is_english("The main entrance is step-free and the elevator is on the left.")
    assert not rules.is_english("Continúe hasta el final del vestíbulo del ascensor para llamar al ascensor.")
    assert ("elevator", "yes") in vals("The elevator is located to the left of the visitor services desk.")
