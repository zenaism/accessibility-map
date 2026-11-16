"""Automatic source discovery: filters keep what is about the region and on topic, and the trust engine rates what is left."""

import json

import pandas as pd
import pytest

from atlas import candidates, discovery

BBOX = [-84.31, 39.70, -84.09, 39.92]
LOCAL = [[-84.4, 39.6], [-84.0, 40.0]]


def item(title, owner="mceogis", extent=LOCAL, typ="Feature Service", **kw):
    return {
        "id": title[:4],
        "title": title,
        "owner": owner,
        "extent": extent,
        "type": typ,
        "modified": 1_700_000_000_000,
        **kw,
    }


def test_extent_filter_drops_world_and_far_away_layers():
    assert discovery.extent_fits(LOCAL, BBOX)
    assert not discovery.extent_fits([[-180, -90], [180, 90]], BBOX)  # world-wide layers overlap everything
    assert not discovery.extent_fits([[-120, 30], [-119, 31]], BBOX)  # somewhere else
    assert not discovery.extent_fits(None, BBOX)


def test_authority_kind_from_the_publisher():
    assert discovery.kind_of("mceogis", "SidewalksCurbRamps") == "official_inventory"  # county engineer GIS
    assert discovery.kind_of("DCGISopendata", "Sidewalks") == "official_inventory"
    assert discovery.kind_of("City of Dayton", "Parks") == "open_dataset"
    assert discovery.kind_of("someuser42", "Sidewalks") == "unknown"


@pytest.fixture
def fake(monkeypatch, tmp_path):
    def fetch(url, **kw):
        if "arcgis" in url:
            return json.dumps(
                {
                    "results": [
                        item("SidewalksCurbRamps"),
                        item("Sidewalks Toronto", owner="EsriTrainingSv", extent=[[-180, -90], [180, 90]]),
                        item("Sidewalk Test Copy"),
                        item("Wine Regions", snippet="vineyards"),
                        item("Parking CSV", typ="CSV", owner="MVRPC", licenseInfo="<p>CC BY 4.0</p>"),
                        item("Some web map", typ="Web Map"),
                    ]
                }
            ).encode()
        return json.dumps({"result": {"results": [{"title": "Dayton ADA curb ramps", "name": "dayton-ada",
                "organization": {"title": "City of Dayton"}, "license_title": "Creative Commons Attribution",
                "metadata_modified": "2025-03-01T00:00:00", "resources": [{"url": "https://data.example.gov/ramps.csv"}]}]}}).encode()  # fmt: skip

    monkeypatch.setattr(discovery, "fetch", fetch)
    monkeypatch.setattr(discovery, "describe", lambda rel: {"bbox": BBOX})
    monkeypatch.setattr(
        discovery, "config", lambda name: {"dayton": {"name": "Dayton, Ohio", "osm_relation": 1}}
    )
    monkeypatch.setattr(candidates, "FILE", tmp_path / "c.csv")
    return tmp_path


def test_discover_keeps_the_right_items_and_rates_them(fake):
    new = discovery.discover("dayton", terms=["sidewalk"])
    titles = {c["title"] for c in new}
    assert titles == {
        "SidewalksCurbRamps",
        "Parking CSV",
        "Dayton ADA curb ramps",
    }  # no world layer, test copy, off-topic or web map
    by = {c["title"]: c for c in new}
    assert (
        by["SidewalksCurbRamps"]["state"] in ("approved", "quarantined", "rejected")
        and by["SidewalksCurbRamps"]["tier"] in "ABCD"
    )
    assert by["Parking CSV"]["licence"] == "CC BY 4.0"  # markup removed from the licence text
    assert (
        by["Dayton ADA curb ramps"]["authority_kind"] == "official_inventory"
        and by["Dayton ADA curb ramps"]["data_year"] == 2025
    )


def test_running_discovery_twice_adds_nothing_new(fake):
    discovery.discover("dayton", terms=["sidewalk"])
    assert discovery.discover("dayton", terms=["sidewalk"]) == []
    assert len(pd.read_csv(candidates.FILE)) == 3
