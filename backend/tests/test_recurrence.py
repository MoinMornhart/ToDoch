from datetime import date

import pytest

from app.services.recurrence import normalize_recurrence, parse_recurrence


def test_normalize() -> None:
    assert normalize_recurrence("rrule:freq=weekly;byday=fr,mo") == "FREQ=WEEKLY;BYDAY=MO,FR"
    assert normalize_recurrence("FREQ=DAILY;INTERVAL=1") == "FREQ=DAILY"
    assert normalize_recurrence("") is None
    assert normalize_recurrence(None) is None


@pytest.mark.parametrize(
    "rule",
    [
        "FREQ=HOURLY",
        "FREQ=DAILY;COUNT=3",
        "FREQ=DAILY;INTERVAL=0",
        "FREQ=DAILY;INTERVAL=abc",
        "FREQ=MONTHLY;BYDAY=MO",
        "FREQ=WEEKLY;BYDAY=XX",
        "FREQ=DAILY;UNTIL=2026-13-01",
        "FREQ=DAILY;FREQ=WEEKLY",
        "INTERVAL=2",
    ],
)
def test_invalid_rules(rule: str) -> None:
    with pytest.raises(ValueError):
        parse_recurrence(rule)


def test_next_weekly_byday() -> None:
    rule = parse_recurrence("FREQ=WEEKLY;BYDAY=MO,TH")
    # Montag 14.09.2026 → Donnerstag 17.09.2026
    assert rule.next_after(date(2026, 9, 14), date(2026, 9, 14)) == date(2026, 9, 17)


def test_next_monthly_interval() -> None:
    rule = parse_recurrence("FREQ=MONTHLY;INTERVAL=2")
    assert rule.next_after(date(2026, 1, 15), date(2026, 1, 15)) == date(2026, 3, 15)


def test_next_never_in_past() -> None:
    rule = parse_recurrence("FREQ=DAILY")
    # Seit einer Woche überfällig → nächste Wiederholung ist heute
    assert rule.next_after(date(2026, 9, 1), date(2026, 9, 11)) == date(2026, 9, 11)


def test_until_ends_series() -> None:
    rule = parse_recurrence("FREQ=WEEKLY;UNTIL=20260920")
    assert rule.next_after(date(2026, 9, 11), date(2026, 9, 11)) == date(2026, 9, 18)
    assert rule.next_after(date(2026, 9, 18), date(2026, 9, 18)) is None


def test_first_on_or_after() -> None:
    rule = parse_recurrence("FREQ=WEEKLY;BYDAY=TU")
    assert rule.first_on_or_after(date(2026, 9, 11)) == date(2026, 9, 15)
