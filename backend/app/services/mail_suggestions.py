"""Terminvorschläge aus Mails: Kalendereinladungen (ICS) und Datumsangaben im Text.

Ein Vorschlag landet nie von selbst im Kalender – er wartet an der Mail auf Bestätigung
(„In Kalender übernehmen“ oder „Verwerfen“). Vergangene Termine werden nicht vorgeschlagen.

Im Text zählt eine Mail nur, wenn Betreff oder Zeile nach einem Termin klingen („Termin“,
„Meeting“, „Einladung“, „appointment“ …) und die Schnellerfassung darin Datum *und* Uhrzeit
findet. Zitierte Zeilen („> …“, „Am … schrieb …:“) werden übersprungen.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.quickadd import parse_quick_add
from app.services.external_calendars import FeedError, parse_ics

log = logging.getLogger(__name__)

KEYWORDS = re.compile(
    r"(?i)(?<!\w)(?:termin\w*|meeting|besprechung|verabredung|einladung|treffen|gespräch|"
    r"interview|webinar|call|appointment|invitation|reservierung|reservation|booking|"
    r"sprechstunde|abholung|übergabe)(?!\w)"
)
REPLY_PREFIX = re.compile(r"(?i)^\s*(?:(?:re|aw|wg|fw|fwd|antw)\s*:\s*)+")
QUOTED = re.compile(r"(?i)^\s*>|(?<!\w)(?:schrieb|wrote)(?!\w).*:\s*$")
CANCEL = re.compile(rb"(?im)^METHOD:\s*CANCEL")
MAX_LINES = 40
MAX_LINE = 300
DURATION = timedelta(hours=1)
HORIZON = timedelta(days=365)


@dataclass
class Suggestion:
    source: str  # „invite“ (Kalendereinladung) oder „text“
    title: str
    start: datetime
    end: datetime
    all_day: bool
    location: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "title": self.title,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "all_day": self.all_day,
            "location": self.location,
        }


def clean_subject(subject: str) -> str:
    return REPLY_PREFIX.sub("", subject).strip()


def from_invites(invites: list[bytes], tzid: str) -> Suggestion | None:
    for data in invites:
        if CANCEL.search(data):
            continue
        try:
            events = parse_ics(data, tzid)
        except FeedError:
            continue
        for event in events:
            if event.status != "cancelled":
                return Suggestion(
                    "invite",
                    event.title[:300],
                    event.start_at,
                    event.end_at,
                    event.all_day,
                    event.location[:500],
                )
    return None


def from_text(
    subject: str, body: str, sent_at: datetime | None, tzid: str, now: datetime
) -> Suggestion | None:
    zone = ZoneInfo(tzid)
    base = (sent_at or now).astimezone(zone).replace(tzinfo=None)
    topic = clean_subject(subject)
    lines = [
        line.strip() for line in body.split("\n")[:400] if line.strip() and not QUOTED.search(line)
    ]
    if KEYWORDS.search(topic):
        candidates = lines[:MAX_LINES]
    else:
        candidates = [line for line in lines if KEYWORDS.search(line)][:MAX_LINES]
        if not candidates:
            return None
    for index, line in enumerate([topic, *candidates]):
        parsed = parse_quick_add(line[:MAX_LINE], base)
        if parsed.due_date is None or parsed.due_time is None:
            continue
        local = datetime.combine(parsed.due_date, parsed.due_time)
        if not base - timedelta(days=1) <= local <= base + HORIZON:
            continue
        start = local.replace(tzinfo=zone).astimezone(UTC)
        title = parsed.title if index == 0 else (topic or parsed.title)
        return Suggestion("text", (title or "–")[:300], start, start + DURATION, False)
    return None


def detect(
    invites: list[bytes],
    subject: str,
    body: str,
    sent_at: datetime | None,
    tzid: str,
    now: datetime | None = None,
) -> Suggestion | None:
    """Einladung vor Text; nichts, was schon vorbei ist. Fehler verhindern nie den Abgleich."""
    now = now or datetime.now(UTC)
    try:
        found = from_invites(invites, tzid) or from_text(subject, body, sent_at, tzid, now)
    except Exception:
        log.warning("Terminerkennung fehlgeschlagen", exc_info=True)
        return None
    if found is None or found.end < now:
        return None
    return found
