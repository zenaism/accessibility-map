"""Render docs/figures/regions_flow.gif: sources -> map (four regions) -> chat answer.

Uses real data only:
  - OSM paths and wheelchair-tagged places from data/processed/<region>/osm.entities.parquet
  - record counts from data/cards/index.csv
  - the chat frame is a screenshot of the assistant (docs/work_logs/screens/assistant/)

Needs `make data` first (data/processed is not in git).  Run:
  .venv/bin/python scripts/make_regions_gif.py
Output stays under about 5 MB.
"""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from PIL import Image  # noqa: E402

from atlas.core import PROCESSED, ROOT  # noqa: E402

OUT = ROOT / "docs" / "figures" / "regions_flow.gif"
SHOT = ROOT / "docs/work_logs/screens/assistant/desktop-2-answer-with-cards.png"
REGIONS = [("cincinnati", "Cincinnati"), ("oxford", "Oxford"), ("dc", "Washington DC"), ("dayton", "Dayton")]
PATHS = ("highway=footway", "highway=path", "highway=steps", "highway=pedestrian", "highway=cycleway")
INK, MUTED, PATH, GOOD, WARN, BAD = "#0b0b0b", "#52514e", "#9aa3ad", "#1b7f3b", "#c27a00", "#b42318"
W, H = 1000, 520


def counts() -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for r in csv.DictReader(open(ROOT / "data/cards/index.csv")):
        if r["collected"] == "True":
            out[r["id"].split(".")[0]] += int(float(r["records"] or 0))
    return out


def load(region: str):
    g = gpd.read_parquet(PROCESSED / region / "osm.entities.parquet")
    g = g.to_crs(4326) if g.crs else g.set_crs(4326)
    tags = g["tags"].map(lambda t: t if isinstance(t, dict) else (json.loads(t) if t else {}))
    lines = g[(g.geometry.geom_type == "LineString") & g.category.isin(PATHS)]
    wc = tags.map(lambda t: t.get("wheelchair"))
    pts = g[(g.geometry.geom_type == "Point") & wc.isin(["yes", "limited", "no"])]
    return lines, pts.assign(wc=wc[pts.index])


def frame(data, n, stage: int, progress: float) -> Image.Image:
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100, facecolor="white")
    fig.text(0.5, 0.955, ["1  Sources: open maps and city data", "2  Map: paths, stairs and places with a wheelchair tag (OpenStreetMap)",
                          "3  Chat: an answer with its source (Cincinnati and Oxford)"][stage],
             ha="center", va="center", fontsize=15, fontweight="bold", color=INK)
    if stage == 2:
        im = Image.open(SHOT).crop((200, 130, 1080, 555))
        ax = fig.add_axes([0.1, 0.03, 0.8, 0.85])
        ax.imshow(im)
        ax.axis("off")
    else:
        for i, (key, label) in enumerate(REGIONS):
            lines, pts = data[key]
            ax = fig.add_axes([0.02 + i * 0.245, 0.14, 0.235, 0.72])
            k = max(1, int(len(lines) * progress)) if stage == 0 else len(lines)
            ls = lines.iloc[:k]
            ls.plot(ax=ax, color=PATH, linewidth=0.35)
            if stage == 1:
                for v, c in (("yes", GOOD), ("limited", WARN), ("no", BAD)):
                    p = pts[pts.wc == v]
                    p = p.iloc[: max(1, int(len(p) * progress))]
                    if len(p):
                        p.plot(ax=ax, color=c, markersize=11, linewidth=0)
            ax.set_aspect(1 / max(0.2, abs(__import__("math").cos(__import__("math").radians(lines.total_bounds[[1, 3]].mean())))))
            ax.axis("off")
            fig.text(0.02 + i * 0.245 + 0.1175, 0.095, label, ha="center", fontsize=12, fontweight="bold", color=INK)
            sub = f"{n.get(key, 0):,} records collected" if stage == 0 else f"{len(pts):,} tagged places"
            fig.text(0.02 + i * 0.245 + 0.1175, 0.055, sub, ha="center", fontsize=9.5, color=MUTED)
        if stage == 1:
            fig.text(0.5, 0.015, "green = yes   amber = limited   red = no   (grey = paths and stairs; most places have no tag: unknown)",
                     ha="center", fontsize=9, color=MUTED)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100)
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def main() -> None:
    n = counts()
    data = {k: load(k) for k, _ in REGIONS}
    frames: list[Image.Image] = []
    durations: list[int] = []
    for p in (0.25, 0.6, 1.0):
        frames.append(frame(data, n, 0, p)); durations.append(500 if p < 1 else 1500)
    for p in (0.3, 0.7, 1.0):
        frames.append(frame(data, n, 1, p)); durations.append(500 if p < 1 else 2200)
    frames.append(frame(data, n, 2, 1)); durations.append(3500)
    frames = [f.convert("P", palette=Image.ADAPTIVE, colors=64) for f in frames]
    frames[0].save(OUT, save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=True)
    print(OUT, OUT.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
