"""The exported assistant data (what guided mode runs on in the browser)."""

import json
from pathlib import Path

import duckdb
import pytest

from atlas.assistant.kb import DB
from atlas.export_assistant_data import LIMIT_BYTES

OUT = Path("data/map/assistant")


@pytest.fixture(scope="module")
def data():
    return {r: json.loads((OUT / f"{r}.json").read_text()) for r in ("cincinnati", "oxford")}


def test_each_region_file_is_small_enough_to_commit_and_to_download():
    for r in ("cincinnati", "oxford", "rules"):
        assert (OUT / f"{r}.json").stat().st_size < LIMIT_BYTES


def test_counts_match_the_knowledge_base(data):
    con = duckdb.connect(str(DB), read_only=True)
    n_places = con.execute("select count(*) from places").fetchone()[0]
    n_facts = con.execute("select count(*) from facts").fetchone()[0]
    n_events = con.execute("select count(*) from events").fetchone()[0]
    assert sum(len(d["places"]) for d in data.values()) == n_places
    assert sum(len(d["facts"]) for d in data.values()) == n_facts
    assert sum(len(d["events"]) for d in data.values()) == n_events


def test_facts_keep_quote_source_and_date(data):
    rows = [f for d in data.values() for f in d["facts"]]
    with_quote = [f for f in rows if f[4]]
    assert len(with_quote) > 100
    assert all(f[5].startswith("http") for f in with_quote)  # a quoted fact always names its source
    assert all(isinstance(f[0], int) for f in rows)


def test_only_public_fields_and_no_private_paths(data):
    blob = json.dumps(data)
    assert "/Users/" not in blob and "data/private" not in blob and "google_places" not in blob.lower()
    assert set(data["oxford"]["places"][0]) <= {"id", "name", "layer", "rating", "lat", "lon", "summary", "notice", "keys",
                                               "newest_source", "address", "phone", "website", "hours", "arrival", "route", "page"}


def test_conditions_are_precomputed_for_every_named_area(data):
    from atlas.assistant.export_assistant_data_keys import key_of  # noqa: F401
def test_conditions_are_precomputed_for_every_named_area(data):
    from atlas.assistant import rules as R
    from atlas.export_assistant_data import key_of

    for a in R.AREAS.values():
        assert key_of(a["lat"], a["lon"]) in data[a["region"]]["areas"], a["name"]


def test_rules_json_carries_what_the_port_needs():
    rules = json.loads((OUT / "rules.json").read_text())
    for k in ("NEED_WORDS", "TYPE_WORDS", "AREAS", "NEEDS", "POSITIVE", "BANNED", "EVENT_STRONG", "HELP_TILES", "RATING_TEXT"):
        assert k in rules, k
