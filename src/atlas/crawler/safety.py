"""Treat every download as hostile: check what a file really is, and read risky formats in a separate process."""

from __future__ import annotations

import json
import subprocess
import sys

MAGIC = [
    (b"%PDF", "pdf"), (b"\x89PNG", "png"), (b"\xff\xd8\xff", "jpeg"), (b"GIF8", "gif"), (b"PK\x03\x04", "zip"),
    (b"RIFF", "riff"), (b"\x1f\x8b", "gzip"), (b"BEGIN:VCALENDAR", "ics"),
]  # fmt: skip
CLAIMS = {
    "application/pdf": {"pdf"},
    "image/png": {"png"},
    "image/jpeg": {"jpeg"},
    "image/gif": {"gif"},
    "image/webp": {"riff"},
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {"zip"},
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {"zip"},
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": {"zip"},
    "text/calendar": {"ics"},
}


def sniff(data: bytes) -> str:
    """What the bytes say the file is (pdf, png, zip, html, text, ...), whatever the server claimed."""
    head = data[:2048].lstrip()
    for magic, kind in MAGIC:
        if head.startswith(magic):
            return kind
    low = head[:512].lower()
    if low.startswith((b"<!doctype html", b"<html")) or b"<html" in low or b"<head" in low:
        return "html"
    if low.startswith((b"<?xml", b"<urlset", b"<rss", b"<feed")):
        return "xml"
    try:
        head.decode("utf-8")
        return "text"
    except UnicodeDecodeError:
        return "unknown"


def mismatch(content_type: str, data: bytes) -> str | None:
    """A note when the server's claim does not fit the bytes (a PDF that is really HTML, an image that is a script)."""
    expected = CLAIMS.get((content_type or "").split(";")[0].strip().lower())
    kind = sniff(data)
    if expected and kind not in expected:
        return f"claimed {content_type}, bytes look like {kind}"
    return None


_PDF_CODE = (
    "import sys, json, io\n"
    "from pypdf import PdfReader\n"
    "data = sys.stdin.buffer.read()\n"
    "r = PdfReader(io.BytesIO(data))\n"
    "print(json.dumps('\\n\\n'.join((p.extract_text() or '') for p in r.pages)))\n"
)


def safe_pdf_text(data: bytes, timeout: float = 45.0) -> str:
    """PDF text read in a separate process with a time limit, so a booby-trapped file cannot hang or crash the crawler."""
    try:
        r = subprocess.run(
            [sys.executable, "-I", "-c", _PDF_CODE], input=data, capture_output=True, timeout=timeout
        )
        if r.returncode == 0:
            return json.loads(r.stdout.decode("utf-8", "replace"))
        return "[pdf text extraction failed]"
    except (subprocess.TimeoutExpired, ValueError):
        return "[pdf text extraction timed out]"
