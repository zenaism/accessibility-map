"""Reading what the crawler saved (docs/crawler_plan.md 6.5): from raw files to text with structure.

HTML  -> main text (trafilatura, with a fallback), sections with their heading path, tables as rows, dates,
         structured data (JSON-LD, Microdata, Open Graph), phones and opening hours, accessibility sentences.
PDF   -> text by page (PyMuPDF), tables, and OCR for pages that are really pictures (scans, flyers).
Image -> OCR text for posters, signs and maps (small icons and logos are skipped).
Everything here is free and runs on a laptop. A vision model for maps and posters is a later, optional step.
"""

from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass, field
from functools import cache

from lxml import html as lxml_html

from . import privacy, relevance

MIN_IMAGE_SIDE = 300  # an image with no side this long is an icon or logo
MIN_IMAGE_AREA = 40_000  # ...and so is one with fewer pixels than this (a wide banner can still be a sign)
MAX_IMAGE_SIDE = 3000
OCR_DPI = 170
SCAN_CHARS = 25  # a PDF page with fewer characters than this is treated as a picture
MAX_PDF_PAGES = 120
MAX_OCR_PAGES = 30
PHONE = re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?\(?([2-9]\d{2})\)?[\s.-]?(\d{3})[\s.-]?(\d{4})(?!\d)")
DAYS = r"(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*\.?"
CLOCK = r"\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)"
HOURS = re.compile(
    rf"\b{DAYS}(?:\s*(?:-|–|to|through|&|and)\s*{DAYS})?[^\n]{{0,40}}?{CLOCK}(?:\s*(?:-|–|to|until)\s*{CLOCK})?",
    re.I,
)
HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


@dataclass
class Read:
    kind: str = "file"
    title: str = ""
    text: str = ""
    method: str = ""
    sections: list[dict] = field(default_factory=list)
    tables: list[dict] = field(default_factory=list)
    structured: dict = field(default_factory=dict)
    published_at: str | None = None
    updated_at: str | None = None
    language: str | None = None
    phones: list[str] = field(default_factory=list)
    hours: list[str] = field(default_factory=list)
    access_snippets: list[dict] = field(default_factory=list)
    pages: int = 0
    ocr_pages: int = 0
    ocr_confidence: float | None = None
    description: dict = field(default_factory=dict)  # what a vision model saw (maps, posters, signs)

    def row(self) -> dict:
        """Flat dict for the documents table (nested parts as JSON text)."""
        d = {k: getattr(self, k) for k in (
            "title", "text", "method", "published_at", "updated_at", "language", "pages", "ocr_pages", "ocr_confidence")}  # fmt: skip
        for k in ("sections", "tables", "structured", "phones", "hours", "access_snippets", "description"):
            d[k] = json.dumps(getattr(self, k), ensure_ascii=False)
        return d


# ---- helpers --------------------------------------------------------------------------------------------------------


def split_sections(markdown: str) -> list[dict]:
    """[{path: 'Visit > Parking', text}] from markdown headings, so every passage keeps the heading it sits under."""
    stack: list[tuple[int, str]] = []
    out, buf = [], []
    for line in markdown.splitlines():
        m = HEADING.match(line)
        if m:
            if buf and "".join(buf).strip():
                out.append({"path": " > ".join(t for _, t in stack), "text": "\n".join(buf).strip()})
            level = len(m.group(1))
            stack = [(lv, t) for lv, t in stack if lv < level] + [(level, m.group(2))]
            buf = []
        else:
            buf.append(line)
    if "".join(buf).strip():
        out.append({"path": " > ".join(t for _, t in stack), "text": "\n".join(buf).strip()})
    return out


def find_phones(text: str) -> list[str]:
    text = privacy.scrub(text)  # a cell or home number is never extracted
    return sorted({f"({a}) {b}-{c}" for a, b, c in PHONE.findall(text)})[:10]


def find_hours(text: str) -> list[str]:
    return list(dict.fromkeys(m.group(0).strip() for m in HOURS.finditer(text)))[:12]


def access_snippets(sections: list[dict], limit: int = 30) -> list[dict]:
    """Sentences that mention what wheelchair users ask about, with the section they sit in (the extractor reads these first)."""
    words = relevance.keywords()
    out = []
    for sec in sections:
        for sent in re.split(r"(?<=[.!?])\s+|\n+", sec["text"]):
            s = sent.strip()
            if 15 <= len(s) <= 400 and any(w in s.lower() for w in words):
                out.append({"section": sec["path"], "sentence": s})
                if len(out) >= limit:
                    return out
    return out


def html_tables(html: bytes) -> list[dict]:
    """Every real data table as {caption, header, rows}; layout tables with one row or one column are skipped."""
    try:
        root = lxml_html.fromstring(html)
    except (ValueError, lxml_html.etree.ParserError):
        return []
    out = []
    for t in root.iter("table"):
        rows = [[" ".join(c.text_content().split()) for c in r.xpath("./th|./td")] for r in t.iter("tr")]
        rows = [r for r in rows if any(r)]
        if len(rows) >= 2 and max(len(r) for r in rows) >= 2:
            cap = t.find("caption")
            has_header = bool(t.xpath(".//th"))
            out.append({
                "caption": " ".join(cap.text_content().split()) if cap is not None else "",
                "header": rows[0] if has_header else [],
                "rows": rows[1:] if has_header else rows,
            })  # fmt: skip
    return out[:30]


def structured_data(html: bytes, url: str) -> dict:
    """What the page says about itself: JSON-LD, Microdata and Open Graph, reduced to the fields that matter to us."""
    try:
        import extruct

        data = extruct.extract(
            html.decode("utf-8", "ignore"),
            base_url=url,
            syntaxes=["json-ld", "microdata", "opengraph"],
            uniform=True,
        )
    except Exception:
        return {}
    keep = ("@type", "name", "description", "url", "telephone", "address", "geo", "openingHours", "openingHoursSpecification",
            "amenityFeature", "isAccessibleForFree", "publicAccess", "accessibilityFeature", "accessibilityHazard",
            "accessibilitySummary", "event", "startDate", "endDate", "location", "image", "sameAs")  # fmt: skip
    items = []
    for syntax in ("json-ld", "microdata"):
        for it in data.get(syntax, []):
            if isinstance(it, dict):
                items.append({k: it[k] for k in keep if k in it} | {"_syntax": syntax})
    og = data.get("opengraph") or []
    out = {"items": items[:20]}
    if og:
        out["opengraph"] = {
            k: v
            for k, v in (og[0] if isinstance(og, list) else og).items()
            if k in ("og:title", "og:description", "og:type", "og:url", "og:image")
        }
    return out if (items or og) else {}


# ---- HTML -----------------------------------------------------------------------------------------------------------


def read_html(data: bytes, url: str, fallback_clean) -> Read:
    import trafilatura

    r = Read(kind="html")
    text = md = None
    try:
        md = trafilatura.extract(data, url=url, output_format="markdown", include_tables=True, include_comments=False,
                                 favor_recall=True, deduplicate=False)  # fmt: skip
        meta = trafilatura.extract_metadata(data, default_url=url)
        if meta:
            r.title = meta.title or ""
            r.language = getattr(meta, "language", None)
    except Exception:
        md = None
    if md and len(md) >= 80:
        r.method, text = "trafilatura", md
    else:  # too little found: the older whole-page extractor never returns nothing
        title, fb, _ = fallback_clean(data, url)
        r.method, text, r.title = "fallback", fb, r.title or title
    r.text = text
    r.sections = split_sections(text)
    r.tables = html_tables(data)
    r.structured = structured_data(data, url)
    try:
        from htmldate import find_date

        r.published_at = find_date(data, original_date=True, outputformat="%Y-%m-%d")
        r.updated_at = find_date(data, original_date=False, outputformat="%Y-%m-%d")
    except Exception:
        pass
    try:
        root = lxml_html.fromstring(data)
        r.language = r.language or root.get("lang") or None
    except (ValueError, lxml_html.etree.ParserError):
        pass
    plain = re.sub(r"[#*_`|>]+", " ", text)
    r.phones, r.hours = find_phones(plain), find_hours(plain)
    r.access_snippets = access_snippets(r.sections or [{"path": "", "text": text}])
    return r


# ---- images and scans (OCR) -----------------------------------------------------------------------------------------


@cache
def _ocr():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def ocr_array(arr) -> tuple[str, float | None]:
    """(text in reading order, mean confidence) from an image array."""
    result, _ = _ocr()(arr)
    if not result:
        return "", None
    rows = sorted(
        result, key=lambda r: (round(r[0][0][1] / 20), r[0][0][0])
    )  # top to bottom, then left to right
    text = "\n".join(r[1] for r in rows)
    return text, round(sum(float(r[2]) for r in result) / len(result), 3)


def is_small_image(data: bytes) -> bool:
    """True for icons and logos (checked from the file header, without decoding the picture)."""
    try:
        from PIL import Image

        w, h = Image.open(io.BytesIO(data)).size
        return max(w, h) < MIN_IMAGE_SIDE or w * h < MIN_IMAGE_AREA
    except Exception:
        return False


def read_image(data: bytes) -> Read:
    """OCR of a poster, sign or map; icons and logos (small images) are skipped."""
    import numpy as np
    from PIL import Image

    r = Read(kind="image")
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception:
        r.method = "unreadable image"
        return r
    if max(img.size) < MIN_IMAGE_SIDE or img.size[0] * img.size[1] < MIN_IMAGE_AREA:  # icons and logos
        r.method = "skipped: small image"
        return r
    if max(img.size) > MAX_IMAGE_SIDE:
        img.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    r.text, r.ocr_confidence = ocr_array(np.array(img))
    r.method, r.pages, r.ocr_pages = "ocr", 1, 1
    r.sections = [{"path": "", "text": r.text}] if r.text else []
    r.access_snippets = access_snippets(r.sections)
    return r


def _worker() -> None:
    """Entry point of the isolated process that reads a PDF from stdin and prints the result as JSON."""
    import sys
    from dataclasses import asdict

    print(json.dumps(asdict(read_pdf(sys.stdin.buffer.read()))))


def _run_worker(data: bytes, timeout: float) -> Read | None:
    """The PDF reader in a separate process; None if it crashed or timed out."""
    import subprocess
    import sys

    try:
        p = subprocess.run([sys.executable, "-I", "-W", "ignore", "-c", "from atlas.crawler.read import _worker; _worker()"],
                           input=data, capture_output=True, timeout=timeout)  # fmt: skip
        if p.returncode == 0:
            return Read(**json.loads(p.stdout.decode("utf-8", "replace").strip().splitlines()[-1]))
    except (subprocess.TimeoutExpired, ValueError, TypeError):
        pass
    return None


def read_pdf_isolated(data: bytes, timeout: float = 240.0) -> Read:
    """read_pdf in a separate process with a time limit, so a booby-trapped or crashing PDF cannot take the crawler
    down. If PyMuPDF crashes on a file (it happens), the slower pure-Python reader pypdf is tried, also isolated."""
    r = _run_worker(data, timeout)
    if r is not None:
        return r
    from . import safety

    text = safety.safe_pdf_text(data)
    if text and not text.startswith("[pdf text extraction"):
        out = Read(
            kind="pdf", method="pypdf (after pymupdf failed)", text=text, sections=split_sections(text)
        )
        out.phones, out.hours = find_phones(text), find_hours(text)
        out.access_snippets = access_snippets(out.sections or [{"path": "", "text": text}])
        return out
    return Read(kind="pdf", method="failed: no pdf reader could open it")


# ---- PDF ------------------------------------------------------------------------------------------------------------


def read_pdf(data: bytes) -> Read:
    """Text by page; tables; OCR for pages that are pictures. Page numbers are kept ('## Page 3') so quotes can cite them."""
    import numpy as np
    import pymupdf

    r = Read(kind="pdf", method="pymupdf")
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception:
        r.method = "unreadable pdf"
        return r
    parts, confs = [], []
    r.pages = min(len(doc), MAX_PDF_PAGES)
    r.title = (doc.metadata or {}).get("title") or ""
    for n in range(r.pages):
        page = doc[n]
        text = page.get_text("text").strip()
        if len(text) < SCAN_CHARS and r.ocr_pages < MAX_OCR_PAGES and (page.get_images() or not text):
            pix = page.get_pixmap(dpi=OCR_DPI, alpha=False)
            arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            text, conf = ocr_array(arr[:, :, :3])
            r.ocr_pages += 1
            if conf is not None:
                confs.append(conf)
        try:
            for t in page.find_tables().tables[:5]:
                rows = [[(c or "").strip() for c in row] for row in t.extract()]
                if len(rows) >= 2:
                    r.tables.append({"caption": f"page {n + 1}", "header": rows[0], "rows": rows[1:]})
        except Exception:
            pass
        parts.append(f"## Page {n + 1}\n\n{text}")
    r.text = "\n\n".join(parts)
    r.sections = split_sections(r.text)
    if r.ocr_pages:
        r.method = "pymupdf+ocr"
        r.ocr_confidence = round(sum(confs) / len(confs), 3) if confs else None
    plain = re.sub(r"[#*_`|>]+", " ", r.text)
    r.phones, r.hours = find_phones(plain), find_hours(plain)
    r.access_snippets = access_snippets(r.sections)
    return r
