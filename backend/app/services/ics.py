"""Termine als iCalendar (RFC 5545) ausgeben – für ICS-Abos in Apple, Google, Outlook & Co."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from icalendar import Calendar, vRecur
from icalendar import Event as VEvent

from app.models import Event

BUSY_TITLE = "Belegt"


def _moment(event: Event, instant: datetime) -> date | datetime:
    """Ganztägig als Datum, sonst in der Zeitzone des Termins (mit VTIMEZONE)."""
    return instant.date() if event.all_day else instant.astimezone(ZoneInfo(event.tzid))


def build_calendar(
    events: Iterable[Event], *, name: str, detail: str, busy_title: str = BUSY_TITLE
) -> bytes:
    """Stabile Ausgabe: gleiche Termine ergeben gleiche Bytes (wichtig für ETag-Caching).

    ``detail``: ``full`` alles, ``public`` ohne Beschreibung und Tags (zum Weitergeben an
    Gesprächspartner – interne Notizen bleiben intern), ``title`` nur Titel, ``busy`` nur „Belegt“.
    """
    calendar = Calendar()
    calendar.add("prodid", "-//Todoch//Todoch//DE")
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")
    calendar.add("method", "PUBLISH")
    calendar.add("x-wr-calname", name)
    calendar.add("refresh-interval", timedelta(hours=1), parameters={"VALUE": "DURATION"})
    calendar.add("x-published-ttl", "PT1H")

    for event in sorted(events, key=lambda e: (e.uid, e.recurrence_id is not None, e.start_at)):
        item = VEvent()
        item.add("uid", event.uid)
        item.add("dtstamp", event.updated_at)
        item.add("sequence", event.sequence)
        item.add("dtstart", _moment(event, event.start_at))
        item.add("dtend", _moment(event, event.end_at))
        if event.recurrence_id is not None:
            item.add("recurrence-id", _moment(event, event.recurrence_id))
        if event.rrule:
            item.add("rrule", vRecur.from_ical(event.rrule))
            if event.exdates:
                item.add("exdate", [_moment(event, d) for d in sorted(event.exdates)])
        if detail == "busy":
            item.add("summary", busy_title)
            item.add("class", "PRIVATE")
        else:
            item.add("summary", event.title)
            if detail in ("full", "public"):
                if event.location:
                    item.add("location", event.location)
                if event.url:
                    item.add("url", event.url)
            if detail == "full":
                if event.description:
                    item.add("description", event.description)
                if event.tags:
                    item.add("categories", list(event.tags))
        item.add("status", event.status.upper())
        item.add("transp", "TRANSPARENT" if event.transparency == "transparent" else "OPAQUE")
        calendar.add_component(item)

    calendar.add_missing_timezones()
    return bytes(calendar.to_ical())
