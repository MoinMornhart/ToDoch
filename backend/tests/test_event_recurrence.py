from datetime import UTC, date, datetime

import pytest

from app.services.event_recurrence import (
    RuleError,
    expand_all_day,
    expand_timed,
    first_occurrence,
    normalize_event_rule,
    occurrences_before,
)


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)  # type: ignore[misc]


def test_normalize() -> None:
    assert (
        normalize_event_rule("rrule:freq=weekly;byday=mo,we;interval=1")
        == "FREQ=WEEKLY;BYDAY=MO,WE"
    )
    assert (
        normalize_event_rule("FREQ=MONTHLY;BYDAY=-1FR;COUNT=5") == "FREQ=MONTHLY;BYDAY=-1FR;COUNT=5"
    )
    assert normalize_event_rule("") is None


@pytest.mark.parametrize(
    "rule",
    [
        "FREQ=HOURLY",
        "FREQ=DAILY;COUNT=3;UNTIL=20260101",
        "FREQ=DAILY;BYSETPOS=1",
        "FREQ=WEEKLY;BYDAY=XY",
        "FREQ=MONTHLY;BYMONTHDAY=32",
        "FREQ=YEARLY;BYMONTH=13",
        "FREQ=DAILY;INTERVAL=0",
        "FREQ=DAILY;UNTIL=morgen",
    ],
)
def test_invalid(rule: str) -> None:
    with pytest.raises(RuleError):
        normalize_event_rule(rule)


def test_weekly_keeps_wall_clock_across_dst() -> None:
    # Montags 9:00 Berlin; am 26.10.2026 gilt wieder Winterzeit (UTC+1).
    start = utc(2026, 10, 19, 7, 0)  # 9:00 Sommerzeit
    found = expand_timed("FREQ=WEEKLY", start, "Europe/Berlin", utc(2026, 10, 1), utc(2026, 11, 1))
    assert found == [utc(2026, 10, 19, 7, 0), utc(2026, 10, 26, 8, 0)]


def test_until_and_count() -> None:
    start = utc(2026, 9, 1, 8, 0)
    assert (
        len(expand_timed("FREQ=DAILY;COUNT=3", start, "UTC", utc(2026, 9, 1), utc(2026, 10, 1)))
        == 3
    )
    until = expand_timed(
        "FREQ=DAILY;UNTIL=20260903T080000Z", start, "UTC", utc(2026, 9, 1), utc(2026, 10, 1)
    )
    assert until[-1] == utc(2026, 9, 3, 8, 0)
    by_date = expand_timed(
        "FREQ=DAILY;UNTIL=20260902", start, "UTC", utc(2026, 9, 1), utc(2026, 10, 1)
    )
    assert len(by_date) == 2


def test_window_is_respected() -> None:
    start = utc(2026, 1, 1, 12, 0)
    found = expand_timed("FREQ=DAILY", start, "UTC", utc(2026, 3, 1), utc(2026, 3, 3))
    assert found == [utc(2026, 3, 1, 12, 0), utc(2026, 3, 2, 12, 0)]


def test_all_day_and_monthly_last_friday() -> None:
    days = expand_all_day(
        "FREQ=MONTHLY;BYDAY=-1FR", date(2026, 9, 25), date(2026, 9, 1), date(2026, 12, 1)
    )
    assert days == [date(2026, 9, 25), date(2026, 10, 30), date(2026, 11, 27)]


def test_helpers() -> None:
    start = utc(2026, 9, 1, 8, 0)
    assert occurrences_before("FREQ=DAILY;COUNT=10", start, "UTC", utc(2026, 9, 4, 8, 0)) == 3
    assert first_occurrence("FREQ=WEEKLY;BYDAY=FR", start, "UTC") == utc(2026, 9, 4, 8, 0)
