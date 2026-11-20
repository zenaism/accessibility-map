# ruff: noqa: E501
"""Dates in words with an injected today."""

import pytest

from atlas.assistant.dates import day_text, parse_when, range_text, time_text, when_text

FRI, SAT, SUN, MON = "2026-11-20", "2026-11-21", "2026-11-22", "2026-11-23"


@pytest.mark.parametrize(
    ("text", "today", "start", "end"),
    [
        ("what's on tonight", FRI, FRI, FRI),
        ("tomorrow", FRI, SAT, SUN[:-2] + "21"),
        ("this weekend", FRI, SAT, SUN),
        ("this weekend", SAT, SAT, SUN),
        ("this weekend", SUN, SUN, SUN),  # the weekend is half over
        ("next weekend", FRI, "2026-11-28", "2026-11-29"),
        ("this week", FRI, FRI, SUN),
        ("next week", FRI, MON, "2026-11-29"),
        ("next Saturday", FRI, "2026-11-28", "2026-11-28"),
        ("on Friday", FRI, FRI, FRI),  # today counts for a bare weekday
        ("on Friday", SAT, "2026-11-27", "2026-11-27"),
        ("this month", FRI, FRI, "2026-11-30"),
        ("next month", "2026-12-15", "2027-01-01", "2027-01-31"),
        ("in December", FRI, "2026-12-01", "2026-12-31"),
        ("in January", "2026-12-15", "2027-01-01", "2027-01-31"),  # month already past this year: next year
        ("this year", FRI, FRI, "2026-12-31"),
    ],
)
def test_parse_when(text, today, start, end):
    w = parse_when(text, today)
    assert (w["start"], w["end"]) == (start, end)


def test_no_date_words_gives_none():
    assert parse_when("where is the library", FRI) is None
    assert parse_when("may I park here", FRI) is None  # the word "may" is not the month


def test_day_and_time_text():
    assert day_text("2026-11-28T14:00") == "Saturday 28 November"
    assert time_text("2026-11-28T14:00") == "2:00 pm"
    assert time_text("2026-11-28T00:30") == ""  # suspicious early-morning starts are not shown
    assert time_text("2026-11-28") == ""
    assert when_text("2026-11-28T19:30") == "Saturday 28 November, 7:30 pm"
    assert range_text({"start": FRI, "end": SUN}) == "Friday 20 November to Sunday 22 November"
