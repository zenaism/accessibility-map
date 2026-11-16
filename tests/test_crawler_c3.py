"""Phase C3: reading pages, PDFs and pictures (text with structure, OCR)."""

import json

import pandas as pd
import pytest

from atlas.connectors.web import _clean_html
from atlas.crawler import read
from tests.crawler_site import ICON, POSTER, RICH, SCAN_PDF, TEXT_PDF, Site
from tests.test_crawler import crawl

# ---- HTML -----------------------------------------------------------------------------------------------------------


def test_html_keeps_the_main_text_and_drops_the_menu():
    r = read.read_html(RICH, "http://x.org/visit", _clean_html)
    assert r.method == "trafilatura" and "step-free" in r.text
    assert "Cookie settings" not in r.text and "Copyright" not in r.text


def test_sections_keep_their_heading_path():
    r = read.read_html(RICH, "http://x.org/visit", _clean_html)
    paths = {s["path"] for s in r.sections}
    assert {"Visit > Accessibility", "Visit > Hours"} <= paths
    snippet = next(s for s in r.access_snippets if "step-free" in s["sentence"])
    assert snippet["section"] == "Visit > Accessibility"


def test_tables_become_rows():
    r = read.read_html(RICH, "http://x.org/visit", _clean_html)
    assert r.tables == [
        {"caption": "Parking", "header": ["Lot", "Spaces"], "rows": [["A", "12"], ["B", "4 van accessible"]]}
    ]


def test_structured_data_dates_phones_and_hours():
    r = read.read_html(RICH, "http://x.org/visit", _clean_html)
    item = r.structured["items"][0]
    assert (
        item["name"] == "City Museum"
        and item["telephone"] == "513-555-0142"
        and item["openingHours"] == "Mo-Su 10:00-17:00"
    )
    assert r.published_at == "2025-03-10" and r.language == "en"
    assert r.phones == ["(513) 555-0142"]
    assert "Mon-Fri 10 am to 5 pm" in r.hours and "Sat 10 am to 6 pm" in r.hours


def test_short_pages_fall_back_to_the_simple_extractor():
    r = read.read_html(
        b"<html><title>Hi</title><body><p>Short.</p></body></html>", "http://x.org/", _clean_html
    )
    assert r.method == "fallback" and "Short." in r.text


def test_split_sections_nests_headings():
    secs = read.split_sections("# A\nintro\n## B\nbody\n# C\nother")
    assert [s["path"] for s in secs] == ["A", "A > B", "C"]


# ---- PDF and images ---------------------------------------------------------------------------------------------------


def test_text_pdf_is_read_by_page():
    r = read.read_pdf(TEXT_PDF)
    assert r.pages == 2 and r.method == "pymupdf" and r.ocr_pages == 0
    assert "## Page 1" in r.text and "Lot B" in r.text and r.phones == ["(513) 555-0142"]


def test_scanned_pdf_is_read_with_ocr_in_a_separate_process():
    r = read.read_pdf_isolated(SCAN_PDF)
    assert r.method == "pymupdf+ocr" and r.ocr_pages == 1 and r.ocr_confidence and r.ocr_confidence > 0.5
    assert "restroom" in r.text.lower() and "level two" in r.text.lower()


def test_poster_image_is_read_and_icons_are_skipped():
    p = read.read_image(POSTER)
    assert p.method == "ocr" and "accessible" in p.text.lower() and "trail" in p.text.lower()
    assert read.read_image(ICON).method == "skipped: small image"


def test_garbage_pdf_does_not_crash_the_reader():
    assert read.read_pdf_isolated(b"this is not a pdf").method.startswith(("unreadable", "failed"))


# ---- through the crawler --------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def reading_crawl(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("c3")
    with Site() as site:
        crawl(tmp, site, name="c3", spec={"render": "never"})
        yield pd.read_parquet(tmp / "processed" / "testregion" / "c3.docs.parquet")


def test_documents_table_has_the_new_structure(reading_crawl):
    page = reading_crawl[reading_crawl.url.str.endswith("/rich")].iloc[0]
    assert page.method == "trafilatura" and page.published_at == "2025-03-10"
    assert "Visit > Accessibility" in json.loads(page.sections)[1]["path"]
    assert json.loads(page.tables)[0]["rows"][1] == ["B", "4 van accessible"]
    assert json.loads(page.structured)["items"][0]["name"] == "City Museum"


def test_scans_and_posters_become_text_documents(reading_crawl):
    scan = reading_crawl[reading_crawl.url.str.endswith("/scan.pdf")].iloc[0]
    assert scan.method == "pymupdf+ocr" and "restroom" in scan.text.lower()
    poster = reading_crawl[reading_crawl.url.str.endswith("/poster.png")].iloc[0]
    assert poster.method == "ocr" and "accessible" in poster.text.lower()
    icon = reading_crawl[reading_crawl.url.str.endswith("/icon.png")].iloc[0]
    assert icon.method == "skipped: small image" and icon.text == ""


def test_a_pdf_the_main_reader_crashes_on_is_read_by_the_fallback(monkeypatch):
    monkeypatch.setattr(read, "_run_worker", lambda data, timeout: None)  # as if PyMuPDF crashed
    r = read.read_pdf_isolated(TEXT_PDF)
    assert r.method == "pypdf (after pymupdf failed)" and "Lot B" in r.text


def test_small_images_are_recognised_from_the_header():
    assert read.is_small_image(ICON) and not read.is_small_image(POSTER)


def test_identical_files_become_one_document_and_legacy_word_is_flagged(reading_crawl):
    dups = reading_crawl[reading_crawl.url.str.contains("/dup/")]
    assert len(dups) == 1 and len(json.loads(dups.iloc[0].duplicate_urls)) == 1
    old = reading_crawl[reading_crawl.url.str.endswith("/old.doc")].iloc[0]
    assert old.method.startswith("skipped: legacy .doc")
