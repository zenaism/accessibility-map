"""Dates in words ("tonight", "this weekend", "next Saturday", "this month") with an injected today.

The browser port (src/atlas/web/assistant/dates.js) must give the same answers; golden tests check it.
Conventions (documented so the answer can always show the resolved dates):
  weekend        Saturday and Sunday (from today on if today is already in the weekend)
  next weekend   the Saturday and Sunday after this weekend
  this week      today to Sunday; next week = Monday to Sunday of the following week
  next <day>     that weekday in the following calendar week (Monday to Sunday)
  <day>          the next one from today on (today counts)
  <month>        that month (this year, or next year when the month has passed)
"""

from __future__ import annotations

import re
from datetime import date, timedelta

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MONTHS = [
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
]
DEFAULT_DAYS = 30


def _iso(d: date) -> str:
    return d.isoformat()


def _last_of_month(y: int, m: int) -> date:
    return (date(y + (m == 12), m % 12 + 1, 1)) - timedelta(days=1)


def _span(label: str, a: date, b: date) -> dict:
    return {"label": label, "start": _iso(a), "end": _iso(b)}


def parse_when(text: str, today: str) -> dict | None:
    """The date range a question asks about, or None when it names no date."""
    t = " " + re.sub(r"[^a-z0-9' ]+", " ", text.lower().replace("’", "'")) + " "
    t = re.sub(r"\s+", " ", t)
    d0 = date.fromisoformat(today)
    wd = d0.weekday()
    next_monday = d0 + timedelta(days=7 - wd)

    def has(p: str) -> bool:
        return f" {p} " in t

    if has("tonight"):
        return _span("tonight", d0, d0)
    if has("today"):
        return _span("today", d0, d0)
    if has("tomorrow"):
        return _span("tomorrow", d0 + timedelta(days=1), d0 + timedelta(days=1))
    if has("next weekend"):
        sat = next_monday + timedelta(days=5)
        return _span("next weekend", sat, sat + timedelta(days=1))
    if has("this weekend") or has("the weekend") or has("weekend"):
        if wd <= 4:
            sat = d0 + timedelta(days=5 - wd)
            return _span("this weekend", sat, sat + timedelta(days=1))
        return _span("this weekend", d0, d0 + timedelta(days=6 - wd))
    if has("next week"):
        return _span("next week", next_monday, next_monday + timedelta(days=6))
    if has("this week"):
        return _span("this week", d0, d0 + timedelta(days=6 - wd))
    for i, name in enumerate(WEEKDAYS):
        if has(f"next {name}"):
            day = next_monday + timedelta(days=i)
            return _span(f"next {name.title()}", day, day)
    for i, name in enumerate(WEEKDAYS):
        if has(name) or has(name + "s"):
            day = d0 + timedelta(days=(i - wd) % 7)
            return _span(name.title(), day, day)
    if has("next month"):
        y, m = (d0.year + (d0.month == 12), d0.month % 12 + 1)
        return _span("next month", date(y, m, 1), _last_of_month(y, m))
    if has("this month"):
        return _span("this month", d0, _last_of_month(d0.year, d0.month))
    if has("this year"):
        return _span("this year", d0, date(d0.year, 12, 31))
    for i, name in enumerate(MONTHS):
        if has(name) or (name != "may" and has(name[:3])) or (name == "may" and has("in may")):
            y = d0.year + (i + 1 < d0.month)
            first = date(y, i + 1, 1)
            return _span(
                name.title(),
                max(first, d0) if y == d0.year and i + 1 == d0.month else first,
                _last_of_month(y, i + 1),
            )
    return None


def default_range(today: str) -> dict:
    d0 = date.fromisoformat(today)
    return _span(f"the next {DEFAULT_DAYS} days", d0, d0 + timedelta(days=DEFAULT_DAYS))


def day_text(iso: str) -> str:
    """Saturday 28 November"""
    d = date.fromisoformat(iso[:10])
    return f"{WEEKDAYS[d.weekday()].title()} {d.day} {MONTHS[d.month - 1].title()}"


def short_day(iso: str) -> str:
    """28 Nov"""
    d = date.fromisoformat(iso[:10])
    return f"{d.day} {MONTHS[d.month - 1][:3].title()}"


def time_text(iso: str) -> str:
    """2:00 pm (empty when the record has no time or a suspicious one between midnight and 6 am)"""
    if len(iso) < 16:
        return ""
    h, m = int(iso[11:13]), iso[14:16]
    if h < 6:  # the source has a clutch of 00:00 to 05:59 starts that look like UTC; show no time
        return ""
    return f"{(h % 12) or 12}:{m} {'am' if h < 12 else 'pm'}"


def when_text(iso: str) -> str:
    t = time_text(iso)
    return f"{day_text(iso)}, {t}" if t else day_text(iso)


def range_text(w: dict) -> str:
    a, b = w["start"], w["end"]
    return day_text(a) if a == b else f"{day_text(a)} to {day_text(b)}"
