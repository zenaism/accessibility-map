"""Region resolver: candidates, boundary sanity checks and writing to regions.yaml (network mocked)."""

import json

import pytest
import yaml

from atlas import core, regions

SQUARE = {
    "type": "Polygon",
    "coordinates": [[[-84.3, 39.7], [-84.1, 39.7], [-84.1, 39.9], [-84.3, 39.9], [-84.3, 39.7]]],
}
TINY = {
    "type": "Polygon",
    "coordinates": [[[-84.3, 39.7], [-84.299, 39.7], [-84.299, 39.701], [-84.3, 39.701], [-84.3, 39.7]]],
}


@pytest.fixture
def fake(monkeypatch, tmp_path):
    def fetch(url, **kw):
        if url.endswith("/search"):
            return json.dumps([
                {"osm_type": "node", "osm_id": 1, "display_name": "A node", "category": "place", "type": "city"},
                {"osm_type": "relation", "osm_id": 182954, "display_name": "Dayton, Ohio", "category": "boundary",
                 "type": "administrative", "extratags": {"admin_level": "8", "wikidata": "Q34739"}},
            ]).encode()  # fmt: skip
        rel = kw["params"]["osm_ids"]
        geom = TINY if rel == "R999" else SQUARE
        return json.dumps({"features": [{"geometry": geom}]}).encode()

    monkeypatch.setattr(regions, "fetch", fetch)
    f = tmp_path / "regions.yaml"
    f.write_text(
        "# comment kept\ncincinnati:\n  name: Cincinnati, Ohio\n  osm_relation: 183453\n  buffer_km: 25\n"
    )
    monkeypatch.setattr(regions, "FILE", f)
    monkeypatch.setattr(regions, "config", lambda name: yaml.safe_load(f.read_text()))
    monkeypatch.setattr(regions.config, "cache_clear", lambda: None, raising=False)
    return f


def test_search_keeps_only_relations(fake):
    out = regions.search("Dayton, Ohio")
    assert (
        [c["osm_relation"] for c in out] == [182954]
        and out[0]["admin_level"] == "8"
        and out[0]["wikidata"] == "Q34739"
    )


def test_describe_gives_area_from_the_polygon(fake):
    info = regions.describe(182954)
    assert 300 < info["area_km2"] < 500  # a 0.2 x 0.2 degree box near Dayton is about 350 km2


def test_add_appends_and_keeps_comments(fake):
    regions.add("dayton", "Dayton, Ohio", 182954, 20, note="admin_level=8")
    text = fake.read_text()
    assert "# comment kept" in text and "dayton:" in text and "osm_relation: 182954   # admin_level=8" in text
    assert "EPSG:32616" in text  # Dayton is in UTM zone 16


def test_add_refuses_duplicates_bad_keys_and_implausible_areas(fake):
    with pytest.raises(ValueError, match="already exists"):
        regions.add("cincinnati", "x", 5)
    with pytest.raises(ValueError, match="already used"):
        regions.add("other", "x", 183453)
    with pytest.raises(ValueError, match="key must"):
        regions.add("Bad Key", "x", 5)
    with pytest.raises(ValueError, match="implausible"):
        regions.add("tiny", "x", 999)


def test_utm_zone_follows_the_place():
    assert regions.utm_epsg(-84.5, 39.1) == 32616  # Cincinnati
    assert regions.utm_epsg(-77.04, 38.9) == 32618  # Washington DC
    assert core.config("regions")  # the real file still loads
