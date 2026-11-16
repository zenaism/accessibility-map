"""History archives: things that change and cannot be recovered later (docs/data_needs.md section 4).

    python -m atlas.cli archive weather|alerts|transit [--region R]

Each call appends one dated line to data/history/<kind>/<region>/<YYYY-MM>.jsonl with the raw answer, so a forecast model,
an outage predictor or a "last confirmed" statement can be built later from what was true at the time.
  weather  current conditions at the nearest station (National Weather Service, free, no key)
  alerts   active weather alerts for the region (snow, ice, flood, heat): the barriers that come and go
  transit  GTFS-Realtime service alerts of agencies listed in config/history.yaml (detours, elevator outages)
Run it on a schedule (see docs/data_needs.md): hourly is plenty. Every fetch also goes through the fetch ledger.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import requests
import yaml

from .core import ROOT, USER_AGENT, config, now
from .regions import describe

HISTORY = ROOT / "data" / "history"
NWS = "https://api.weather.gov"


def _get(url: str, accept: str = "application/geo+json", **kw) -> requests.Response:
    r = requests.get(url, headers={"User-Agent": USER_AGENT, "Accept": accept}, timeout=30, **kw)
    r.raise_for_status()
    return r


def append(kind: str, region: str, record: dict, when: datetime | None = None) -> Path:
    when = when or datetime.now(UTC)
    f = HISTORY / kind / region / f"{when:%Y-%m}.jsonl"
    f.parent.mkdir(parents=True, exist_ok=True)
    with f.open("a") as fh:
        fh.write(json.dumps({"fetched_at": now(), **record}) + "\n")
    return f


def centre(region: str) -> tuple[float, float]:
    d = describe(config("regions")[region]["osm_relation"])
    return d["lat"], d["lon"]


def weather(region: str) -> dict:
    lat, lon = centre(region)
    pts = _get(f"{NWS}/points/{lat},{lon}").json()["properties"]
    stations = _get(pts["observationStations"]).json()["features"]
    obs = _get(f"{stations[0]['id']}/observations/latest").json()["properties"]
    keep = ("timestamp", "textDescription", "temperature", "windSpeed", "windGust", "precipitationLastHour",
            "relativeHumidity", "visibility", "presentWeather", "barometricPressure")  # fmt: skip
    rec = {
        "region": region,
        "station": stations[0]["properties"]["stationIdentifier"],
        **{k: obs.get(k) for k in keep},
    }
    append("weather", region, rec)
    return rec


def alerts(region: str) -> list[dict]:
    lat, lon = centre(region)
    feats = _get(f"{NWS}/alerts/active", params={"point": f"{lat},{lon}"}).json().get("features", [])
    keep = (
        "id",
        "event",
        "severity",
        "urgency",
        "headline",
        "onset",
        "ends",
        "effective",
        "expires",
        "areaDesc",
    )
    rows = [{k: f["properties"].get(k) for k in keep} for f in feats]
    append("alerts", region, {"region": region, "active": rows})
    return rows


def transit_alerts(region: str) -> list[dict]:
    """GTFS-Realtime alerts for every feed listed for this region in config/history.yaml."""
    from google.transit import gtfs_realtime_pb2

    cfg = yaml.safe_load((ROOT / "config" / "history.yaml").read_text()).get("transit_alerts", {})
    out, tried = [], False
    for name, spec in cfg.items():
        if region not in spec["regions"]:
            continue
        tried = True
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(_get(spec["url"], accept="*/*").content)
        for e in feed.entity:
            if not e.HasField("alert"):
                continue
            a = e.alert
            out.append({
                "feed": name, "id": e.id,
                "header": a.header_text.translation[0].text if a.header_text.translation else "",
                "description": a.description_text.translation[0].text if a.description_text.translation else "",
                "cause": gtfs_realtime_pb2.Alert.Cause.Name(a.cause), "effect": gtfs_realtime_pb2.Alert.Effect.Name(a.effect),
                "periods": [{"start": p.start, "end": p.end} for p in a.active_period],
                "stops": [i.stop_id for i in a.informed_entity if i.stop_id][:50],
                "routes": [i.route_id for i in a.informed_entity if i.route_id][:50],
            })  # fmt: skip
    if tried:  # nothing is written for a region that has no feed
        append("transit", region, {"region": region, "alerts": out})
    return out


KINDS = {"weather": weather, "alerts": alerts, "transit": transit_alerts}
