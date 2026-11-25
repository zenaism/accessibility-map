"""The database script for problem reports: it parses, it is locked down, and it agrees with the form."""

import re
from pathlib import Path

import pglast
import pytest

from atlas.report_ui import JS

SQL = (Path(__file__).resolve().parents[1] / "supabase" / "problem_reports.sql").read_text()


def test_script_parses_as_postgres():
    assert len(pglast.parse_sql(SQL)) >= 14


def test_browsers_cannot_touch_the_table_or_the_review_view():
    assert "alter table public.problem_reports enable row level security" in SQL
    assert "revoke all on public.problem_reports from anon, authenticated" in SQL
    assert "revoke all on public.problem_reports_review from anon, authenticated" in SQL
    assert not re.search(r"grant\s+(select|insert|update|delete|all)\s+on\s+public\.problem_reports", SQL)


def test_the_only_public_doors_are_the_three_functions():
    grants = re.findall(r"grant execute on function public\.(\w+) to anon", SQL)
    assert sorted(grants) == ["delete_problem_report", "report_ping", "submit_problem_report"]
    assert (
        "revoke all on function public.purge_old_reports from public, anon, authenticated" in SQL
    )  # retention is the team's tool
    assert re.search(r"security definer set search_path = public", SQL)


def test_categories_match_the_form():
    sql_cats = set(
        re.findall(
            r"'(\w+)'",
            re.search(r"category\s+text not null check \(category in\s*\((.*?)\)\)", SQL, re.S).group(1),
        )
    )
    js_cats = set(re.findall(r"\['(\w+)', '", JS.split("REPORT_KINDS = [")[1].split("];")[0]))
    assert sql_cats == js_cats and len(js_cats) == 5


def test_limits_match_the_form():
    assert (
        "char_length(description) between 5 and 1000" in SQL
        and 'maxlength="1000"' in JS
        and "t.length < 5" in JS
    )
    assert (
        "octet_length(v_photo) > 250000" in SQL and "blob.size <= 200000" in JS
    )  # the browser aims below the server's limit
    assert "\\xffd8ff" in SQL  # only JPEG data is accepted


@pytest.mark.parametrize(
    "word",
    [
        "p_website",
        "on conflict (id) do nothing",
        "interval '1 day'",
        "interval '1 hour') >= 200",
        "pg_advisory_xact_lock",
    ],
)
def test_abuse_and_retry_protection_is_present(word):
    assert word in SQL


# ---- the new "Rate or report" form (src/atlas/web/report/report.js) must agree with both SQL scripts -------------------

RATINGS_SQL = (Path(__file__).resolve().parents[1] / "supabase" / "ratings.sql").read_text()
FORM_JS = (Path(__file__).resolve().parents[1] / "src" / "atlas" / "web" / "report" / "report.js").read_text()


def _params(sql: str, fn: str) -> set[str]:
    sig = re.search(rf"function public\.{fn}\((.*?)\)\s*returns", sql, re.S).group(1)
    return set(re.findall(r"\b(p_\w+)\b", sig))


def test_ratings_script_parses():
    assert len(pglast.parse_sql(RATINGS_SQL)) >= 8


def test_form_sends_exactly_the_parameters_the_functions_take():
    sent_rating = set(
        re.findall(
            r"\b(p_\w+):",
            FORM_JS.split("async function sendRating")[1].split("async function sendProblem")[0],
        )
    )
    assert sent_rating == _params(RATINGS_SQL, "submit_rating")
    sent_problem = set(
        re.findall(r"\b(p_\w+):", FORM_JS.split("async function sendProblem")[1].split("const kindOf")[0])
    )
    assert sent_problem == _params(SQL, "submit_problem_report")
    assert set(
        re.findall(r"\b(p_\w+):", FORM_JS.split("rpc('delete_problem_report', {")[1].split("}")[0])
    ) == _params(SQL, "delete_problem_report")


def test_form_categories_profiles_and_regions_are_allowed_by_the_database():
    cats = set(
        re.findall(
            r"'(\w+)'",
            re.search(r"category\s+text not null check \(category in\s*\((.*?)\)\)", SQL, re.S).group(1),
        )
    )
    chips = re.findall(r"\['(?:blocked|lift|wrong|other)', '[^']+', '(\w+)', '\w+'\]", FORM_JS)
    assert len(chips) == 4 and set(chips) <= cats
    profiles = set(
        re.findall(
            r"'(\w+)'",
            re.search(r"profile\s+text\s+check \(profile in\s*\((.*?)\)\)", RATINGS_SQL, re.S).group(1),
        )
    )
    who = set(
        re.findall(r"\['(\w+)', '[^']+'\](?:,|\];)", FORM_JS.split("const WHO = ")[1].split("];")[0] + "];")
    )
    assert who == profiles
    regions = set(re.findall(r"'(\w+)'", re.search(r"check \(region in \((.*?)\)\)", RATINGS_SQL).group(1)))
    assert set(re.findall(r"'(\w+)'", FORM_JS.split("const RATING_REGIONS = [")[1].split("]")[0])) == regions


def test_form_limits_match_the_database():
    assert "char_length(comment) <= 500" in RATINGS_SQL and "R.stars > 0 ? 500 : 1000" in FORM_JS
    assert (
        "between 1 and 5" in RATINGS_SQL
        and "R.parts[k] === v" in FORM_JS
        and 'data-v="5"' in FORM_JS
        and 'data-v="1"' in FORM_JS
    )
    assert (
        ">= 40" in RATINGS_SQL and ">= 10" in SQL and ">= 200" in SQL
    )  # the three limit messages in the form quote these
    for words in ("You rated 40 places today", "You sent 10 problems today", "very busy right now"):
        assert words in FORM_JS
    assert "octet_length(v_photo) > 250000" in SQL and "blob.size <= 200000" in FORM_JS
    assert "'-01'" in FORM_JS  # the visit month is the first day of the month
