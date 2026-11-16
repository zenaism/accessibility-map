"""Cross-source agreement: matching by position, corroboration versus coverage, and conflicts."""

import json

import numpy as np
import pandas as pd

from atlas import fusion


def test_nearest_matches_within_the_tolerance_only():
    a = np.array([[0.0, 0.0], [100.0, 0.0], [500.0, 500.0]])
    b = np.array([[3.0, 4.0], [101.0, 0.0]])
    m = fusion.nearest(a, b, 15)
    assert list(m.hit) == [True, True, False] and abs(m.dist[0] - 5.0) < 1e-9 and list(m.idx[:2]) == [0, 1]
    assert not fusion.nearest(a, np.empty((0, 2)), 15).hit.any()


def frame(rows, **cols):
    return pd.DataFrame(rows, columns=["lat", "lon"]).assign(**cols)


def test_ramps_are_corroborated_and_conflicts_are_counted(monkeypatch):
    osm = pd.concat([
        frame([[0, 0], [0, 0.1]], entity_type="kerb", attribute="kerb", value=["lowered", "flush"]),  # one backed up, one not
        frame([[0.2, 0.2]], entity_type="kerb", attribute="kerb", value=["raised"]),
    ])  # fmt: skip
    inv = frame([[0, 0.00001], [0.5, 0.5], [0.0001, 0]], value=["Good", "Non-Compliant", "Missing"])
    monkeypatch.setattr(fusion, "load", lambda source, region: osm if source == "osm" else inv)
    monkeypatch.setattr(
        fusion,
        "project",
        lambda df, region: np.column_stack([df["lon"].to_numpy() * 111_000, df["lat"].to_numpy() * 111_000]),
    )
    r = fusion.ramps_vs_osm("x", tol_m=15)
    assert (
        r["osm_lowered_or_flush"] == 2
        and r["osm_corroborated_by_inventory"] == 1
        and r["osm_corroboration"] == 0.5
    )
    assert (
        r["inventory_ramps"] == 3 and r["inventory_in_osm"] == 2 and r["osm_coverage_of_inventory"] == 0.667
    )
    assert r["inventory_missing_but_osm_lowered"] == 1  # the inventory says missing, OSM says there is a ramp
    assert r["osm_raised_kerbs"] == 1 and r["osm_raised_where_inventory_has_a_ramp"] == 0


def test_only_the_crowd_source_is_scored_by_corroboration(monkeypatch, tmp_path):
    monkeypatch.setattr(fusion, "CARDS", tmp_path)
    (tmp_path / "agreement_dc.json").write_text(
        json.dumps({"a": {"osm_corroboration": 0.9}, "b": {"osm_corroboration": 0.3}, "c": {}})
    )
    assert fusion.corroboration_for("dc", "osm") == 0.6
    assert (
        fusion.corroboration_for("dc", "dc_ada_curb_ramps") is None
    )  # the official inventory is not penalised for what OSM lacks
    assert fusion.corroboration_for("cincinnati", "osm") is None
