# ruff: noqa: E501
"""The "Rate or report" form (session B2): one screen with a 1 to 5 star rating and a problem, built on the B0 foundation.

    from atlas import report_form
    report_form.css()            the form's CSS (needs the foundation CSS first)
    report_form.js()             the form (needs the foundation JS first)
    report_form.config_js(data)  <script> text that gives the form its settings and places

The form opens from the event atlas:open-report {placeId, region}. It talks to Supabase with the two existing functions,
submit_rating and submit_problem_report (and delete_problem_report); nothing in the SQL changes. Ratings accept only the
regions in RATING_REGIONS until supabase/ratings.sql is widened (owner decision, 2026-11-24).
"""

from __future__ import annotations

import json
from pathlib import Path

WEB = Path(__file__).with_name("web") / "report"
RATING_REGIONS = ["cincinnati", "oxford"]
GITHUB_FALLBACK = "https://github.com/zenaism/accessibility-map/issues/new"


def css() -> str:
    return (WEB / "report.css").read_text(encoding="utf-8")


def js() -> str:
    return (WEB / "report.js").read_text(encoding="utf-8")


def _json(obj) -> str:
    return (
        json.dumps(obj, ensure_ascii=False)
        .replace("</", "<\\/")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def config_js(ratecfg: dict | None) -> str:
    """window.__RATECFG: the public Supabase URL and publishable key, or null (then the form is not hooked and the Report
    tab keeps following its link)."""
    return f"window.__RATECFG={_json(ratecfg)};"
