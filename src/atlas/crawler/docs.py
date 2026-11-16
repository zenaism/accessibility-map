"""Turn the pages the crawler saved into the documents table (data/processed/<region>/<source>.docs.parquet),
the same columns the earlier web connector wrote, plus the crawl fields."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..connectors.web import _clean_html
from ..core import out_dir
from . import archive, office, read
from .frontier import Frontier

# which saved file to read when several share one hash prefix (the page, its rendered copy, its screenshot)
PREFERENCE = (".rendered.html", ".html", ".pdf", ".docx", ".xlsx", ".pptx", ".csv", ".ics", ".json")
OFFICE = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
}


def pick_file(source: str, sha: str) -> Path | None:
    files = [
        p
        for p in (archive.RAW / "web" / source).glob(f"{sha[:12]}.*")
        if not p.name.endswith(".screenshot.png")
    ]
    for suffix in PREFERENCE:
        for p in files:
            if p.name.endswith(suffix):
                return p
    return files[0] if files else None


def read_file(path: Path, ctype: str, url: str, ocr_left: list[int]) -> read.Read:
    """Read one saved file into text and structure. `ocr_left` is a one-item budget of images still allowed to be OCR'd."""
    data = path.read_bytes()
    if path.name.endswith((".html", ".htm")):
        return read.read_html(data, url, _clean_html)
    if path.suffix == ".pdf":
        return read.read_pdf_isolated(data)
    kind = OFFICE.get(ctype) or path.suffix.lstrip(".")
    if kind in ("docx", "xlsx", "pptx"):
        return read.Read(kind=kind, title=Path(url).name, text=office.extract(data, kind), method="zip-xml")
    if kind in ("csv", "ics", "json", "txt"):
        return read.Read(
            kind=kind, title=Path(url).name, text=data.decode("utf-8", "replace")[:500_000], method="text"
        )
    if path.suffix in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        if ocr_left[0] <= 0:
            return read.Read(kind="image", method="skipped: ocr budget")
        r = read.read_image(data)
        ocr_left[0] -= r.ocr_pages
        return r
    return read.Read(kind=kind or "file", title=Path(url).name)


def build(source: str, region: str, spec: dict, frontier: Frontier) -> pd.DataFrame:
    docs = []
    ocr_left = [spec.get("budget", {}).get("ocr_images", 60)]
    for r in frontier.rows("fetched"):
        if not r["content_sha"]:
            continue
        path = pick_file(source, r["content_sha"])
        if path is None:
            continue
        rd = read_file(path, r["content_type"] or "", r["final_url"] or r["url"], ocr_left)
        shot = path.with_name(f"{r['content_sha'][:12]}.screenshot.png")
        docs.append(
            {
                "doc_id": f"{source}:{r['content_sha'][:12]}",
                "source": source,
                "url": r["url"],
                "canonical_url": r["final_url"] or r["url"],
                "screenshot": str(shot) if shot.exists() else None,
                **rd.row(),
                "content_type": rd.kind,
                "raw_file": str(path),
                "retrieved_at": r["last_fetched"],
                "author_type": spec.get("author_type", "official"),
                "region": region,
                "chars": len(rd.text),
                "depth": r["depth"],
                "discovered_via": r["via"],
                "relevance": r["score"],
                "content_sha": r["content_sha"],
                "crawl_id": r["crawl_id"],
                "rendered": bool(r["rendered"]),
            }
        )
    df = pd.DataFrame(docs)
    if len(df):
        df.to_parquet(out_dir(region) / f"{source}.docs.parquet", index=False)
    return df
