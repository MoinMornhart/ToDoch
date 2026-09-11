"""Schnellerfassung auf Englisch – dieselbe Zeile, dieselben Regeln wie auf Deutsch."""

from datetime import date, datetime, time

import pytest

from app.quickadd import parse_quick_add

# Friday, 11 September 2026, 10:00
NOW = datetime(2026, 9, 11, 10, 0)


def parse(text: str):  # type: ignore[no-untyped-def]
    return parse_quick_add(text, NOW)


def test_full_example() -> None:
    r = parse("Pay bill tomorrow 2pm !high #finance @work")
    assert r.title == "Pay bill"
    assert r.due_date == date(2026, 9, 12)
    assert r.due_time == time(14, 0)
    assert r.priority == 3
    assert r.tags == ["finance"]
    assert r.area == "work"


@pytest.mark.parametrize(
    ("text", "title", "due", "at"),
    [
        ("Call dentist on Monday at 9", "Call dentist", date(2026, 9, 14), time(9)),
        ("Dinner tonight", "Dinner", date(2026, 9, 11), time(19)),
        ("Groceries tomorrow evening", "Groceries", date(2026, 9, 12), time(19)),
        ("Status report next week", "Status report", date(2026, 9, 14), None),
        ("File tax return by October 31", "File tax return", date(2026, 10, 31), None),
        ("Party on 3rd October 8:30pm", "Party", date(2026, 10, 3), time(20, 30)),
        ("Conference Oct 3rd, 2027 9:15am", "Conference", date(2027, 10, 3), time(9, 15)),
        ("Book flight in 2 weeks", "Book flight", date(2026, 9, 25), None),
        ("Renew passport in a month", "Renew passport", date(2026, 10, 11), None),
        ("Invoice end of the month", "Invoice", date(2026, 9, 30), None),
        ("Plan trip the day after tomorrow", "Plan trip", date(2026, 9, 13), None),
        ("Lunch at noon", "Lunch", date(2026, 9, 11), time(12)),
        ("Clean up this weekend", "Clean up", date(2026, 9, 12), None),
        ("Review next Thursday", "Review", date(2026, 9, 17), None),
        ("Standup 12am", "Standup", date(2026, 9, 12), time(0)),
    ],
)
def test_dates_and_times(text: str, title: str, due: date, at: time | None) -> None:
    r = parse(text)
    assert (r.title, r.due_date, r.due_time) == (title, due, at)


@pytest.mark.parametrize(
    ("text", "title", "parts", "due"),
    [
        (
            "Gym every Monday and Thursday 18:00",
            "Gym",
            ["FREQ=WEEKLY", "MO", "TH"],
            date(2026, 9, 14),
        ),
        (
            "Water plants every 3 days",
            "Water plants",
            ["FREQ=DAILY", "INTERVAL=3"],
            date(2026, 9, 11),
        ),
        ("Standup weekdays 9:15am", "Standup", ["FREQ=WEEKLY", "MO", "FR"], date(2026, 9, 14)),
        ("Bins every other week", "Bins", ["FREQ=WEEKLY", "INTERVAL=2"], date(2026, 9, 11)),
        ("Rent monthly", "Rent", ["FREQ=MONTHLY"], date(2026, 9, 11)),
        ("Yoga mondays", "Yoga", ["FREQ=WEEKLY", "MO"], date(2026, 9, 14)),
    ],
)
def test_recurrence(text: str, title: str, parts: list[str], due: date) -> None:
    r = parse(text)
    assert r.title == title
    assert r.recurrence is not None
    assert all(part in r.recurrence for part in parts), r.recurrence
    assert r.due_date == due


@pytest.mark.parametrize(("text", "priority"), [("Fix bug !urgent", 3), ("Tidy !low", 1)])
def test_priority(text: str, priority: int) -> None:
    assert parse(text).priority == priority


def test_english_words_inside_titles_stay() -> None:
    # „may“ ohne Tag, „march“ als Verb – kein Datum
    assert parse("We may march ahead").title == "We may march ahead"
    assert parse("We may march ahead").due_date is None


def test_mixed_languages() -> None:
    r = parse("Meeting morgen 3pm @arbeit")
    assert (r.title, r.due_date, r.due_time, r.area) == (
        "Meeting",
        date(2026, 9, 12),
        time(15),
        "arbeit",
    )
