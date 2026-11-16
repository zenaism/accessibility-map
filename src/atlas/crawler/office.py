"""Text from Word, Excel and PowerPoint files, with no extra libraries (they are zip files of XML).
Zip bombs are refused before anything is read."""

from __future__ import annotations

import io
import re
import zipfile

from lxml import etree

MAX_UNCOMPRESSED = 200 * 1024 * 1024
MAX_RATIO = 100
MAX_ROWS = 5000
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


class Unsafe(ValueError):
    pass


def _open(data: bytes) -> zipfile.ZipFile:
    z = zipfile.ZipFile(io.BytesIO(data))
    total = sum(i.file_size for i in z.infolist())
    if total > MAX_UNCOMPRESSED or (len(data) and total / len(data) > MAX_RATIO):
        raise Unsafe("zip too large when unpacked (possible zip bomb)")
    return z


def _xml(z: zipfile.ZipFile, name: str):
    return etree.fromstring(z.read(name), parser=etree.XMLParser(resolve_entities=False, no_network=True))


def docx_text(data: bytes) -> str:
    z = _open(data)
    root = _xml(z, "word/document.xml")
    lines = []
    for p in root.iter(W + "p"):
        text = "".join(t.text or "" for t in p.iter(W + "t")).strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


def xlsx_text(data: bytes) -> str:
    z = _open(data)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        shared = [
            "".join(t.text or "" for t in si.iter(S + "t"))
            for si in _xml(z, "xl/sharedStrings.xml").iter(S + "si")
        ]
    out = []
    for name in sorted(n for n in z.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)):
        out.append(f"## {name.split('/')[-1][:-4]}")
        for n, row in enumerate(_xml(z, name).iter(S + "row")):
            if n >= MAX_ROWS:
                out.append("[more rows not read]")
                break
            cells = []
            for c in row.iter(S + "c"):
                v = c.find(S + "v")
                inline = "".join(t.text or "" for t in c.iter(S + "t"))
                cells.append(
                    shared[int(v.text)]
                    if c.get("t") == "s" and v is not None
                    else inline or (v.text if v is not None else "")
                )
            cells = ["" if c is None else str(c) for c in cells]  # empty and formula cells have no text
            if any(cells):
                out.append(" | ".join(cells))
    return "\n".join(out)


def pptx_text(data: bytes) -> str:
    z = _open(data)
    out = []
    for name in sorted(
        (n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
        key=lambda n: int(re.findall(r"\d+", n)[0]),
    ):
        out.append("\n".join(t.text or "" for t in _xml(z, name).iter(A + "t") if t.text))
    return "\n\n".join(out)


def extract(data: bytes, ext: str) -> str:
    """Text of a .docx, .xlsx or .pptx; empty string for anything else or a refused file."""
    try:
        return {"docx": docx_text, "xlsx": xlsx_text, "pptx": pptx_text}[ext.lstrip(".").lower()](data)
    except (
        Unsafe,
        zipfile.BadZipFile,
        KeyError,
        etree.XMLSyntaxError,
        TypeError,
        ValueError,
        AttributeError,
        IndexError,
    ) as e:
        return f"[could not read {ext}: {e or type(e).__name__}]"
