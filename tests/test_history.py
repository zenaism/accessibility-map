"""History archives: dated lines, parsed feeds, and nothing written when there is nothing to record."""

import json
from datetime import UTC, datetime

import pytest
from google.transit import gtfs_realtime_pb2

from atlas import history


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(history, "HISTORY", tmp_path / "history")
    monkeypatch.setattr(history, "centre", lambda region: (39.1, -84.5))
    return tmp_path


def lines(tmp_path, kind, region):
    return [
        json.loads(x)
        for f in (tmp_path / "history" / kind / region).glob("*.jsonl")
        for x in f.read_text().splitlines()
    ]


def test_records_are_appended_to_a_monthly_file():
    f = history.append("weather", "x", {"a": 1}, datetime(2026, 11, 3, tzinfo=UTC))
    history.append("weather", "x", {"a": 2}, datetime(2026, 11, 20, tzinfo=UTC))
    history.append("weather", "x", {"a": 3}, datetime(2026, 12, 1, tzinfo=UTC))
    assert f.name == "2026-11.jsonl" and len(f.read_text().splitlines()) == 2
    assert (f.parent / "2026-12.jsonl").exists()


def test_weather_and_alerts_are_archived(monkeypatch, isolated):
    class R:
        def __init__(self, data):
            self.data = data

        def json(self):
            return self.data

    def get(url, accept="application/geo+json", **kw):
        if "/points/" in url:
            return R({"properties": {"observationStations": "https://nws/stations"}})
        if url.endswith("/stations"):
            return R(
                {
                    "features": [
                        {"id": "https://nws/stations/KXYZ", "properties": {"stationIdentifier": "KXYZ"}}
                    ]
                }
            )
        if "observations" in url:
            return R(
                {"properties": {"timestamp": "t", "textDescription": "Snow", "temperature": {"value": -2}}}
            )
        return R(
            {
                "features": [
                    {
                        "properties": {
                            "id": "a1",
                            "event": "Winter Storm Warning",
                            "severity": "Severe",
                            "headline": "Snow",
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(history, "_get", get)
    assert history.weather("x")["textDescription"] == "Snow"
    assert history.alerts("x")[0]["event"] == "Winter Storm Warning"
    assert (
        lines(isolated, "weather", "x")[0]["station"] == "KXYZ"
        and lines(isolated, "alerts", "x")[0]["active"][0]["id"] == "a1"
    )


def test_transit_alerts_are_decoded_and_regions_without_feeds_write_nothing(monkeypatch, isolated):
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"
    e = feed.entity.add()
    e.id = "alert-1"
    e.alert.cause = gtfs_realtime_pb2.Alert.CONSTRUCTION
    e.alert.effect = gtfs_realtime_pb2.Alert.DETOUR
    e.alert.header_text.translation.add().text = "Route 4 detour"
    e.alert.informed_entity.add().stop_id = "S1"

    class R:
        content = feed.SerializeToString()

    monkeypatch.setattr(history, "_get", lambda url, accept="x", **kw: R())
    out = history.transit_alerts("cincinnati")
    assert out[0]["header"] == "Route 4 detour" and out[0]["effect"] == "DETOUR" and out[0]["stops"] == ["S1"]
    assert history.transit_alerts("oxford") == []
    assert not (isolated / "history" / "transit" / "oxford").exists()
