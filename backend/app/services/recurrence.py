"""Wiederholungen als RRULE-Untermenge: FREQ, INTERVAL, BYDAY, UNTIL."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal

from dateutil import rrule

FREQUENCIES: dict[str, Literal[0, 1, 2, 3, 4, 5, 6]] = {
    "DAILY": rrule.DAILY,
    "WEEKLY": rrule.WEEKLY,
    "MONTHLY": rrule.MONTHLY,
    "YEARLY": rrule.YEARLY,
}
WEEKDAYS = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
_WEEKDAY_OBJECTS = (rrule.MO, rrule.TU, rrule.WE, rrule.TH, rrule.FR, rrule.SA, rrule.SU)


@dataclass(frozen=True)
class Recurrence:
    freq: str
    interval: int = 1
    byday: tuple[str, ...] = ()
    until: date | None = None

    def to_rrule(self) -> str:
        parts = [f"FREQ={self.freq}"]
        if self.interval > 1:
            parts.append(f"INTERVAL={self.interval}")
        if self.byday:
            parts.append("BYDAY=" + ",".join(self.byday))
        if self.until:
            parts.append("UNTIL=" + self.until.strftime("%Y%m%d"))
        return ";".join(parts)

    def _rule(self, start: date) -> rrule.rrule:
        return rrule.rrule(
            FREQUENCIES[self.freq],
            dtstart=datetime.combine(start, time()),
            interval=self.interval,
            byweekday=[_WEEKDAY_OBJECTS[WEEKDAYS.index(d)] for d in self.byday] or None,
            until=datetime.combine(self.until, time()) if self.until else None,
        )

    def first_on_or_after(self, start: date) -> date | None:
        first = next(iter(self._rule(start)), None)
        return first.date() if first else None

    def next_after(self, current: date, today: date) -> date | None:
        """Nächster Termin nach ``current``, aber nie in der Vergangenheit."""
        threshold = max(current, today - timedelta(days=1))
        following = self._rule(current).after(datetime.combine(threshold, time()), inc=False)
        return following.date() if following else None


def parse_recurrence(text: str) -> Recurrence:
    fields: dict[str, str] = {}
    for part in text.strip().upper().removeprefix("RRULE:").split(";"):
        if not part:
            continue
        key, sep, value = part.partition("=")
        if not sep or key in fields:
            raise ValueError("Ungültige Wiederholung")
        fields[key] = value
    unknown = set(fields) - {"FREQ", "INTERVAL", "BYDAY", "UNTIL"}
    if unknown:
        raise ValueError("Nicht unterstützte Wiederholungsregel: " + ", ".join(sorted(unknown)))
    freq = fields.get("FREQ", "")
    if freq not in FREQUENCIES:
        raise ValueError("Wiederholung braucht FREQ=DAILY|WEEKLY|MONTHLY|YEARLY")
    interval_text = fields.get("INTERVAL", "1")
    if not interval_text.isdigit() or not 1 <= int(interval_text) <= 365:
        raise ValueError("INTERVAL muss zwischen 1 und 365 liegen")
    byday: tuple[str, ...] = ()
    if "BYDAY" in fields:
        if freq != "WEEKLY":
            raise ValueError("BYDAY ist nur bei wöchentlicher Wiederholung erlaubt")
        days = fields["BYDAY"].split(",")
        if not days or any(d not in WEEKDAYS for d in days):
            raise ValueError("BYDAY enthält ungültige Wochentage")
        byday = tuple(d for d in WEEKDAYS if d in days)
    until: date | None = None
    if "UNTIL" in fields:
        try:
            until = datetime.strptime(fields["UNTIL"][:8], "%Y%m%d").date()
        except ValueError as exc:
            raise ValueError("UNTIL muss ein Datum im Format JJJJMMTT sein") from exc
    return Recurrence(freq=freq, interval=int(interval_text), byday=byday, until=until)


def normalize_recurrence(text: str | None) -> str | None:
    if text is None or not text.strip():
        return None
    return parse_recurrence(text).to_rrule()
