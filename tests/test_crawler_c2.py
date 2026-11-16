"""Phase C2: browser fallback, hidden content, Office files and safety checks."""

import io
import zipfile

import pandas as pd
import pytest

from atlas.crawler import office, render, safety
from tests.crawler_site import DOCX, XLSX, Site
from tests.test_crawler import crawl, frontier_rows

# ---- pure functions ------------------------------------------------------------------------------------------------


def test_needs_render_detects_empty_app_shells():
    assert render.needs_render("", b"<div id=root></div><script src=app.js></script>")
    assert not render.needs_render("short page", b"<html><body>Contact us</body></html>")  # static and short: no browser
    assert render.needs_render("x" * 300, b"", "always")
    assert not render.needs_render("x" * 300, b"<html>" + b"y" * 400)
    assert not render.needs_render("", b"", "never")
    shell = (
        b'<html><body><div id="root"></div><noscript>You need to enable JavaScript</noscript></body></html>'
    )
    assert render.needs_render("y" * 400, shell)  # short page that is an app shell
    assert not render.needs_render("y" * 900, shell)  # plenty of real text: no browser needed


def test_sniff_and_mismatch():
    assert safety.sniff(b"%PDF-1.7 ...") == "pdf" and safety.sniff(b"\x89PNG....") == "png"
    assert safety.sniff(b"<!DOCTYPE html><html>") == "html"
    assert safety.mismatch("application/pdf", b"<html><body>error</body></html>").startswith(
        "claimed application/pdf"
    )
    assert safety.mismatch("application/pdf", b"%PDF-1.4") is None
    assert safety.mismatch("text/html", b"anything") is None


def test_office_text_is_read_without_extra_libraries():
    assert "Accessible seating is available in row A." in office.docx_text(DOCX)
    sheet = office.xlsx_text(XLSX)
    assert "Van accessible | 4" in sheet and "Lot | 12" in sheet
    assert office.extract(b"not a zip", "docx").startswith("[could not read")


def test_zip_bomb_is_refused():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", "A" * 60_000_000)  # compresses to almost nothing
    assert "zip too large" in office.extract(buf.getvalue(), "docx")


def test_private_addresses_are_recognised():
    assert render.is_private_host("127.0.0.1") and render.is_private_host("localhost")


def test_pdf_text_is_read_in_a_separate_process():
    assert safety.safe_pdf_text(b"this is not a pdf").startswith("[pdf text extraction")


# ---- the crawler with a real browser -------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def browser_crawl(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("c2")
    with Site() as site:
        crawl(tmp, site, name="c2", delay="0.5")
        yield tmp, site


def docs(tmp):
    return pd.read_parquet(tmp / "processed" / "testregion" / "c2.docs.parquet")


def test_javascript_built_page_is_rendered_and_its_links_followed(browser_crawl):
    tmp, site = browser_crawl
    d = docs(tmp)
    spa = d[d.url.str.endswith("/spa")].iloc[0]
    assert spa.rendered and "Step-free entrance" in spa.text and "lot B" in spa.text
    assert spa.screenshot and spa.screenshot.endswith(".screenshot.png")
    assert "/spa-details" in site.paths()  # a link that exists only after the script ran


def test_hidden_content_behind_a_button_is_opened(browser_crawl):
    tmp, _ = browser_crawl
    d = docs(tmp)
    page = d[d.url.str.endswith("/accordion")].iloc[0]
    assert page.rendered and "accessible restroom is on level two" in page.text


def test_word_and_excel_files_become_documents(browser_crawl):
    tmp, _ = browser_crawl
    d = docs(tmp).set_index("content_type")
    assert "row A" in d.loc["docx", "text"]
    assert "Van accessible | 4" in d.loc["xlsx", "text"]


def test_browser_load_respects_the_pause_between_requests(browser_crawl):
    tmp, site = browser_crawl
    hits = sorted(t for p, t, _ in site.log if p == "/spa")
    assert (
        len(hits) >= 2 and hits[1] - hits[0] >= 0.4
    )  # the browser waited the 0.5 s pause after the plain fetch


def test_rendered_pages_are_counted_in_the_report(browser_crawl):
    import json

    tmp, _ = browser_crawl
    rep = json.loads((tmp / "crawl" / "c2" / "report.json").read_text())
    assert rep["rendered_in_browser"] >= 2
    rows = frontier_rows(tmp, "c2")
    assert next(r for u, r in rows.items() if u.endswith("spa"))["rendered"] == 1


def test_browser_can_be_turned_off(tmp_path):
    with Site() as site:
        crawl(tmp_path, site, name="norender", spec={"render": "never"})
        assert "/spa-details" not in site.paths()
        d = pd.read_parquet(tmp_path / "processed" / "testregion" / "norender.docs.parquet")
        assert not d[d.url.str.endswith("/spa")].iloc[0].rendered
