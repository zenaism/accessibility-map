"""Export the problem reports for the accessibility team: a spreadsheet, the photos, and a simple gallery page.

    SUPABASE_SERVICE_KEY=... python scripts/export_reports.py [--out data/private/reports] [--status new]

The service key (Supabase dashboard -> Project settings -> API -> secret key) can read the locked table. It is read from
the environment only, never stored in a file, and never goes into the repository. The output holds personal data (the
optional contact field and photos), so it is written under data/private/, which git ignores.
"""

from __future__ import annotations

import csv
import html
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import requests
import yaml

from .core import ROOT

PAGE = 20  # rows per request: photos make rows large
COLUMNS = ["ref", "created_at", "status", "category", "place_name", "link_id", "region", "description", "contact",
           "photo", "page_url", "team_notes"]  # fmt: skip
CATEGORY = {
    "blocked_or_broken": "Blocked or broken",
    "wrong_info": "Information is wrong",
    "less_accessible": "Harder to use than shown",
    "missing_info": "Something is missing",
    "other": "Something else",
}


def config() -> tuple[str, str]:
    c = yaml.safe_load((ROOT / "config" / "ratings.yaml").read_text())
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not key:
        raise SystemExit(
            "Set SUPABASE_SERVICE_KEY in your terminal first (the secret key; never put it in a file)."
        )
    return str(c["url"]).rstrip("/"), key


def fetch_all(url: str, key: str, status: str | None = None) -> list[dict]:
    rows, start = [], 0
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    while True:
        q = f"{url}/rest/v1/problem_reports?select=*&order=created_at.desc" + (
            f"&status=eq.{status}" if status else ""
        )
        r = requests.get(
            q, headers={**headers, "Range-Unit": "items", "Range": f"{start}-{start + PAGE - 1}"}, timeout=120
        )
        r.raise_for_status()
        batch = r.json()
        rows += batch
        if len(batch) < PAGE:
            return rows
        start += PAGE


def photo_from(value) -> bytes | None:
    """PostgREST sends bytea as the text '\\x' followed by hex."""
    if not value:
        return None
    return bytes.fromhex(value[2:]) if isinstance(value, str) and value.startswith("\\x") else None


def export(rows: list[dict], out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    (out / "photos").mkdir(exist_ok=True)
    flat = []
    for r in rows:
        ref = r["id"][:8].upper()
        data = photo_from(r.get("photo"))
        if data:
            (out / "photos" / f"{ref}.jpg").write_bytes(data)
        flat.append(
            {**{k: r.get(k) for k in COLUMNS}, "ref": ref, "photo": f"photos/{ref}.jpg" if data else ""}
        )
    with (out / "reports.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(flat)
    cards = []
    for r in flat:
        img = (
            f'<a href="{html.escape(r["photo"])}"><img src="{html.escape(r["photo"])}" alt="Photo for report {r["ref"]}"></a>'
            if r["photo"]
            else ""
        )
        cards.append(
            f"<article><h2>{html.escape(CATEGORY.get(r['category'], r['category'] or ''))} "
            f"<small>#{r['ref']} · {html.escape(str(r['created_at'])[:16])} · {html.escape(r['status'] or '')}</small></h2>"
            f"<p><b>{html.escape(r['place_name'] or 'About the map itself')}</b></p><p>{html.escape(r['description'] or '')}</p>"
            f'{img}<p class="m">Contact: {html.escape(r["contact"] or "none given")}</p></article>'
        )
    page = (
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>Problem reports</title>'
        "<style>body{font:16px/1.5 system-ui,sans-serif;max-width:760px;margin:24px auto;padding:0 16px}"
        "article{border:1px solid #d1d5db;border-radius:12px;padding:14px 16px;margin:0 0 14px}h2{font-size:18px;margin:0}"
        "small{font-weight:400;color:#4b5563}img{max-width:100%;max-height:360px;border-radius:8px}.m{color:#4b5563;font-size:14px}</style>"
        f"<h1>Problem reports ({len(flat)})</h1><p>Exported {datetime.now(UTC):%Y-%m-%d %H:%M} UTC. Contains personal data: do not share.</p>"
        + "".join(cards)
    )
    (out / "index.html").write_text(page)
    return out / "index.html"


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(ROOT / "data" / "private" / "reports"))
    ap.add_argument("--status", help="only reports with this status, e.g. new")
    a = ap.parse_args(argv)
    url, key = config()
    rows = fetch_all(url, key, a.status)
    page = export(rows, Path(a.out))
    print(f"{len(rows)} reports exported. Open {page}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
