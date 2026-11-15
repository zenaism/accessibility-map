"""Generate docs/categories.md from config/categories.yaml and check it against config/attributes.yaml.

    python scripts/make_categories_doc.py

Fails (exit 1) if a category uses an attribute that is neither in attributes.yaml nor listed under its
own new_attributes, so the two files cannot drift apart.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CATS = yaml.safe_load((ROOT / "config/categories.yaml").read_text())
ATTRS = yaml.safe_load((ROOT / "config/attributes.yaml").read_text())

KINDS = "place | route | event | service | infrastructure | condition | information"


def check() -> list[str]:
    problems = []
    for cid, c in CATS.items():
        new = set((c.get("new_attributes") or {}))
        for a in c.get("attributes", []):
            if a not in ATTRS and a not in new:
                problems.append(f"{cid}: attribute '{a}' is not in attributes.yaml or new_attributes")
        for a in new:
            if a in ATTRS:
                problems.append(f"{cid}: new attribute '{a}' already exists in attributes.yaml")
    return problems


def main() -> int:
    problems = check()
    if problems:
        print("\n".join(problems))
        return 1
    order = {"P0": 0, "P1": 1, "P2": 2}
    rows = sorted(CATS.items(), key=lambda kv: (order.get(kv[1]["priority"], 9), kv[0]))
    out = [
        "# Question categories",
        "",
        "_Generated from `config/categories.yaml` by `scripts/make_categories_doc.py`. Do not edit by hand: change the YAML and rerun._",
        "",
        "Everything a wheelchair user might ask about, grouped so that data fetching, source discovery and evaluation all use "
        "the same list. For each category the YAML holds the OpenStreetMap selectors, Overture category hints, the attributes to "
        "extract, the words that mark a relevant web page, the usual source kinds (letters A to K in `source_types.md`), how often to "
        "refresh, and whether values expire. Attribute meanings are in `config/attributes.yaml` (existing) and under "
        "*new attributes* below (to add).",
        "",
        "Status: **have** = collected for Cincinnati and Oxford, **partial** = some, **none** = not yet. "
        "Priority: P0 first regions, P1 next, P2 later.",
        "",
        "## Overview",
        "",
        "| Priority | Category | Kind | Refresh | Expires | Status |",
        "|---|---|---|---|---|---|",
    ]
    for cid, c in rows:
        refresh = f"{c['refresh_days']} days" if c.get("refresh_days") else "rarely"
        out.append(
            f"| {c['priority']} | [{c['label']}](#{cid}) | {c['kind']} | {refresh} | "
            f"{'yes' if c.get('temporal') else 'no'} | {c['status']} |"
        )
    out += ["", f"Kinds: {KINDS}.", ""]
    for cid, c in rows:
        out += [
            f"## {cid}",
            "",
            f"**{c['label']}** (priority {c['priority']}, status {c['status']})",
            "",
            "Typical questions:",
        ]
        out += [f"- {q}" for q in c["asks"]]
        out += ["", f"- **Attributes to extract:** {', '.join(c['attributes']) or 'none yet'}"]
        new = c.get("new_attributes") or {}
        if new:
            out.append("- **New attributes needed:**")
            out += [f"  - `{k}`: {v}" for k, v in new.items()]
        osm = c.get("osm") or []
        out.append(
            "- **OSM selectors:** " + ("; ".join(f"`{s}`" for s in osm) if osm else "none (not map-based)")
        )
        out.append("- **Overture hints (unchecked):** " + (", ".join(c.get("overture") or []) or "none"))
        out.append("- **Page words:** " + ", ".join(c["page_words"]))
        out.append("- **Source kinds:** " + ", ".join(c["sources"]))
        out.append("")
    (ROOT / "docs/categories.md").write_text("\n".join(out))
    print(f"wrote docs/categories.md ({len(CATS)} categories)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
