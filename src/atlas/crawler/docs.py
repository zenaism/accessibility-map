"""Turn the pages the crawler saved into the documents table (data/processed/<region>/<source>.docs.parquet),
the same columns the earlier web connector wrote, plus the crawl fields."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..connectors.web import _clean_html, _pdf_text
from ..core import out_dir
from . import archive
from .frontier import Frontier


def build(source: str, region: str, spec: dict, frontier: Frontier) -> pd.DataFrame:
    docs = []
    for r in frontier.rows("fetched"):
        if not r["content_sha"]:
            continue
        ctype = r["content_type"] or ""
        ext = {"application/pdf": "pdf"}.get(
            ctype, "html" if ctype.startswith("text/html") else ctype.split("/")[-1]
        )
        try:
            data = archive.read(
                next(Path(archive.RAW / "web" / source).glob(f"{r['content_sha'][:12]}.*")).as_posix()
            )
        except StopIteration:
            continue
        title, text = "", ""
        if ext == "html":
            title, text, _ = _clean_html(data, r["final_url"] or r["url"])
        elif ext == "pdf":
            title, text = Path(r["url"]).name, _pdf_text(data)
        docs.append(
            {
                "doc_id": f"{source}:{r['content_sha'][:12]}",
                "source": source,
                "url": r["url"],
                "canonical_url": r["final_url"] or r["url"],
                "screenshot": None,
                "title": title,
                "text": text,
                "content_type": ext,
                "raw_file": str(next(Path(archive.RAW / "web" / source).glob(f"{r['content_sha'][:12]}.*"))),
                "retrieved_at": r["last_fetched"],
                "author_type": spec.get("author_type", "official"),
                "region": region,
                "chars": len(text),
                "depth": r["depth"],
                "discovered_via": r["via"],
                "relevance": r["score"],
                "content_sha": r["content_sha"],
                "crawl_id": r["crawl_id"],
            }
        )
    df = pd.DataFrame(docs)
    if len(df):
        df.to_parquet(out_dir(region) / f"{source}.docs.parquet", index=False)
    return df
