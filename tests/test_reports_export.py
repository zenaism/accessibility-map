"""The team's export: rows from the database become a spreadsheet, photo files and a gallery page."""

import csv
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from atlas import reports_export

JPEG = b"\xff\xd8\xff\xe0" + b"x" * 50
ROWS = [
    {"id": f"{i:08x}-0000-4000-8000-000000000000", "created_at": f"2026-11-1{i}T10:00:00+00:00", "status": "new", "category": "blocked_or_broken",
     "place_name": "Cafe <b>", "link_id": "cafe", "region": "oxford", "description": "Ramp <script>alert(1)</script> blocked", "contact": None,
     "photo": "\\x" + JPEG.hex() if i % 2 == 0 else None, "page_url": "https://x", "team_notes": None}
    for i in range(1, 46)
]  # fmt: skip


@pytest.fixture
def server():
    seen = []

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            seen.append((self.path, dict(self.headers)))
            a, b = self.headers["Range"].split("-")
            body = json.dumps(ROWS[int(a) : int(b) + 1]).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    s = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{s.server_address[1]}", seen
    s.shutdown()


def test_all_pages_are_fetched_with_the_service_key(server):
    url, seen = server
    rows = reports_export.fetch_all(url, "secret-key", status="new")
    assert len(rows) == 45 and len(seen) == 3  # 20 + 20 + 5
    assert seen[0][1]["apikey"] == "secret-key" and "status=eq.new" in seen[0][0]


def test_export_writes_csv_photos_and_a_safe_gallery(tmp_path):
    page = reports_export.export(ROWS, tmp_path)
    assert page.name == "index.html"
    with (tmp_path / "reports.csv").open() as f:
        out = list(csv.DictReader(f))
    assert len(out) == 45 and out[0]["ref"] == "0000000" + "1" and out[1]["photo"].startswith("photos/")
    photos = list((tmp_path / "photos").glob("*.jpg"))
    assert len(photos) == 22 and photos[0].read_bytes()[:3] == b"\xff\xd8\xff"
    text = page.read_text()
    assert (
        "<script>alert(1)</script>" not in text and "&lt;script&gt;" in text
    )  # report text can never run code in the gallery
    assert "Cafe &lt;b&gt;" in text


def test_service_key_is_required(monkeypatch):
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    with pytest.raises(SystemExit, match="SUPABASE_SERVICE_KEY"):
        reports_export.config()
