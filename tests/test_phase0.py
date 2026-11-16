"""Phase 0 foundations: schema v2, trust engine, candidate rating, dataset cards, raw manifest."""

import json
from datetime import date

import pandas as pd

from atlas import candidates, schema, trust


def _v1(**over):
    row = dict(
        entity_id="s:1", entity_type="poi", name="x", category="c", attribute="a", value="yes",
        signal="supports", source="cagis_curb_ramps", source_ref="http://r", observed_at="2025-07-15",
        retrieved_at="2026-11-07T18:46:54+00:00", license="CC0", region="cincinnati", lat=39.1, lon=-84.5,
    )  # fmt: skip
    return pd.DataFrame([row | over])


def test_upgrade_adds_history_and_keeps_v1_columns():
    df = schema.upgrade(_v1(), {"cagis_curb_ramps": 90.0})
    assert list(df.columns) == schema.OBS_V2_COLUMNS
    r = df.iloc[0]
    assert r.valid_from == "2025-07-15" and r.snapshot_date == "2026-11-07" and pd.isna(r.valid_to)
    assert r.confidence == 0.9 and r.method == "structured" and r.schema_version == "2.0"


def test_upgrade_valid_from_falls_back_to_snapshot_date():
    df = schema.upgrade(_v1(observed_at=None))
    assert df.iloc[0].valid_from == "2026-11-07" and pd.isna(df.iloc[0].confidence)


def test_validate_flags_problems():
    assert schema.validate(_v1()) == []
    bad = schema.validate(_v1(signal="maybe", lat=120.0, value=None))
    assert (
        any("empty value" in p for p in bad)
        and any("signal" in p for p in bad)
        and any("coordinates" in p for p in bad)
    )


def test_combine_rescales_over_measured_components():
    full = {c: 1.0 for c in trust.COMPONENTS}
    assert trust.combine(full)[0] == 100.0
    partial = full | {"agreement": None, "track_record": None}
    score, used = trust.combine(partial)
    assert score == 100.0 and "agreement" not in used  # missing parts do not drag the score down


def test_tiers_and_cap():
    assert [trust.tier(s) for s in (90, 80, 79.9, 50, 49.9, 30, 29.9)] == list("AABBCCD")
    capped = trust.cap_tier({"tier": "A", "score": 90}, "B", "why")
    assert capped["tier"] == "B" and capped["capped"] == "why"
    assert trust.cap_tier({"tier": "C"}, "B")["tier"] == "C"


def test_freshness_decays_after_the_refresh_interval():
    assert trust.freshness(30, 30) == 1.0 and trust.freshness(None, 30) is None
    assert trust.freshness(120, 30) == 0.0 and 0 < trust.freshness(60, 30) < 1
    assert trust.age_days("2026-11-01T10:00:00+00:00", date(2026, 11, 15)) == 14


def test_fact_confidence_rules():
    base = trust.fact_confidence(80)
    assert base == 0.8
    assert trust.fact_confidence(80, corroborations=2) > base
    assert trust.fact_confidence(80, conflicts=1) < base
    assert trust.fact_confidence(80, age=365, half_life_days=365) == 0.4
    assert trust.fact_confidence(100, corroborations=3) == 1.0  # capped
    assert [trust.shown_as(c) for c in (0.9, 0.5, 0.2, None)] == [
        "confirmed",
        "reported",
        "unknown",
        "unknown",
    ]


def test_candidates_are_rated_automatically_and_unlicensed_are_capped():
    df = pd.DataFrame(columns=candidates.COLUMNS)
    df = candidates.add(
        df,
        url="http://a",
        title="open",
        authority_kind="official_inventory",
        licence="CC BY 4.0",
        data_year=date.today().year,
    )
    df = candidates.add(
        df,
        url="http://b",
        title="no licence",
        authority_kind="official_inventory",
        licence="",
        data_year=date.today().year,
    )
    df = candidates.add(
        df, url="http://c", title="lived", authority_kind="lived_experience", licence="", data_year=None
    )
    df = candidates.add(df, url="http://a", title="duplicate url")  # ignored
    assert len(df) == 3
    out = candidates.rate(df).set_index("title")
    assert out.loc["open", "tier"] == "A" and out.loc["open", "state"] == "approved"
    assert out.loc["no licence", "tier"] == "B" and "licence" in out.loc["no licence", "reason"]
    assert (
        out.loc["lived", "state"] in ("quarantined", "rejected", "approved")
        and out.loc["lived", "tier"] in "BCD"
    )


def test_unclear_licence_text_is_not_mistaken_for_open():
    assert candidates.licence_score("unclear (CC0 in one record, other in another)") == 0.0
    assert candidates.licence_score("CC BY 4.0") == 1.0 and candidates.licence_score("custom terms") == 0.5


def test_seed_candidates_all_rated():
    out = candidates.rate(candidates.seed())
    assert len(out) >= 8 and out["state"].isin(["approved", "quarantined", "rejected"]).all()


def test_raw_manifest_never_records_param_values(tmp_path, monkeypatch):
    from atlas import core

    monkeypatch.setattr(core, "RAW", tmp_path)
    core._manifest("k1", "GET", "http://x/api", {"key": "SECRET", "q": "1"}, 200, b"abc")
    line = json.loads((tmp_path / "manifest.jsonl").read_text())
    assert line["params"] == ["key", "q"] and "SECRET" not in json.dumps(line)
    assert line["sha256"].startswith("ba7816bf") and line["bytes"] == 3


def test_old_facts_lose_weight_at_the_speed_of_their_kind():
    assert trust.half_life("notice") == 14 and trust.half_life("wheelchair_loan") == 365
    assert trust.half_life("entrance_step_free") == 3650 and trust.half_life("something_new") == 1095
    assert trust.aged(0.8, 14, "notice") == 0.4  # a two-week-old closure notice has half its weight
    assert trust.aged(0.8, 365, "wheelchair_loan") == 0.4
    assert trust.aged(0.8, 365, "entrance_step_free") > 0.7  # a year-old entrance fact is still strong
    assert trust.aged(0.8, None, "notice") == 0.8
