"""Save exactly what we received. Same layout and manifest as the earlier web connector
(data/raw/web/<source>/<sha12><ext> + manifest.jsonl), so archived_doc() and the document builder keep working."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..connectors.web import _ext
from ..core import RAW, now

KEEP_HEADERS = (
    "content-type",
    "content-length",
    "last-modified",
    "etag",
    "content-language",
    "server",
    "cache-control",
)


def save(source: str, url: str, final_url: str, status: int, ctype: str, headers: dict, body: bytes) -> dict:
    d = RAW / "web" / source
    d.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(body).hexdigest()
    f = d / f"{sha[:12]}{_ext(final_url, ctype)}"
    if not f.exists():  # identical bytes are stored once
        f.write_bytes(body)
    rec = {
        "url": url,
        "retrieved_at": now(),
        "rendered": False,
        "status": status,
        "final_url": final_url,
        "content_type": ctype,
        "sha256": sha,
        "bytes": len(body),
        "file": str(f.relative_to(RAW.parent.parent)) if RAW.parent.parent in f.parents else str(f),
        "headers": {k: v for k, v in headers.items() if k in KEEP_HEADERS},
        "crawler": "atlas-crawler/1",
    }
    with (d / "manifest.jsonl").open("a") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec


def read(rec_file: str) -> bytes:
    p = Path(rec_file)
    return p.read_bytes() if p.is_absolute() else (RAW.parent.parent / rec_file).read_bytes()
