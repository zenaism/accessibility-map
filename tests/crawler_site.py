"""A small local website full of crawler traps, used to test the crawler (tests/test_crawler.py).

It has: robots.txt with a Disallow and a Sitemap line · a page reachable only through the sitemap · an endless
calendar · duplicate addresses (tracking parameters) · a redirect · a 404 · a 429 with Retry-After · ETags (304) · a PDF.
Every request is logged with its time so tests can check behaviour (order, repeats, pauses, politeness).
"""

from __future__ import annotations

import io
import threading
import time
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, body in files.items():
            z.writestr(name, body)
    return buf.getvalue()


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
SS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOCX = _zip(
    {
        "word/document.xml": f'<w:document xmlns:w="{W}"><w:body><w:p><w:r><w:t>Accessible seating is available in row A.</w:t></w:r></w:p></w:body></w:document>'
    }
)
XLSX = _zip(
    {
        "xl/worksheets/sheet1.xml": f'<worksheet xmlns="{SS}"><sheetData><row><c t="inlineStr"><is><t>Lot</t></is></c><c><v>12</v></c></row><row><c t="inlineStr"><is><t>Van accessible</t></is></c><c><v>4</v></c></row></sheetData></worksheet>'
    }
)
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
SPA = (
    '<html><head><title>App</title></head><body><div id="root"></div><script>'
    "document.getElementById('root').innerHTML='<h1>Step-free entrance</h1><p>The wheelchair accessible entrance is on Main Street. "
    'Accessible parking is in lot B. <a href="/spa-details">More details</a></p>\'</script></body></html>'
)
ACCORDION = (
    "<html><head><title>Visit</title></head><body><button aria-expanded=\"false\" onclick=\"this.setAttribute('aria-expanded','true');"
    "document.getElementById('p').innerText='The accessible restroom is on level two next to the elevator.'\">Restrooms</button>"
    '<div id="p"></div></body></html>'
)


def _png(text: str, size=(900, 220)) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", size, "white")
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 56)
    except OSError:
        font = ImageFont.load_default()
    ImageDraw.Draw(img).text((30, size[1] // 2 - 30), text, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _scanned_pdf() -> bytes:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_image(page.rect, stream=_png("Accessible restroom on level two", (1400, 400)))
    return doc.tobytes()


def _text_pdf() -> bytes:
    import pymupdf

    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Accessible parking is available in Lot B.")
    doc.new_page().insert_text((72, 72), "Call (513) 555-0142 for assistance.")
    return doc.tobytes()


RICH = b"""<html lang="en"><head><title>Visit the Museum</title><meta property="article:published_time" content="2025-03-10">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Museum","name":"City Museum","telephone":"513-555-0142",
"address":{"@type":"PostalAddress","streetAddress":"1301 Western Ave","addressLocality":"Cincinnati","addressRegion":"OH"},
"openingHours":"Mo-Su 10:00-17:00"}</script></head>
<body><nav><a href=/>Home</a> <a href=/tickets>Tickets</a> Cookie settings</nav><main><h1>Visit</h1>
<p>Plan your trip to the museum with these tips for a smooth and enjoyable visit today.</p><h2>Accessibility</h2>
<p>The main entrance is step-free and wheelchair accessible. Accessible parking is on Lot B. Call (513) 555-0142 with questions.</p>
<h2>Hours</h2><p>Mon-Fri 10 am to 5 pm. Sat 10 am to 6 pm.</p>
<table><caption>Parking</caption><tr><th>Lot</th><th>Spaces</th></tr><tr><td>A</td><td>12</td></tr><tr><td>B</td><td>4 van accessible</td></tr></table>
</main><footer>Copyright 2025</footer></body></html>"""
POSTER = _png("Trail map: accessible loop")
ICON = _png("x", (60, 60))
SCAN_PDF = _scanned_pdf()
TEXT_PDF = _text_pdf()
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
ACCESS = (
    "<html><head><title>Accessibility</title></head><body><h1>Accessibility</h1>"
    "<p>Our wheelchair accessible entrance is on the north side. Accessible parking and an accessible restroom are available."
    ' See <a href="/visit/parking">parking</a>.</p></body></html>'
)


def page(title: str, body: str, links: list[tuple[str, str]]) -> bytes:
    a = "".join(f'<a href="{h}">{t}</a> ' for h, t in links)
    return f"<html><head><title>{title}</title></head><body><h1>{title}</h1><p>{body}</p>{a}</body></html>".encode()


class Site:
    def __init__(self):
        self.log: list[tuple[str, float, dict]] = []
        self.flaky_hits = 0
        self.terms: str | None = None  # text of /terms-of-use, if the site has one
        self.lock = threading.Lock()
        site = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def send(self, code, body=b"", ctype="text/html", headers=None):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                path = self.path
                with site.lock:
                    site.log.append((path, time.time(), dict(self.headers)))
                base = f"http://127.0.0.1:{site.port}"
                p = path.split("?")[0]
                if p == "/robots.txt":
                    return self.send(
                        200,
                        f"User-agent: *\nDisallow: /private/\nSitemap: {base}/sitemap.xml\n".encode(),
                        "text/plain",
                    )
                if p == "/sitemap.xml":
                    xml = (
                        '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                        f"<url><loc>{base}/hidden-orphan</loc><lastmod>2026-01-01</lastmod></url>"
                        f"<url><loc>{base}/visit/parking</loc></url>"
                        + "".join(f"<url><loc>{base}/dir/place-{i}</loc></url>" for i in range(1, 7))
                        + "</urlset>"
                    )
                    return self.send(200, xml.encode(), "application/xml")
                if p == "/terms-of-use" and site.terms:
                    return self.send(
                        200,
                        f"<html><title>Terms</title><body><h1>Terms of use</h1><p>{site.terms}</p></body></html>".encode(),
                    )
                if p == "/":
                    links = [("/accessibility", "Accessibility"), ("/about", "About"), ("/about?utm_source=news", "About again"),
                             ("/old", "Old"), ("/missing", "Missing"), ("/guide.pdf", "Accessibility guide"), ("/flaky", "Flaky"),
                             ("/private/secret", "Secret"), ("/calendar/2030/01/01", "Calendar")]  # fmt: skip
                    links += [(f"/blog/{i}", f"Post {i}") for i in range(1, 31)]
                    links += [(f"/img/{i}.jpg", "pic") for i in range(1, 16)]
                    links.append(("/list/page/1", "Listing"))
                    links += [
                        ("/rich", "Visit"),
                        ("/scan.pdf", "Scanned guide"),
                        ("/text.pdf", "Text guide"),
                        ("/poster.png", "Trail map poster"),
                        ("/icon.png", "icon"),
                    ]
                    links += [
                        ("/dup/a.pdf", "Report"),
                        ("/dup/b.pdf", "Report copy"),
                        ("/old.doc", "Old guide"),
                    ]
                    links += [(f"/icons/{i}.png", "icon") for i in range(1, 7)]
                    links += [("/es/visite", "Visite"), ("/a/b/c/d/e/f/g/h/i/deep-guide.pdf", "Deep guide")]
                    links += [(f"/thin/{i}", "Notice") for i in range(1, 9)]
                    links += [
                        ("/spa", "App"),
                        ("/accordion", "Visit"),
                        ("/doc.docx", "Seating guide"),
                        ("/sheet.xlsx", "Parking table"),
                    ]
                    return self.send(200, page("Home", "Welcome to the museum.", links))
                if p == "/accessibility":
                    etag = '"acc-v1"'
                    if self.headers.get("If-None-Match") == etag:
                        return self.send(304, b"", headers={"ETag": etag})
                    return self.send(200, ACCESS.encode(), headers={"ETag": etag})
                if p == "/visit/parking":
                    return self.send(
                        200, page("Parking", "Accessible parking for wheelchair users near the entrance.", [])
                    )
                if p == "/hidden-orphan":
                    return self.send(
                        200, page("Orphan", "An accessible restroom is on the ground floor.", [])
                    )
                if p.startswith("/dup/"):
                    return self.send(
                        200, TEXT_PDF + b"\n% fixture for the duplicate test\n", "application/pdf"
                    )
                if p == "/old.doc":
                    return self.send(200, b"\xd0\xcf\x11\xe0 legacy word", "application/msword")
                if p.startswith("/icons/"):
                    return self.send(200, ICON, "image/png")
                if p.startswith("/thin/"):
                    return self.send(200, b"<html><body>Notice.<script>var a=1;</script></body></html>")
                if p == "/es/visite":
                    return self.send(200, page("Visite", "Une page en espagnol.", []))
                if p.endswith("deep-guide.pdf"):
                    return self.send(200, TEXT_PDF, "application/pdf")
                if p == "/rich":
                    return self.send(200, RICH)
                if p == "/scan.pdf":
                    return self.send(200, SCAN_PDF, "application/pdf")
                if p == "/text.pdf":
                    return self.send(200, TEXT_PDF, "application/pdf")
                if p == "/poster.png":
                    return self.send(200, POSTER, "image/png")
                if p == "/icon.png":
                    return self.send(200, ICON, "image/png")
                if p == "/spa":
                    return self.send(200, SPA.encode())
                if p == "/spa-details":
                    return self.send(
                        200,
                        page(
                            "Details",
                            "Details about the entrance for wheelchair users and the accessible route.",
                            [],
                        ),
                    )
                if p == "/accordion":
                    return self.send(200, ACCORDION.encode())
                if p == "/doc.docx":
                    return self.send(200, DOCX, DOCX_TYPE)
                if p == "/sheet.xlsx":
                    return self.send(200, XLSX, XLSX_TYPE)
                if p.startswith("/list/page/"):
                    n = int(p.split("/")[-1])
                    nxt = [(f"/list/page/{n + 1}", "Next")] if n < 8 else []
                    return self.send(200, page(f"Listing {n}", "Entries.", nxt))
                if p.startswith("/img/"):
                    return self.send(200, b"\xff\xd8\xff\xe0fakejpeg", "image/jpeg")
                if p.startswith("/dir/place-"):
                    return self.send(200, page("Place", "A cozy place with good food.", []))
                if p == "/about":
                    return self.send(200, page("About", "About the museum.", []))
                if p == "/old":
                    return self.send(301, b"", headers={"Location": "/accessibility"})
                if p == "/guide.pdf":
                    return self.send(200, PDF, "application/pdf")
                if p == "/flaky":
                    with site.lock:
                        site.flaky_hits += 1
                        first = site.flaky_hits == 1
                    if first:
                        return self.send(429, b"slow down", headers={"Retry-After": "1"})
                    return self.send(
                        200, page("Flaky", "Sometimes slow. Accessible entrance information.", [])
                    )
                if p.startswith("/blog/"):
                    n = int(p.split("/")[-1])
                    return self.send(
                        200, page(f"Post {n}", "Museum news and notes.", [(f"/blog/{n + 1}", "next")])
                    )
                if p.startswith("/calendar/"):
                    return self.send(200, page("Calendar", "Events.", [("/calendar/2030/01/02", "next day")]))
                if p.startswith("/private/"):
                    return self.send(200, page("Secret", "private", []))
                return self.send(404, b"not found")

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.httpd.server_address[1]
        self.url = f"http://127.0.0.1:{self.port}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *a):
        self.httpd.shutdown()

    def paths(self) -> list[str]:
        return [p for p, _, _ in self.log]
