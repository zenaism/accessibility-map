"""The exported routing graph and the golden routes the JavaScript port is checked against."""

import json
import math
from pathlib import Path

import pytest

from atlas import export_routing, routing

pytestmark = pytest.mark.skipif(
    not (routing.PROCESSED / "oxford" / "walk_edges.parquet").exists(),
    reason="walking network not downloaded",
)
GOLDEN = Path(__file__).parent / "golden_routes_oxford.json"


@pytest.fixture(scope="module")
def graph():
    return export_routing.build("oxford")


def test_export_is_deterministic(graph):
    again = export_routing.build("oxford")
    assert json.dumps(graph, sort_keys=True) == json.dumps(again, sort_keys=True)


def test_no_nan_and_valid_endpoints(graph):
    json.dumps(graph, allow_nan=False)  # raises on NaN / Infinity
    n = len(graph["nodes"]["lon"])
    e = graph["edges"]
    assert len({len(v) for v in e.values()}) == 1
    assert all(0 <= x < n for x in e["u"] + e["v"])
    assert all(x > 0 for x in e["len"])
    assert all(c is None or math.isfinite(c) and c > 0 for c in e["cost"] + e["blind"])


def test_stairs_kept_with_no_cost(graph):
    e, stairs = graph["edges"], export_routing.FLAGS["stairs"]
    flagged = [i for i, f in enumerate(e["flags"]) if f & stairs]
    assert flagged
    assert all(e["cost"][i] is None and e["blind"][i] is None for i in flagged)
    assert all(e["cost"][i] is not None for i, f in enumerate(e["flags"]) if not f & stairs)


def test_coordinates_round_trip(graph):
    _, nodes, _, _ = routing.network("oxford")
    lon = 0
    for d, want in zip(graph["nodes"]["lon"], nodes.lon, strict=True):
        lon += d
        assert abs(lon / graph["scale"] - want) < 1e-9


def test_golden_file_covers_the_cases():
    g = json.loads(GOLDEN.read_text())
    assert g["n_pairs"] == len(g["pairs"]) == 20
    cats = {p["category"] for p in g["pairs"]}
    assert {"avoids stairs", "many crossings", "too far", "no route", "same point"} <= cats
    for p in g["pairs"]:
        for prof in ("wheelchair", "blind"):
            r = p["results"][prof]
            assert (r["result"] is None) == (r["reason"] is not None)
            assert "NaN" not in json.dumps(r)
    assert any(p["results"]["wheelchair"]["reason"] == "no_step_free_route" for p in g["pairs"])


def test_golden_matches_current_python_routes():
    g = json.loads(GOLDEN.read_text())
    for p in g["pairs"][:5]:
        r = routing.route("oxford", *p["from"], *p["to"])
        want = p["results"]["wheelchair"]["result"]
        assert (r is None) == (want is None)
        if r:
            assert r["directions"] == want["directions"]
