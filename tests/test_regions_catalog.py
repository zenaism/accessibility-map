"""Region catalog (city switcher): order, keys, coverage words from flags, and the device rule `closest`."""

import json

import pytest

from atlas import regions, report_form, routing_ui
from atlas.core import ROOT, config

KEYS = {
    "id", "name", "short", "tier", "center", "bbox", "buffer_km", "zoom", "has_routes", "has_ratings",
    "has_detail", "places_detail", "places_listed", "layers", "coverage",
}  # fmt: skip


@pytest.fixture
def cat():
    return regions.catalog()


def by_id(cat):
    return {r["id"]: r for r in cat}


def test_order_keys_and_hidden(cat):
    assert [r["id"] for r in cat] == ["cincinnati", "oxford", "dc", "dayton"]
    assert all(set(r) == KEYS for r in cat)
    assert "baltimore" not in by_id(cat)  # no cards: hidden
    assert [r["tier"] for r in cat] == ["full", "full", "limited", "limited"]


def test_coverage_words(cat):
    c = by_id(cat)
    assert c["cincinnati"]["coverage"] == "Places, ratings"
    assert c["oxford"]["coverage"] == "Places, routes, ratings"
    assert c["dc"]["coverage"] == "Places and curb ramps"
    assert c["dayton"]["coverage"] == "Places only"


def test_coverage_follows_flags(monkeypatch):
    monkeypatch.setattr(routing_ui, "ROUTING_REGIONS", ["oxford", "cincinnati"])
    c = by_id(regions.catalog())["cincinnati"]
    assert c["has_routes"] and c["coverage"] == "Places, routes, ratings"
    monkeypatch.setattr(report_form, "RATING_REGIONS", ["oxford"])
    assert (
        by_id(regions.catalog())["cincinnati"]["coverage"] == "Places, routes, ratings"
    )  # full tier wording
    assert not by_id(regions.catalog())["cincinnati"]["has_ratings"]


def test_notice(cat):
    assert regions.notice(by_id(cat)["dc"]) == (
        "Places and curb ramps. Ratings not open yet. Routes are not available yet."
    )
    assert regions.notice("dayton") == "Places only. Ratings not open yet. Routes are not available yet."
    assert regions.notice("oxford") == ""
    assert regions.notice("baltimore") == ""


def test_counts_and_detail(cat):
    c = by_id(cat)
    assert c["cincinnati"]["has_detail"] and c["oxford"]["has_detail"]
    assert c["dc"]["places_detail"] is None and not c["dc"]["has_detail"]
    assert c["dc"]["places_listed"] > 0
    assert "dc_ada_curb_ramps" in c["dc"]["layers"] and c["dc"]["layers"] == sorted(c["dc"]["layers"])


def test_yaml_keys_for_all_five():
    cfg = config("regions")
    assert set(cfg) == {"cincinnati", "oxford", "dc", "dayton", "baltimore"}
    for r in cfg.values():
        assert {"name", "short", "tier", "osm_relation", "buffer_km", "center", "bbox", "zoom"} <= set(r)
        assert r["tier"] in ("full", "limited")
    assert [cfg[k]["tier"] for k in ("cincinnati", "oxford", "dc", "dayton", "baltimore")] == [
        "full", "full", "limited", "limited", "limited",
    ]  # fmt: skip


def test_center_inside_bbox_and_city_sized():
    for k, r in config("regions").items():
        s, w, n, e = r["bbox"]
        lat, lon = r["center"]
        assert s < lat < n and w < lon < e, k
        height = regions.haversine_km(s, w, n, w)
        width = regions.haversine_km(s, w, s, e)
        assert 3 < height < 60 and 3 < width < 60, (k, height, width)


@pytest.mark.parametrize(
    "lat, lon, expected",
    [
        (39.5070, -84.7452, "oxford"),  # Miami University campus
        (39.1031, -84.5120, "cincinnati"),  # downtown
        (39.3995, -84.5613, "cincinnati"),  # Hamilton OH: inside both buffers, deepest in Cincinnati's
        (39.9612, -82.9988, None),  # Columbus
        (39.7589, -84.1916, "dayton"),
        (38.8977, -77.0365, "dc"),
        (39.2904, -76.6122, None),  # Baltimore is hidden
    ],
)
def test_closest(cat, lat, lon, expected):
    assert regions.closest(lat, lon, cat) == expected


def test_haversine():
    assert regions.haversine_km(39.0, -84.0, 39.0, -84.0) == 0
    assert regions.haversine_km(0, 0, 1, 0) == pytest.approx(111.19, abs=0.1)


def test_golden_file_is_current(cat):
    golden = json.loads((ROOT / "tests" / "js" / "regions_golden.json").read_text())
    assert golden and all(regions.closest(g["lat"], g["lon"], cat) == g["expected"] for g in golden)
