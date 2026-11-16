"""The crawler against a local website full of traps (tests/crawler_site.py): each test proves one requirement
from docs/crawler_plan.md. Each crawl runs in its own process, exactly as in real use."""

import json
import os
import subprocess
import sys
from collections import Counter

import pandas as pd
import pytest

from atlas.crawler import urls
from tests.crawler_site import Site

SPEC = {
    "regions": ["testregion"],
    "author_type": "official",
    "scope": {"depth": 4},
    "budget": {"pages": 200, "megabytes": 50, "per_pattern": 40},
    "assets": "all",
    "discover": {"sitemaps": True, "feeds": True, "probe_paths": False},
    "explore_share": 0.0,
}


def crawl(tmp_path, site, name="t", delay="0.05", extra=(), spec=None, env_extra=None):
    spec = {**SPEC, **(spec or {}), "seeds": [site.url + "/"]}
    sf = tmp_path / f"{name}.json"
    sf.write_text(json.dumps(spec))
    env = {**os.environ, "ATLAS_RAW_DIR": str(tmp_path / "raw"), "ATLAS_CRAWL_DIR": str(tmp_path / "crawl"),
           "ATLAS_PROCESSED_DIR": str(tmp_path / "processed"), **(env_extra or {})}  # fmt: skip
    r = subprocess.run([sys.executable, "-m", "atlas.crawler.run", name, "--spec-file", str(sf), "--delay", delay,
                        "--allow-private", *extra], env=env, capture_output=True, text=True, timeout=180)  # fmt: skip
    assert r.returncode == 0, r.stderr[-2000:]
    rep = json.loads((tmp_path / "crawl" / name / "report.json").read_text())
    return rep


def frontier_rows(tmp_path, name="t"):
    from atlas.crawler.frontier import Frontier

    f = Frontier(tmp_path / "crawl" / name / "frontier.sqlite")
    rows = {r["url"].replace("http://127.0.0.1:", "").split("/", 1)[-1]: r for r in f.rows()}
    f.close()
    return rows


@pytest.fixture
def run_once(tmp_path):
    with Site() as site:
        rep = crawl(tmp_path, site)
        yield tmp_path, site, rep


def test_obeys_robots_and_records_the_block(run_once):
    tmp, site, rep = run_once
    assert "/private/secret" not in site.paths()
    row = next(r for u, r in frontier_rows(tmp).items() if u.endswith("private/secret"))
    assert row["state"] == "blocked" and row["reason"] == "robots.txt"


def test_finds_pages_only_the_sitemap_knows(run_once):
    tmp, site, rep = run_once
    assert "/hidden-orphan" in site.paths()
    row = next(r for u, r in frontier_rows(tmp).items() if u.endswith("hidden-orphan"))
    assert row["via"] == "sitemap" and row["state"] == "fetched"
    assert rep["sitemap"]["coverage"] == 1.0


def test_calendar_trap_is_not_followed(run_once):
    tmp, site, rep = run_once
    assert not [p for p in site.paths() if p.startswith("/calendar")]
    assert any("trap guard" in (r["reason"] or "") for r in frontier_rows(tmp).values())


def test_duplicate_addresses_are_fetched_once(run_once):
    tmp, site, rep = run_once
    assert Counter(p.split("?")[0] for p in site.paths())["/about"] == 1


def test_retry_after_is_honoured(run_once):
    tmp, site, rep = run_once
    hits = [t for p, t, _ in site.log if p == "/flaky"]
    assert len(hits) == 2 and hits[1] - hits[0] >= 0.9  # waited the 1 second the server asked for
    row = next(r for u, r in frontier_rows(tmp).items() if u.endswith("flaky"))
    assert row["state"] == "fetched" and row["status"] == 200


def test_pdf_and_redirect_and_404_are_recorded(run_once):
    tmp, site, rep = run_once
    rows = frontier_rows(tmp)
    pdf = next(r for u, r in rows.items() if u.endswith("guide.pdf"))
    assert pdf["state"] == "fetched" and pdf["content_type"] == "application/pdf"
    assert next(r for u, r in rows.items() if u.endswith("missing"))["state"] == "failed"
    raw = list((tmp / "raw" / "web" / "t").glob("*.pdf"))
    assert raw and raw[0].read_bytes().startswith(b"%PDF")


def test_every_url_has_a_final_state_and_a_manifest_line(run_once):
    tmp, site, rep = run_once
    assert rep["gate_status_audit"] and rep["unfinished_queued"] == 0
    manifest = [
        json.loads(x) for x in (tmp / "raw" / "web" / "t" / "manifest.jsonl").read_text().splitlines()
    ]
    assert manifest and all(m["sha256"] and m["status"] and "crawler" in m for m in manifest)


def test_documents_table_is_written(run_once):
    tmp, site, rep = run_once
    df = pd.read_parquet(tmp / "processed" / "testregion" / "t.docs.parquet")
    assert {"doc_id", "text", "url", "relevance", "discovered_via", "content_sha"} <= set(df.columns)
    assert df.loc[df.url.str.endswith("/accessibility"), "text"].str.contains("wheelchair").any()


def test_relevant_pages_come_first_when_the_budget_is_small(tmp_path):
    with Site() as site:
        rep = crawl(tmp_path, site, spec={"budget": {"pages": 12, "megabytes": 50}})
        fetched = {p.split("?")[0] for p in site.paths()}
        assert (
            "/accessibility" in fetched and "/visit/parking" in fetched
        )  # best-first beat the 30 blog posts
        assert rep["unfinished_queued"] > 0 and rep["complete"] is False  # an incomplete crawl says so


def test_second_crawl_uses_conditional_requests(tmp_path):
    with Site() as site:
        crawl(tmp_path, site)
        first = len(site.log)
        crawl(tmp_path, site, extra=["--fresh"])
        again = [h for p, _, h in site.log[first:] if p == "/accessibility"]
        assert again and again[0].get("If-None-Match") == '"acc-v1"'
        assert (
            next(r for u, r in frontier_rows(tmp_path).items() if u.endswith("accessibility"))["state"]
            == "unchanged"
        )


def test_crawl_resumes_without_refetching(tmp_path):
    with Site() as site:
        crawl(tmp_path, site, spec={"budget": {"pages": 10, "megabytes": 50}})
        part = Counter(p for p in site.paths() if p not in ("/robots.txt", "/sitemap.xml"))
        crawl(tmp_path, site)  # same queue on disk: carries on
        total = Counter(p for p in site.paths() if p not in ("/robots.txt", "/sitemap.xml"))
        twice_by_design = {"/flaky", "/spa", "/accordion"}  # 429 then retry; plain fetch then browser render
        assert (
            max(n for p, n in total.items() if p not in twice_by_design and not p.startswith("/thin/")) == 1
        )
        assert len(total) > len(part)


def test_pages_the_sitemap_lists_are_fetched_even_with_no_keywords(tmp_path):
    with Site() as site:
        crawl(tmp_path, site, spec={"budget": {"pages": 12, "megabytes": 50}})
        fetched = {p for p in site.paths() if p.startswith("/dir/place-")}
        assert len(fetched) == 6  # all six directory pages, ahead of the 30 blog posts


def test_stop_is_real_the_queue_is_not_drained(tmp_path):
    with Site() as site:
        rep = crawl(tmp_path, site, spec={"budget": {"pages": 5, "megabytes": 50}})
        pages = [p for p in site.paths() if not p.startswith(("/img/", "/robots", "/sitemap"))]
        assert len(pages) <= 15  # budget of 5 plus the (at most 8) requests already handed to the downloader
        assert len(pages) < 40  # the site has far more pages: the queue was not drained
        assert rep["ended"] == "page budget reached" and rep["unfinished_queued"] > 0


def test_images_have_their_own_budget(tmp_path):
    with Site() as site:
        crawl(tmp_path, site, spec={"budget": {"pages": 40, "images": 3, "megabytes": 50}})
        images = [p for p in site.paths() if p.startswith("/img/")]
        assert (
            0 < len(images) <= 6
        )  # at most 3 large pictures, up to twice that many requests (icons are only known after)
        assert "/accessibility" in site.paths() and "/hidden-orphan" in site.paths()


def test_pagination_does_not_count_toward_depth(tmp_path):
    with Site() as site:
        crawl(tmp_path, site, spec={"scope": {"depth": 3}})
        assert (
            "/list/page/8" in site.paths()
        )  # eight pages deep, but each is just the next page of one listing


def test_auto_budget_grows_with_the_sitemap(tmp_path):
    with Site() as site:
        rep = crawl(
            tmp_path,
            site,
            spec={"budget": {"pages": "auto", "auto_min": 3, "auto_max": 100, "megabytes": 50}},
        )
        assert (
            len([p for p in site.paths() if p.startswith("/dir/place-")]) == 6
        )  # the sitemap listed them: budget grew
        assert rep["by_state"].get("fetched", 0) > 3


def test_files_in_deep_folders_are_not_mistaken_for_traps(tmp_path):
    with Site() as site:
        crawl(tmp_path, site)
        assert (
            "/a/b/c/d/e/f/g/h/i/deep-guide.pdf" in site.paths()
        )  # pages that deep would be skipped; files are fine
        assert (
            next(r for u, r in frontier_rows(tmp_path).items() if u.endswith("deep-guide.pdf"))["state"]
            == "fetched"
        )


def test_translation_copies_are_skipped_unless_wanted(tmp_path):
    with Site() as site:
        crawl(tmp_path, site)
        assert "/es/visite" not in site.paths()
        row = next(r for u, r in frontier_rows(tmp_path).items() if u.endswith("es/visite"))
        assert row["state"] == "skipped" and row["reason"] == "translation (es)"
        crawl(tmp_path, site, name="t2", spec={"scope": {"depth": 4, "languages": ["en", "es"]}})
        assert "/es/visite" in site.paths()


def test_missing_guessed_paths_are_not_failures(tmp_path):
    with Site() as site:
        crawl(tmp_path, site, spec={"discover": {"sitemaps": True, "feeds": True, "probe_paths": True}})
        row = next(r for u, r in frontier_rows(tmp_path).items() if u.endswith("ada"))
        assert row["state"] == "skipped" and row["reason"].startswith("probe: not found")
        failed = [r for r in frontier_rows(tmp_path).values() if r["state"] == "failed"]
        assert failed and not any(
            r["via"] == "probe" for r in failed
        )  # real broken links only, never our guesses


def test_each_site_gets_its_own_page_budget(tmp_path):
    with Site() as site:
        crawl(tmp_path, site, spec={"budget": {"pages": 100, "per_host": 6, "megabytes": 50}})
        pages = [p for p in site.paths() if not p.startswith(("/img/", "/robots", "/sitemap"))]
        rows = frontier_rows(tmp_path)
        assert not any(
            r["reason"] == "host budget" for r in rows.values()
        )  # over-budget URLs are counted, not stored
        assert len(rows) < 120
        assert (
            len(set(pages)) <= 6 + 12
        )  # six queued pages plus probes, the robots/sitemap files and in-flight requests


def test_pages_know_the_place_their_website_belongs_to(tmp_path):
    with Site() as site:
        host = site.url.split("//")[1].split(":")[0]
        crawl(
            tmp_path,
            site,
            name="pl",
            spec={
                "seed_places": {host: {"place_id": "overture:123", "name": "Test Cafe", "category": "cafe"}}
            },
        )
        d = pd.read_parquet(tmp_path / "processed" / "testregion" / "pl.docs.parquet")
        assert (d.place_id == "overture:123").all() and (d.place_name == "Test Cafe").all()


def test_place_seeds_skip_chains_and_aggregators(monkeypatch):
    import geopandas as gpd
    from shapely.geometry import Point

    from atlas.crawler import seeds

    rows = [("a", "Local Cafe", "https://localcafe.com", 0.9), ("b", "Chain", "https://bigchain.com/1", 0.8),
            ("c", "Chain", "https://bigchain.com/2", 0.8), ("d", "Chain", "https://bigchain.com/3", 0.8),
            ("e", "On Yelp", "https://www.yelp.com/biz/x", 0.9), ("f", "No site", None, 0.9)]  # fmt: skip
    gdf = gpd.GeoDataFrame({"entity_id": [r[0] for r in rows], "name": [r[1] for r in rows], "website": [r[2] for r in rows],
                            "confidence": [r[3] for r in rows], "basic_category": "cafe"}, geometry=[Point(0, 0)] * 6)  # fmt: skip
    monkeypatch.setattr(seeds.gpd, "read_parquet", lambda p: gdf)
    found = seeds.places("x", {"cafe"}, 10)
    assert [p["name"] for p in found] == ["Local Cafe"]
    spec = seeds.crawl_spec("x", found)
    assert (
        spec["seeds"] == ["https://localcafe.com/"]
        and spec["seed_places"]["localcafe.com"]["place_id"] == "a"
    )


def test_relative_sitemap_addresses_in_robots_txt_are_resolved():
    assert urls.normalize("/sitemap.xml", "https://www.example.gov/") == "https://www.example.gov/sitemap.xml"
    assert urls.normalize("https://other.org/s.xml", "https://www.example.gov/") == "https://other.org/s.xml"
