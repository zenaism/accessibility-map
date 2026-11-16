"""Save exactly what we received. Same layout and manifest as the earlier web connector
(data/raw/web/<source>/<sha12><ext> + manifest.jsonl), so archived_doc() and the document builder keep working."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from ..core import RAW, now
from . import safety

BY_PATH = (".pdf", ".docx", ".xlsx", ".pptx", ".doc", ".xls", ".ppt", ".csv", ".ics", ".json", ".geojson", ".kml",
           ".jpg", ".jpeg", ".png", ".webp", ".gif")  # fmt: skip
BY_TYPE = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "text/calendar": ".ics",
    "text/csv": ".csv",
    "application/json": ".json",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def file_ext(url: str, ctype: str) -> str:
    """File extension to save under: from the address if it names a known type, else from the content type, else .html."""
    path = urlsplit(url).path.lower()
    for e in BY_PATH:
        if path.endswith(e):
            return e
    return BY_TYPE.get((ctype or "").split(";")[0].strip().lower(), ".html")


KEEP_HEADERS = (
    "content-type",
    "content-length",
    "last-modified",
    "etag",
    "content-language",
    "server",
    "cache-control",
)


def save(
    source: str, url: str, final_url: str, status: int, ctype: str, headers: dict, body: bytes,
    rendered: bool = False, screenshot: bytes | None = None,
) -> dict:  # fmt: skip
    d = RAW / "web" / source
    d.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(body).hexdigest()
    f = d / (f"{sha[:12]}.rendered.html" if rendered else f"{sha[:12]}{file_ext(final_url, ctype)}")
    if not f.exists():  # identical bytes are stored once
        f.write_bytes(body)
    shot = d / f"{sha[:12]}.screenshot.png"
    if screenshot and not shot.exists():
        shot.write_bytes(screenshot)
    rec = {
        "url": url,
        "retrieved_at": now(),
        "rendered": rendered,
        "screenshot": str(shot.relative_to(RAW.parent.parent))
        if screenshot and RAW.parent.parent in shot.parents
        else (str(shot) if screenshot else None),
        "type_note": safety.mismatch(ctype, body),
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
