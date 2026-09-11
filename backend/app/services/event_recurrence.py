"""Wiederholungsregeln für Termine (RRULE-Teilmenge nach RFC 5545) und ihre Expansion.

Unterstützt: FREQ, INTERVAL, BYDAY (auch „1MO“, „-1FR“), BYMONTHDAY, BYMONTH, COUNT, UNTIL, WKST.
Expandiert wird in der Wanduhrzeit der Termin-Zeitzone – ein Termin um 9:00 bleibt auch nach
dem Wechsel auf Sommer- oder Winterzeit um 9:00.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, time, timedelta
from itertools import islice
from zoneinfo import ZoneInfo

from dateutil import rrule

FREQUENCIES = ("DAILY", "WEEKLY", "MONTHLY", "YEARLY")
WEEKDAYS = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
KEY_ORDER = ("FREQ", "INTERVAL", "BYDAY", "BYMONTHDAY", "BYMONTH", "COUNT", "UNTIL", "WKST")
MAX_OCCURRENCES = 1000

_BYDAY = re.compile(r"^([+-]?[1-5])?(MO|TU|WE|TH|FR|SA|SU)$")
_UNTIL = re.compile(r"^\d{8}(T\d{6}Z?)?$")


class RuleError(ValueError):
    pass


def _parse(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for part in text.strip().upper().removeprefix("RRULE:").split(";"):
        if not part:
            continue
        key, sep, value = part.partition("=")
        if not sep or not value or key in fields:
            raise RuleError("Ungültige Wiederholungsregel")
        fields[key] = value
    return fields


def normalize_event_rule(text: str | None) -> str | None:
    """Prüft eine Regel und gibt sie in fester Schreibweise zurück."""
    if text is None or not text.strip():
        return None
    fields = _parse(text)
    unknown = set(fields) - set(KEY_ORDER)
    if unknown:
        raise RuleError("Nicht unterstützt: " + ", ".join(sorted(unknown)))
    if fields.get("FREQ") not in FREQUENCIES:
        raise RuleError("FREQ muss DAILY, WEEKLY, MONTHLY oder YEARLY sein")
    if "INTERVAL" in fields:
        if not fields["INTERVAL"].isdigit() or not 1 <= int(fields["INTERVAL"]) <= 999:
            raise RuleError("INTERVAL muss zwischen 1 und 999 liegen")
        if fields["INTERVAL"] == "1":
            del fields["INTERVAL"]
    if "BYDAY" in fields:
        days = fields["BYDAY"].split(",")
        if not all(_BYDAY.match(d) for d in days):
            raise RuleError("BYDAY enthält ungültige Tage")
    if "BYMONTHDAY" in fields:
        for value in fields["BYMONTHDAY"].split(","):
            if not re.fullmatch(r"-?\d{1,2}", value) or not 1 <= abs(int(value)) <= 31:
                raise RuleError("BYMONTHDAY muss zwischen 1 und 31 liegen")
    if "BYMONTH" in fields:
        for value in fields["BYMONTH"].split(","):
            if not value.isdigit() or not 1 <= int(value) <= 12:
                raise RuleError("BYMONTH muss zwischen 1 und 12 liegen")
    if "COUNT" in fields and (
        not fields["COUNT"].isdigit() or not 1 <= int(fields["COUNT"]) <= 1000
    ):
        raise RuleError("COUNT muss zwischen 1 und 1000 liegen")
    if "UNTIL" in fields and not _UNTIL.match(fields["UNTIL"]):
        raise RuleError("UNTIL muss JJJJMMTT oder JJJJMMTTTHHMMSSZ sein")
    if "COUNT" in fields and "UNTIL" in fields:
        raise RuleError("COUNT und UNTIL schließen sich aus")
    if "WKST" in fields and fields["WKST"] not in WEEKDAYS:
        raise RuleError("WKST ist ungültig")
    return ";".join(f"{key}={fields[key]}" for key in KEY_ORDER if key in fields)


def rule_fields(rule: str) -> dict[str, str]:
    return _parse(rule)


def build_rule(fields: dict[str, str]) -> str:
    return ";".join(f"{key}={fields[key]}" for key in KEY_ORDER if key in fields)


def _until_local(value: str, tz: ZoneInfo | None) -> datetime:
    if len(value) == 8:
        return datetime.combine(datetime.strptime(value, "%Y%m%d").date(), time(23, 59, 59))
    parsed = datetime.strptime(value[:15], "%Y%m%dT%H%M%S")
    if value.endswith("Z") and tz is not None:
        return parsed.replace(tzinfo=UTC).astimezone(tz).replace(tzinfo=None)
    return parsed


def _rule(rule: str, dtstart: datetime, tz: ZoneInfo | None) -> rrule.rrule:
    fields = _parse(rule)
    until = fields.pop("UNTIL", None)
    parsed = rrule.rrulestr("RRULE:" + build_rule(fields), dtstart=dtstart)
    assert isinstance(parsed, rrule.rrule)
    if until:
        parsed = parsed.replace(until=_until_local(until, tz))
    return parsed


def to_utc(local: datetime, tzid: str) -> datetime:
    return local.replace(tzinfo=ZoneInfo(tzid)).astimezone(UTC)


def to_local(instant: datetime, tzid: str) -> datetime:
    return instant.astimezone(ZoneInfo(tzid)).replace(tzinfo=None)


def expand_timed(
    rule: str, start: datetime, tzid: str, window_start: datetime, window_end: datetime
) -> list[datetime]:
    """Beginn-Zeitpunkte (UTC) aller Vorkommen mit Beginn in [window_start, window_end)."""
    tz = ZoneInfo(tzid)
    dtstart = to_local(start, tzid)
    series = _rule(rule, dtstart, tz)
    lo = to_local(window_start, tzid) - timedelta(hours=26)  # Puffer für Zeitumstellungen
    hi = to_local(window_end, tzid) + timedelta(hours=26)
    result = []
    for local in islice(series.xafter(lo, inc=True), MAX_OCCURRENCES):
        if local > hi:
            break
        instant = local.replace(tzinfo=tz).astimezone(UTC)
        if window_start <= instant < window_end:
            result.append(instant)
    return result


def expand_all_day(rule: str, start: date, window_start: date, window_end: date) -> list[date]:
    """Tage aller ganztägigen Vorkommen in [window_start, window_end)."""
    series = _rule(rule, datetime.combine(start, time()), None)
    result = []
    for occurrence in islice(
        series.xafter(datetime.combine(window_start, time()), inc=True), MAX_OCCURRENCES
    ):
        if occurrence.date() >= window_end:
            break
        result.append(occurrence.date())
    return result


def occurrences_before(rule: str, start: datetime, tzid: str | None, before: datetime) -> int:
    """Anzahl der Vorkommen mit Beginn vor ``before`` (für das Aufteilen von COUNT-Serien)."""
    tz = ZoneInfo(tzid) if tzid else None
    local_start = to_local(start, tzid) if tzid else start.replace(tzinfo=None)
    local_before = to_local(before, tzid) if tzid else before.replace(tzinfo=None)
    series = _rule(rule, local_start, tz)
    return len(series.between(local_start, local_before - timedelta(microseconds=1), inc=True))


def first_occurrence(rule: str, start: datetime, tzid: str | None) -> datetime | None:
    """Ersten Beginn der Serie (UTC) oder None, wenn die Regel nichts ergibt."""
    tz = ZoneInfo(tzid) if tzid else None
    local = to_local(start, tzid) if tzid else start.replace(tzinfo=None)
    first = next(iter(_rule(rule, local, tz)), None)
    if first is None:
        return None
    return first.replace(tzinfo=tz or UTC).astimezone(UTC)
