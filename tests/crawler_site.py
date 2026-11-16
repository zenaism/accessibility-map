"""A small local website full of crawler traps, used to test the crawler (tests/test_crawler.py).

It has: robots.txt with a Disallow and a Sitemap line · a page reachable only through the sitemap · an endless
calendar · duplicate addresses (tracking parameters) · a redirect · a 404 · a 429 with Retry-After · ETags (304) · a PDF.
Every request is logged with its time so tests can check behaviour (order, repeats, pauses, politeness).
"""

from __future__ import annotations

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

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
                        f"<url><loc>{base}/visit/parking</loc></url></urlset>"
                    )
                    return self.send(200, xml.encode(), "application/xml")
                if p == "/":
                    links = [("/accessibility", "Accessibility"), ("/about", "About"), ("/about?utm_source=news", "About again"),
                             ("/old", "Old"), ("/missing", "Missing"), ("/guide.pdf", "Accessibility guide"), ("/flaky", "Flaky"),
                             ("/private/secret", "Secret"), ("/calendar/2030/01/01", "Calendar")]  # fmt: skip
                    links += [(f"/blog/{i}", f"Post {i}") for i in range(1, 31)]
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
