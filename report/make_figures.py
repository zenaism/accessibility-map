#!/usr/bin/env python
"""Numbers, tables and figures for the CSE 486/586 report. Everything printed in the report comes from here.

Needs a checkout of the project's `submission` branch (read-only use; nothing is written into it):

    git worktree add ../atlas-submission submission          # or: git archive submission | tar -x -C <dir>
    PYTHON=<repo>/.venv/bin/python                           # must have geopandas, networkx, pandas<3, matplotlib
    $PYTHON report/make_figures.py --repo ../atlas-submission

Steps: (1) node report/search_bench.js <repo> runs the browser A* against Dijkstra (needs Node 18+),
(2) the routing comparison is recomputed on the 20 golden Oxford routes for the wheelchair and blind profiles,
(3) the A* heuristic is checked against exact distances, (4) tables are collected from the repo's own
result files, (5) figures are drawn at 300 dpi.  Outputs: report/results/*.json, report/figures/*.png.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import statistics as st
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--repo", default=os.environ.get("ATLAS_SUBMISSION"), help="checkout of the submission branch")
ap.add_argument("--out", default=str(HERE))
ap.add_argument("--skip-bench", action="store_true", help="reuse results/search_bench.json")
args = ap.parse_args()
if not args.repo:
    sys.exit("pass --repo <checkout of the submission branch>")
REPO = Path(args.repo).resolve()
OUT = Path(args.out)
RES, FIG = OUT / "results", OUT / "figures"
RES.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)

os.environ["ATLAS_PROCESSED_DIR"] = str(REPO / "sample")
sys.path.insert(0, str(REPO / "src"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

from atlas import routing  # noqa: E402

# Okabe-Ito colour-blind-safe palette
BLUE, ORANGE, PURPLE, GREEN, BLACK, GREY = "#0072B2", "#D55E00", "#CC79A7", "#009E73", "#000000", "#BBBBBB"
W = 3.45  # inches: one column of the IEEE-style template
plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 7,
        "axes.labelsize": 7,
        "axes.titlesize": 7.5,
        "xtick.labelsize": 6.5,
        "ytick.labelsize": 6.5,
        "legend.fontsize": 6.3,
        "axes.linewidth": 0.6,
        "savefig.dpi": 300,
    }
)
GOLDEN = json.loads((REPO / "tests" / "golden_routes_oxford.json").read_text())


# ---------------------------------------------------------------- routing comparison
def path_edges(g, path):
    return [g[a][b] for a, b in zip(path, path[1:], strict=False)]


def no_sidewalk(e):
    return (
        e["highway"] in routing.ROADS and e["footway"] is None and (e.get("sidewalk") or "") in ("", "no", "none", "separate")
    )


def routing_comparison():
    g, nodes, _, lat0 = routing.network("oxford")
    rows, refusals = [], []
    for p in GOLDEN["pairs"]:
        a, da = routing._snap("oxford", *p["from"])
        b, db = routing._snap("oxford", *p["to"])
        want = p["results"]["wheelchair"].get("reason")
        if da > 150 or db > 150:
            refusals.append({"label": p["label"], "why": "too_far", "expected": want})
            continue
        try:
            short = nx.shortest_path(g, a, b, weight="length_m")
        except nx.NetworkXNoPath:  # not connected in the mapped network at all
            refusals.append({"label": p["label"], "why": "no_step_free_route", "expected": want, "stairs_on_shortest": "not connected"})
            continue
        out = {"label": p["label"], "category": p["category"], "same_point": a == b, "paths": {"shortest": short}}
        ok = True
        for prof, w in (("wheelchair", "cost"), ("blind", "cost_blind")):
            try:
                path = nx.shortest_path(g, a, b, weight=w)
            except nx.NetworkXNoPath:
                ok = False
                break
            if not math.isfinite(nx.path_weight(g, path, w)):
                ok = False
                break
            out["paths"][prof] = path
        if not ok:
            stairs = None
            try:
                stairs = routing._summary(g, short)["steps"]
            except Exception:  # noqa: BLE001
                pass
            refusals.append({"label": p["label"], "why": "no_step_free_route", "expected": want, "stairs_on_shortest": stairs})
            continue
        out["summary"] = {k: routing._summary(g, v) for k, v in out["paths"].items()}
        for k in out["summary"]:
            es = path_edges(g, out["paths"][k])
            out["summary"][k]["road_no_sidewalk_m"] = round(sum(e["length_m"] for e in es if no_sidewalk(e)), 1)
        rows.append(out)
    return g, nodes, lat0, rows, refusals


def aggregate(rows, refusals):
    inform = [r for r in rows if not r["same_point"]]
    agg = {"n_pairs": len(GOLDEN["pairs"]), "n_routes": len(rows), "n_informative": len(inform), "refusals": refusals}
    for prof in ("shortest", "wheelchair", "blind"):
        s = [r["summary"][prof] for r in inform]
        d = {
            "stairs": sum(x["steps"] for x in s),
            "steep": sum(x["steep_sections"] for x in s),
            "road_no_sidewalk_m": round(sum(x["road_no_sidewalk_m"] for x in s), 1),
            "length_m": round(sum(x["length_m"] for x in s), 1),
            "crossings": sum(x["crossings"]["total"] for x in s),
            "crossings_signals": sum(x["crossings"]["signals"] for x in s),
            "crossings_audible": sum(x["crossings"]["audible"] for x in s),
            "crossings_unmarked": sum(x["crossings"]["unmarked_or_unknown"] for x in s),
        }
        if prof != "shortest":
            extra = [r["summary"][prof]["length_m"] - r["summary"]["shortest"]["length_m"] for r in inform]
            pct = [100 * e / r["summary"]["shortest"]["length_m"] for e, r in zip(extra, inform, strict=True)]
            d.update(
                extra_mean=round(st.mean(extra), 1),
                extra_median=round(st.median(extra), 1),
                extra_max=round(max(extra), 1),
                extra_pct_mean=round(st.mean(pct), 1),
                extra_pct_median=round(st.median(pct), 1),
                differs_from_shortest=sum(r["paths"][prof] != r["paths"]["shortest"] for r in inform),
                worse_on_a_hazard=[
                    r["label"]
                    for r in inform
                    if r["summary"][prof]["road_no_sidewalk_m"] > r["summary"]["shortest"]["road_no_sidewalk_m"]
                    or r["summary"][prof]["steps"] > r["summary"]["shortest"]["steps"]
                    or r["summary"][prof]["steep_sections"] > r["summary"]["shortest"]["steep_sections"]
                ],
            )
        agg[prof] = d
    agg["wheelchair_path_equals_blind_path"] = sum(r["paths"]["wheelchair"] == r["paths"]["blind"] for r in inform)
    return agg


# ---------------------------------------------------------------- heuristic admissibility
def admissibility(g, nodes, lat0, n_targets=8):
    """h(n) = 0.98 * r * straight_line(n, t), r = lowest cost/length ratio over edges (as routing.js does).
    Compare with exact least cost d(n, t) from Dijkstra for several targets and both profiles."""
    gj = json.loads((REPO / "data/map/routing/oxford.graph.json").read_text())
    E = gj["edges"]
    ratio = {"wheelchair": math.inf, "blind": math.inf}
    for c, b, ln in zip(E["cost"], E["blind"], E["len"], strict=True):
        if c is not None and ln > 0:
            ratio["wheelchair"] = min(ratio["wheelchair"], c / ln)
            ratio["blind"] = min(ratio["blind"], b / ln)
    xy = {r.node_id: (r.lon * math.cos(lat0) * 111320, r.lat * 111320) for r in nodes.itertuples()}
    # per-edge: is the stored length at least the straight-line distance between its ends?
    rel = []
    for a, b, d in g.edges(data=True):
        if a in xy and b in xy:
            s = math.dist(xy[a], xy[b])
            if s > 0:
                rel.append(d["length_m"] / s)
    rng = np.random.default_rng(486)
    ids = list(g.nodes)
    out = {"heuristic_ratio": ratio, "edge_len_over_straight_min": round(min(rel), 4), "edge_len_over_straight_p01": round(float(np.percentile(rel, 1)), 4), "checks": {}}
    for prof, w in (("wheelchair", "cost"), ("blind", "cost_blind")):
        worst, viol, total = 0.0, 0, 0
        for t in rng.choice(ids, n_targets, replace=False):
            d = nx.single_source_dijkstra_path_length(g, int(t), weight=w)
            tx, ty = xy[int(t)]
            for n, dist in d.items():
                if n == t or not math.isfinite(dist) or dist <= 0 or n not in xy:
                    continue
                h = 0.98 * ratio[prof] * math.hypot(xy[n][0] - tx, xy[n][1] - ty)
                total += 1
                worst = max(worst, h / dist)
                viol += h > dist + 1e-9
        out["checks"][prof] = {"pairs_checked": total, "violations": viol, "max_h_over_true_cost": round(worst, 4)}
    return out


# ---------------------------------------------------------------- tables from repo files
def parse_md_table(path: Path) -> dict[str, list[str]]:
    rows = {}
    head = None
    for ln in path.read_text().splitlines():
        if not ln.startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if cells[0] == "metric":
            head = cells
            continue
        if head and not set(cells[0]) <= {"-"} and len(cells) == len(head):
            rows[cells[0]] = cells[1:]
        if head and not ln.strip():
            break
    return rows


def assistant_tables():
    a_new = parse_md_table(REPO / "eval/results/agent_2026-11-23_submission.md")
    abcd = parse_md_table(REPO / "eval/results/agent_2026-11-20.md")
    return {"A_2026-11-23": a_new, "ABCD_2026-11-20": abcd}


def source_table():
    idx = list(csv.DictReader(open(REPO / "data/cards/index.csv")))
    fam = {
        "OpenStreetMap features": lambda i, c: c == "overpass",
        "OSM destinations and entrances": lambda i, c: c in ("osm_destinations", "osm_entrances"),
        "Overture places": lambda i, c: c == "overture",
        "CAGIS curb ramps, sidewalks, stairs, signals": lambda i, c: i.split(".")[1].startswith("cagis"),
        "Cincinnati 311 reports": lambda i, c: c == "socrata",
        "USGS 3DEP slope (path sections)": lambda i, c: i.split(".")[1] == "slope_3dep_local",
        "GTFS bus stops": lambda i, c: c == "gtfs",
        "Venue and agency web pages": lambda i, c: c == "web",
        "Event calendar records": lambda i, c: c in ("events_ical", "mura_calendar"),
    }
    t = {}
    for name, f in fam.items():
        t[name] = {"oxford": 0, "cincinnati": 0, "score": []}
        for r in idx:
            region, src = r["id"].split(".", 1)
            if region in ("oxford", "cincinnati") and f(r["id"], r["connector"]) and r["collected"] == "True":
                t[name][region] += int(r["records"])
                try:
                    t[name]["score"].append(float(r["trust_score"]))
                except ValueError:
                    pass
    tiers = defaultdict(int)
    for r in idx:
        tiers[r["tier"]] += 1
    nodes = pd.read_parquet(REPO / "sample/oxford/walk_nodes.parquet")
    edges = pd.read_parquet(REPO / "sample/oxford/walk_edges.parquet")
    e = edges[edges.length_m > 0]
    return {
        "families": t,
        "tiers_all_64": dict(tiers),
        "n_cards": len(idx),
        "oxford_walk_nodes": len(nodes),
        "oxford_walk_edges_parquet": len(edges),
        "oxford_stair_edges": int(edges.steps.sum()),
        "oxford_edges_grade_gt_8_33_pct": round(float((edges.grade > 8.33).mean() * 100), 1) if "grade" in edges else None,
        "oxford_edges_grade_gt_5_pct": round(float((edges.grade > 5).mean() * 100), 1) if "grade" in edges else None,
        "oxford_edges_with_grade": int(edges.grade.notna().sum()) if "grade" in edges else None,
    }


# ---------------------------------------------------------------- figures
def clean(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def fig_pipeline():
    fig, ax = plt.subplots(figsize=(W, 4.1))
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(0, 1)
    ax.axis("off")

    def box(x, y, w, h, text, fc="#F2F2F2", ec="#555555", ls="-", bold=False):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.004,rounding_size=0.015", fc=fc, ec=ec, lw=0.7, ls=ls))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=6, weight="bold" if bold else "normal", linespacing=1.15)

    def arrow(p, q, ls="-"):
        ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=7, color="#333333", lw=0.7, ls=ls, shrinkA=0, shrinkB=0))

    box(0.0, 0.86, 0.62, 0.13, "Sources: OpenStreetMap, Overture, CAGIS,\nCincinnati 311, USGS 3DEP, GTFS,\nvenue websites", fc="#E8F1F8")
    box(0.69, 0.86, 0.31, 0.13, "Fusion +\ntrust score\n(dataset cards)", ls="--", fc="white")
    arrow((0.62, 0.925), (0.69, 0.925), "--")
    # left branch
    ax.text(0.23, 0.775, "Route search", ha="center", fontsize=6.5, weight="bold", color=BLUE)
    ax.text(0.93, 0.815, "Assistant", ha="center", fontsize=6.5, weight="bold", color="#444444")
    box(0.0, 0.62, 0.46, 0.12, "Walking graph: OSM paths\n+ USGS slope per edge")
    box(0.0, 0.45, 0.46, 0.12, "Edge cost = length x penalties\n(stairs, slope, sidewalk, kerb,\ncrossing)")
    box(0.0, 0.28, 0.46, 0.12, "A* search (routing.js)\nvs plain shortest path", fc="#DCEBF7", bold=True)
    box(0.54, 0.62, 0.46, 0.12, "Knowledge base (DuckDB):\nplaces, quoted facts, events")
    box(0.54, 0.45, 0.46, 0.12, "Rule planner (optional\nlocal model fills slots)\nthen tool executor")
    box(0.54, 0.28, 0.46, 0.12, "Composer writes sentences,\nverifier keeps cited ones", fc="#EEEEEE", bold=True)
    for x in (0.23, 0.77):
        arrow((x, 0.62), (x, 0.57))
        arrow((x, 0.45), (x, 0.40))
    arrow((0.23, 0.86), (0.23, 0.74))
    ax.plot([0.5, 0.5, 0.77], [0.86, 0.80, 0.80], color="#333333", lw=0.7)
    arrow((0.77, 0.80), (0.77, 0.74))
    box(0.0, 0.04, 1.0, 0.13, "Map page (Leaflet): route panel with step directions,\nquestion box with cited answers and \"I don't know\"", fc="#E8F1F8")
    arrow((0.23, 0.28), (0.23, 0.17))
    arrow((0.77, 0.28), (0.77, 0.17))
    fig.subplots_adjust(0, 0, 1, 1)
    fig.savefig(FIG / "fig1_pipeline.png")
    plt.close(fig)


def fig_route_map(g, nodes, lat0, rows, label="Ogden Hall -> Bishop Hall"):
    r = next(x for x in rows if x["label"] == label)
    xy = {n.node_id: (n.lon * math.cos(lat0) * 111320, n.lat * 111320) for n in nodes.itertuples()}
    short, easy = r["paths"]["shortest"], r["paths"]["wheelchair"]
    fig, ax = plt.subplots(figsize=(W, 3.1))
    allp = [xy[n] for n in short + easy]
    pad = 40
    x0, x1 = min(p[0] for p in allp) - pad, max(p[0] for p in allp) + pad
    y0, y1 = min(p[1] for p in allp) - pad, max(p[1] for p in allp) + pad
    for u, v in g.edges:
        if u in xy and v in xy:
            (ax_, ay_), (bx_, by_) = xy[u], xy[v]
            if max(ax_, bx_) >= x0 and min(ax_, bx_) <= x1 and max(ay_, by_) >= y0 and min(ay_, by_) <= y1:
                ax.plot([ax_, bx_], [ay_, by_], color=GREY, lw=0.5, zorder=1)

    def draw(path, colour, lw, z):
        pts = [xy[n] for n in path]
        ax.plot(*zip(*pts, strict=True), color=colour, lw=lw, zorder=z, solid_capstyle="round")
        for a, b in zip(path, path[1:], strict=False):  # white dashes where the road has no sidewalk mapped
            if no_sidewalk(g[a][b]):
                ax.plot([xy[a][0], xy[b][0]], [xy[a][1], xy[b][1]], color="white", lw=lw * 0.45, ls=(0, (1.2, 1.2)), zorder=z + 0.1)

    draw(short, ORANGE, 3.0, 3)
    draw(easy, BLUE, 2.0, 4)
    sx, sy, hx, hy = [], [], [], []
    for a, b in zip(short, short[1:], strict=False):
        e = g[a][b]
        mid = ((xy[a][0] + xy[b][0]) / 2, (xy[a][1] + xy[b][1]) / 2)
        if e["steps"]:
            sx.append(mid[0])
            sy.append(mid[1])
        if e["grade"] is not None and e["grade"] > 8.33:
            hx.append(mid[0])
            hy.append(mid[1])
    ax.scatter(sx, sy, marker="X", s=48, color=BLACK, edgecolor="white", lw=0.8, zorder=6)
    ax.scatter(hx, hy, marker="^", s=40, color=PURPLE, edgecolor="white", lw=0.8, zorder=6)
    s_, e_ = r["summary"]["shortest"], r["summary"]["wheelchair"]
    for n, t, off in ((short[0], "Ogden Hall", (-4, 7)), (short[-1], "Bishop Hall", (6, -3))):
        ax.scatter(*xy[n], s=26, color="white", edgecolor=BLACK, lw=1.0, zorder=7)
        ax.annotate(t, xy[n], xytext=off, textcoords="offset points", fontsize=6.5, zorder=8, bbox={"fc": "white", "ec": "none", "pad": 0.8, "alpha": 0.85})
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    # scale bar
    bx, by = x0 + 12, y0 + 12
    ax.plot([bx, bx + 50], [by, by], color=BLACK, lw=1.4, zorder=9)
    ax.text(bx + 25, by + 5, "50 m", ha="center", fontsize=6, zorder=9)
    h = [
        Line2D([], [], color=ORANGE, lw=3, label=f"Plain shortest path, {s_['length_m']:.0f} m"),
        Line2D([], [], color=BLUE, lw=2, label=f"Step-free route, {e_['length_m']:.0f} m"),
        Line2D([], [], color="none", marker="X", mfc=BLACK, mec="white", ms=6, label=f"Stair section on shortest path ({s_['steps']})"),
        Line2D([], [], color="none", marker="^", mfc=PURPLE, mec="white", ms=5.5, label=f"Slope over 8.33% on shortest path ({s_['steep_sections']})"),
        Line2D([], [], color="#777777", lw=2, ls=(0, (1.2, 1.2)), label="White dashes: road, no sidewalk mapped"),
    ]
    ax.legend(handles=h, loc="upper center", bbox_to_anchor=(0.5, -0.01), frameon=False, ncol=1, handlelength=2.2, borderaxespad=0)
    fig.subplots_adjust(0.01, 0.30, 0.99, 0.99)
    fig.savefig(FIG / "fig2_route_map.png")
    plt.close(fig)


def fig_hazards(rows):
    inform = [r for r in rows if not r["same_point"]]
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(W, 4.4), gridspec_kw={"height_ratios": [1, 1.25], "hspace": 0.62})
    xs = [r["summary"]["wheelchair"]["length_m"] - r["summary"]["shortest"]["length_m"] for r in inform]
    sv = [r["summary"]["shortest"]["steps"] for r in inform]
    ev = [r["summary"]["wheelchair"]["steps"] for r in inform]
    sp = [r["summary"]["shortest"]["steep_sections"] for r in inform]
    ep = [r["summary"]["wheelchair"]["steep_sections"] for r in inform]
    ys = [(a + b) - (c + d) for a, b, c, d in zip(sv, sp, ev, ep, strict=True)]
    a1.grid(color="#E5E5E5", lw=0.5, zorder=0)
    a1.set_axisbelow(True)
    a1.scatter(xs, ys, s=22, color=BLUE, edgecolor="white", lw=0.6, zorder=3)
    a1.axhline(0, color="#777777", lw=0.6)
    for x, y, r in zip(xs, ys, inform, strict=True):
        if y >= 2 or x >= 100 or y < 0:
            nm = r["label"].split(" -> ")[0]
            off, ha = {"Yager Stadium": ((-3, -9), "right"), "Ogden Hall": ((4, -9), "left")}.get(nm, ((4, 3), "left"))
            a1.annotate(nm, (x, y), xytext=off, ha=ha, textcoords="offset points", fontsize=5.8)
    a1.set_xlim(-8, 175)
    a1.set_xlabel("Extra distance over the shortest path (m)")
    a1.set_ylabel("Stairs + steep sections\navoided (count)")
    a1.set_yticks(range(min(ys) - (min(ys) < 0), max(ys) + 2))
    a1.set_title("(a) Hazards avoided against distance paid", loc="left")
    clean(a1)
    order = sorted(inform, key=lambda r: r["summary"]["shortest"]["road_no_sidewalk_m"])
    ys2 = np.arange(len(order))
    for i, r in enumerate(order):
        s, e = r["summary"]["shortest"]["road_no_sidewalk_m"], r["summary"]["wheelchair"]["road_no_sidewalk_m"]
        a2.plot([s, e], [i, i], color="#999999", lw=0.9, zorder=1)
    a2.scatter([r["summary"]["shortest"]["road_no_sidewalk_m"] for r in order], ys2, s=16, color=ORANGE, zorder=3, label="Plain shortest path")
    a2.scatter([r["summary"]["wheelchair"]["road_no_sidewalk_m"] for r in order], ys2, s=16, color=BLUE, marker="s", zorder=4, label="Step-free route")
    a2.set_yticks(ys2)
    firsts = [r["label"].split(" -> ")[0] for r in order]
    names = [f + (" > " + r["label"].split(" -> ")[1].split()[0] if firsts.count(f) > 1 else "") for f, r in zip(firsts, order, strict=True)]
    a2.set_yticklabels(names, fontsize=5.3)
    a2.set_xlabel("Road with no sidewalk mapped, per route (m)")
    a2.set_title("(b) Walking on the road", loc="left")
    a2.legend(loc="lower right", frameon=False)
    a2.grid(axis="x", color="#E5E5E5", lw=0.5)
    a2.set_axisbelow(True)
    clean(a2)
    fig.subplots_adjust(0.35, 0.09, 0.98, 0.95)
    fig.savefig(FIG / "fig3_hazards_vs_distance.png")
    plt.close(fig)


def fig_cost_and_search(bench):
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(W, 4.6), gridspec_kw={"hspace": 0.62})
    gr = np.linspace(0, 14, 561)
    base = {"steps": False, "highway": "footway", "footway": "sidewalk", "surface": None, "raised_kerb": False}
    mult = [routing.penalty({**base, "grade": float(x)}) for x in gr]
    a1.step(gr, mult, where="post", color=BLUE, lw=1.6)
    a1.axvline(5, color="#777777", lw=0.6, ls="--")
    a1.axvline(8.33, color="#777777", lw=0.6, ls="--")
    a1.text(4.9, 3.4, "5%: ADA limit for\nwalking surfaces", fontsize=5.8, va="top", ha="right")
    a1.text(8.5, 4.0, "8.33% (1:12):\nADA ramp limit", fontsize=5.8, va="top")
    a1.set_xlabel("Slope of the path section (%)")
    a1.set_ylabel("Cost multiplier on length\n(1 = free)")
    a1.set_ylim(0, 6.8)
    a1.set_title("(a) Slope penalty (stairs are never used)", loc="left")
    clean(a1)
    rows = [r for r in bench["rows"] if r["found"]]
    for prof, mk, col in (("wheelchair", "o", BLUE), ("blind", "s", ORANGE)):
        d = [r for r in rows if r["profile"] == prof]
        a2.scatter([r["dijkstra_pops"] for r in d], [r["astar_pops"] for r in d], s=16, marker=mk, color=col, edgecolor="white", lw=0.5, label=prof.capitalize() if prof == "wheelchair" else "Blind / low vision", zorder=3)
    lim = [200, 2.5e4]
    a2.plot(lim, lim, color="#777777", lw=0.6, ls="--")
    a2.text(230, 75, "dashed line: same work\nas Dijkstra", fontsize=5.8, color="#555555")
    a2.set_xscale("log")
    a2.set_yscale("log")
    a2.set_xlim(*lim)
    a2.set_ylim(60, 2.5e4)
    a2.set_xlabel("Nodes taken from the queue, Dijkstra (h = 0)")
    a2.set_ylabel("Nodes taken from\nthe queue, A*")
    a2.set_title("(b) Search work on 15 Oxford routes", loc="left")
    a2.legend(loc="upper left", frameon=False)
    clean(a2)
    fig.subplots_adjust(0.20, 0.09, 0.97, 0.95)
    fig.savefig(FIG / "fig4_cost_and_search.png")
    plt.close(fig)


# ---------------------------------------------------------------- main
def main():
    if not args.skip_bench:
        with open(RES / "search_bench.json", "w") as f:
            subprocess.run(["node", str(HERE / "search_bench.js"), str(REPO)], check=True, stdout=f)
    bench = json.loads((RES / "search_bench.json").read_text())

    g, nodes, lat0, rows, refusals = routing_comparison()
    agg = aggregate(rows, refusals)
    fb = [r for r in bench["rows"] if r["found"]]
    agg["search"] = {
        "node_version": bench["node_version"],
        "graph_nodes": bench["nodes"],
        "graph_edges": bench["edges"],
        "heuristic_ratio": bench["heuristic_ratio"],
        "load_graph_ms": round(bench["load_graph_ms"], 1),
        "json_parse_ms": round(bench["json_read_parse_ms"], 1),
        "all_costs_equal_to_dijkstra": all(r["same_cost"] for r in fb),
        "all_paths_equal_to_dijkstra": all(r["same_path"] for r in fb),
        "n_searches": len(fb),
    }
    for prof in ("wheelchair", "blind"):
        d = [r for r in fb if r["profile"] == prof]
        agg["search"][prof] = {
            "n": len(d),
            "astar_pops_median": st.median(r["astar_pops"] for r in d),
            "dijkstra_pops_median": st.median(r["dijkstra_pops"] for r in d),
            "pops_ratio_median": round(st.median(r["dijkstra_pops"] / r["astar_pops"] for r in d), 1),
            "astar_ms_median": round(st.median(r["astar_ms"] for r in d), 3),
            "dijkstra_ms_median": round(st.median(r["dijkstra_ms"] for r in d), 3),
            "astar_ms_max": round(max(r["astar_ms"] for r in d), 3),
        }
    agg["admissibility"] = admissibility(g, nodes, lat0)
    agg["per_route"] = [
        {
            "label": r["label"],
            "category": r["category"],
            "extra_m": round(r["summary"]["wheelchair"]["length_m"] - r["summary"]["shortest"]["length_m"], 1),
            **{
                f"{p}_{k}": r["summary"][p][k]
                for p in ("shortest", "wheelchair", "blind")
                for k in ("length_m", "steps", "steep_sections", "road_no_sidewalk_m")
            },
        }
        for r in rows
        if not r["same_point"]
    ]
    (RES / "routing.json").write_text(json.dumps(agg, indent=1))
    (RES / "assistant_tables.json").write_text(json.dumps(assistant_tables(), indent=1))
    (RES / "sources.json").write_text(json.dumps(source_table(), indent=1))
    (RES / "agreement_dc.json").write_text((REPO / "data/cards/agreement_dc.json").read_text())

    fig_pipeline()
    fig_route_map(g, nodes, lat0, rows)
    fig_hazards(rows)
    fig_cost_and_search(bench)
    print("done:", *sorted(p.name for p in FIG.glob("*.png")))


if __name__ == "__main__":
    main()
