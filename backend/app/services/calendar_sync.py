"""Zwei-Wege-Abgleich mit Online-Kalendern: Google Kalender und Outlook (Microsoft 365, Hotmail).

Verbinden: „Google Kalender verbinden“ bzw. „Outlook-Kalender verbinden“ im Bereich – OAuth wie
beim Postfach (dieselbe Rücksprungadresse), aber nur mit dem Recht auf Termine. Jede Verbindung
gehört zu einem Bereich: Termine dieses Bereichs gehen zum Anbieter, Termine von dort landen in
diesem Bereich.

Abgleich (Worker alle 5 Minuten oder auf Knopfdruck):

1. Holen – Google liefert nur Änderungen seit dem letzten Mal (``syncToken``), Microsoft jedes Mal
   die vollständige Liste (was darin fehlt, wurde dort gelöscht). Übernommen wird ein Termin nur,
   wenn er sich beim Anbieter seit dem letzten Abgleich geändert hat – so gehen Änderungen in
   ToDoch nicht verloren. Beim ersten Mal nur Serien und Termine der letzten 90 Tage und der
   Zukunft.
2. Senden – neue und geänderte Termine des Bereichs (erkannt am Fingerabdruck der Inhalte), in
   ToDoch gelöschte Termine (Grabsteine) und Termine, die in einen anderen Bereich wanderten.

Wurde ein Termin auf beiden Seiten geändert, gewinnt der Anbieter. Einzelne geänderte Vorkommen
einer Serie werden nicht abgeglichen, bei Outlook außerdem keine gelöschten Vorkommen.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from typing import Any, Protocol
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import CalendarConnection, CalendarTombstone, Event, User
from app.security.crypto import Crypto, DecryptionError
from app.services import mail_oauth as oauth
from app.services.event_recurrence import WEEKDAYS, RuleError, normalize_event_rule, rule_fields
from app.services.events import midnight_utc
from app.services.mail import html_to_text

log = logging.getLogger(__name__)

GOOGLE_API = "https://www.googleapis.com/calendar/v3"
GRAPH_ROOT = "https://graph.microsoft.com/"
GRAPH_EVENTS = "https://graph.microsoft.com/v1.0/me/calendar/events"
SCOPES = {
    "google": "openid email https://www.googleapis.com/auth/calendar.events",
    "microsoft": "openid email offline_access https://graph.microsoft.com/Calendars.ReadWrite",
}
TIMEOUT = httpx.Timeout(20.0, connect=10.0)
# Tests setzen hier einen Nachbau von Google Kalender bzw. Outlook ein
TRANSPORT: httpx.AsyncBaseTransport | None = None
MAX_PAGES = 20
GRAPH_PAGES = 50
MAX_PUSH = 200
PAST_DAYS = 90

UNREACHABLE = "Google Kalender ist nicht erreichbar."
REJECTED = "Google Kalender hat die Anmeldung abgelehnt. Bitte neu verbinden."
OUTLOOK_UNREACHABLE = "Der Outlook-Kalender ist nicht erreichbar."
OUTLOOK_REJECTED = "Der Outlook-Kalender hat die Anmeldung abgelehnt. Bitte neu verbinden."
TOO_MANY = "Der Kalender enthält zu viele Termine (höchstens 5000)."

GRAPH_DAYS = dict(
    zip(
        WEEKDAYS,
        ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"),
        strict=True,
    )
)
DAY_CODES = {name: code for code, name in GRAPH_DAYS.items()}
GRAPH_INDEX = {
    "1": "first",
    "+1": "first",
    "2": "second",
    "3": "third",
    "4": "fourth",
    "-1": "last",
}
INDEX_CODES = {"first": "1", "second": "2", "third": "3", "fourth": "4", "last": "-1"}


class SyncError(Exception):
    """Verständliche Fehlermeldung (Deutsch; übersetzt in app/i18n.py)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class _Gone(Exception):
    """Der syncToken ist abgelaufen – alles neu holen."""


@dataclass
class RemoteItem:
    remote_id: str
    fields: dict[str, Any] | None = None  # None: unlesbar – überspringen
    deleted: bool = False
    instance_of: str | None = None  # abgesagtes Vorkommen dieser Serie
    original_start: datetime | None = None


@dataclass
class Changes:
    items: list[RemoteItem]
    token: str | None
    complete: bool = False  # vollständige Liste: was fehlt, wurde beim Anbieter gelöscht


class CalendarClient(Protocol):
    unreachable: str
    exdates: bool  # kann der Anbieter Ausnahmen einer Serie übernehmen?

    async def changes(self, sync_token: str | None) -> Changes: ...

    async def insert(self, event: Event) -> str: ...

    async def update(self, remote_id: str, event: Event) -> bool: ...

    async def delete(self, remote_id: str) -> None: ...


def token_context(connection_id: object) -> str:
    return f"calendar_connection:{connection_id}:token"


def calendar_provider(settings: Settings, name: str) -> oauth.Provider | None:
    """Wie der Anbieter fürs Postfach, aber nur mit dem Recht auf Termine."""
    base = oauth.provider(settings, name)
    if base is None or name not in SCOPES:
        return None
    return replace(base, scope=SCOPES[name])


# --- Fingerabdruck ------------------------------------------------------------------------


def _digest(values: dict[str, Any], exdates: bool) -> str:
    parts = [
        str(values["title"]),
        str(values.get("description") or ""),
        str(values.get("location") or ""),
        values["start_at"].astimezone(UTC).isoformat(),
        values["end_at"].astimezone(UTC).isoformat(),
        str(values["all_day"]),
        str(values["tzid"]),
        str(values.get("rrule") or ""),
        ",".join(sorted(d.astimezone(UTC).isoformat() for d in values.get("exdates") or []))
        if exdates
        else "",
        str(values["status"]),
        str(values["transparency"]),
    ]
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def fingerprint(event: Event, exdates: bool = True) -> str:
    """Fingerabdruck der abgeglichenen Inhalte – ändert er sich, muss der Termin zum Anbieter."""
    values = {
        name: getattr(event, name)
        for name in (
            "title",
            "description",
            "location",
            "start_at",
            "end_at",
            "all_day",
            "tzid",
            "rrule",
            "exdates",
            "status",
            "transparency",
        )
    }
    return _digest(values, exdates)


# --- Google: Umrechnung -------------------------------------------------------------------


def _zone(name: object, fallback: str) -> str:
    if isinstance(name, str) and name:
        try:
            ZoneInfo(name)
            return name
        except (KeyError, ValueError):
            pass
    return fallback


def _moment(value: dict[str, Any], tzid: str) -> tuple[datetime, bool]:
    if "date" in value:
        return midnight_utc(date.fromisoformat(value["date"])), True
    moment = datetime.fromisoformat(str(value["dateTime"]).replace("Z", "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=ZoneInfo(tzid))
    return moment.astimezone(UTC), False


def _ical_moment(raw: str, zone: str) -> datetime | None:
    try:
        if len(raw) == 8:
            return midnight_utc(datetime.strptime(raw, "%Y%m%d").date())
        if raw.endswith("Z"):
            return datetime.strptime(raw, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        local = datetime.strptime(raw, "%Y%m%dT%H%M%S").replace(tzinfo=ZoneInfo(zone))
        return local.astimezone(UTC)
    except (ValueError, KeyError):
        return None


def _recurrence(lines: list[Any], tzid: str) -> tuple[str | None, list[datetime]]:
    rule: str | None = None
    exdates: set[datetime] = set()
    for line in lines:
        if not isinstance(line, str):
            continue
        head, _, values = line.partition(":")
        kind, *params = head.split(";")
        if kind.upper() == "RRULE":
            try:
                rule = normalize_event_rule(values)
            except (RuleError, ValueError):
                rule = None  # unbekannte Regel: nur das erste Vorkommen
        elif kind.upper() == "EXDATE":
            options = dict(p.split("=", 1) for p in params if "=" in p)
            zone = _zone(options.get("TZID"), tzid)
            for raw in values.split(","):
                parsed = _ical_moment(raw.strip(), zone)
                if parsed is not None:
                    exdates.add(parsed)
    return rule, sorted(exdates)


def fields_from_google(item: dict[str, Any], fallback_tz: str) -> dict[str, Any]:
    start_info = item["start"]
    tzid = _zone(start_info.get("timeZone"), fallback_tz)
    start, all_day = _moment(start_info, tzid)
    end, _ = _moment(item.get("end") or start_info, tzid)
    rule, exdates = _recurrence(item.get("recurrence") or [], tzid)
    return {
        "title": str(item.get("summary") or "–")[:300],
        "description": str(item.get("description") or "")[:50_000],
        "location": str(item.get("location") or "")[:500],
        "start_at": start,
        "end_at": max(end, start),
        "all_day": all_day,
        "tzid": tzid,
        "rrule": rule,
        "exdates": exdates if rule else [],
        "status": "tentative" if item.get("status") == "tentative" else "confirmed",
        "transparency": "transparent" if item.get("transparency") == "transparent" else "opaque",
    }


def _google_moment(event: Event, instant: datetime) -> dict[str, str]:
    if event.all_day:
        return {"date": instant.astimezone(UTC).date().isoformat()}
    local = instant.astimezone(ZoneInfo(event.tzid)).replace(tzinfo=None)
    return {"dateTime": local.isoformat(timespec="seconds"), "timeZone": event.tzid}


def to_google(event: Event) -> dict[str, Any]:
    recurrence: list[str] = []
    if event.rrule:
        recurrence.append(f"RRULE:{event.rrule}")
        for instant in sorted(event.exdates or []):
            if event.all_day:
                recurrence.append(f"EXDATE;VALUE=DATE:{instant.astimezone(UTC):%Y%m%d}")
            else:
                recurrence.append(f"EXDATE:{instant.astimezone(UTC):%Y%m%dT%H%M%SZ}")
    return {
        "summary": event.title,
        "description": event.description or "",
        "location": event.location or "",
        "start": _google_moment(event, event.start_at),
        "end": _google_moment(event, event.end_at),
        "recurrence": recurrence,
        "status": "tentative" if event.status == "tentative" else "confirmed",
        "transparency": event.transparency,
    }


# --- Microsoft: Umrechnung ----------------------------------------------------------------


def _graph_moment(value: dict[str, Any]) -> datetime:
    moment = datetime.fromisoformat(str(value["dateTime"])[:19])
    zone = str(value.get("timeZone") or "UTC")
    try:
        tz = UTC if zone.upper() == "UTC" else ZoneInfo(zone)
    except (KeyError, ValueError):
        tz = UTC
    return moment.replace(tzinfo=tz).astimezone(UTC)


def _graph_day(instant: datetime) -> datetime:
    """Ganztägig: Mitternacht des Tages – egal in welcher Zeitzone Outlook ihn liefert."""
    return midnight_utc((instant + timedelta(hours=12)).date())


def rrule_from_graph(recurrence: object) -> str | None:
    if not isinstance(recurrence, dict):
        return None
    pattern = recurrence.get("pattern") or {}
    span = recurrence.get("range") or {}
    kind = pattern.get("type")
    days = [DAY_CODES[d] for d in pattern.get("daysOfWeek") or [] if d in DAY_CODES]
    try:
        if kind == "daily":
            parts = ["FREQ=DAILY"]
        elif kind == "weekly":
            parts = ["FREQ=WEEKLY", *([f"BYDAY={','.join(days)}"] if days else [])]
        elif kind in ("absoluteMonthly", "relativeMonthly", "absoluteYearly", "relativeYearly"):
            yearly = kind.endswith("Yearly")
            parts = [f"FREQ={'YEARLY' if yearly else 'MONTHLY'}"]
            if yearly:
                parts.append(f"BYMONTH={int(pattern['month'])}")
            if kind.startswith("relative"):
                if not days:
                    return None
                index = INDEX_CODES.get(str(pattern.get("index") or "first"), "1")
                parts.append(f"BYDAY={index}{days[0]}")
            else:
                parts.append(f"BYMONTHDAY={int(pattern['dayOfMonth'])}")
        else:
            return None
        interval = int(pattern.get("interval") or 1)
        if interval > 1:
            parts.append(f"INTERVAL={interval}")
        if span.get("type") == "numbered":
            parts.append(f"COUNT={int(span['numberOfOccurrences'])}")
        elif span.get("type") == "endDate" and span.get("endDate"):
            parts.append(f"UNTIL={date.fromisoformat(str(span['endDate'])):%Y%m%d}")
        return normalize_event_rule(";".join(parts))
    except (KeyError, ValueError, TypeError, RuleError):
        return None


def graph_recurrence(event: Event) -> dict[str, Any] | None:
    """RRULE → Muster von Outlook; None, wenn Outlook die Regel nicht abbilden kann."""
    if not event.rrule:
        return None
    try:
        fields = rule_fields(event.rrule)
        zone = UTC if event.all_day else ZoneInfo(event.tzid)
        first = event.start_at.astimezone(zone).date()
        freq = fields.get("FREQ")
        byday = [d for d in fields.get("BYDAY", "").split(",") if d]
        pattern: dict[str, Any] = {
            "interval": int(fields.get("INTERVAL", "1")),
            "firstDayOfWeek": "monday",
        }
        if freq == "DAILY":
            pattern["type"] = "daily"
        elif freq == "WEEKLY":
            pattern["type"] = "weekly"
            codes = [d[-2:] for d in byday] or [WEEKDAYS[first.weekday()]]
            pattern["daysOfWeek"] = [GRAPH_DAYS[c] for c in codes]
        elif freq in ("MONTHLY", "YEARLY"):
            yearly = freq == "YEARLY"
            if yearly:
                pattern["month"] = int(fields.get("BYMONTH", str(first.month)))
            ordinal = next((d for d in byday if len(d) > 2), None)
            if ordinal:
                index = GRAPH_INDEX.get(ordinal[:-2])
                if index is None:
                    return None
                pattern |= {
                    "type": "relativeYearly" if yearly else "relativeMonthly",
                    "index": index,
                    "daysOfWeek": [GRAPH_DAYS[ordinal[-2:]]],
                }
            elif byday:
                return None
            else:
                pattern |= {
                    "type": "absoluteYearly" if yearly else "absoluteMonthly",
                    "dayOfMonth": int(fields.get("BYMONTHDAY", str(first.day))),
                }
        else:
            return None
        span: dict[str, Any] = {"startDate": first.isoformat(), "recurrenceTimeZone": event.tzid}
        if "COUNT" in fields:
            span |= {"type": "numbered", "numberOfOccurrences": int(fields["COUNT"])}
        elif "UNTIL" in fields:
            until = fields["UNTIL"]
            end = date(int(until[:4]), int(until[4:6]), int(until[6:8]))
            span |= {"type": "endDate", "endDate": end.isoformat()}
        else:
            span["type"] = "noEnd"
        return {"pattern": pattern, "range": span}
    except (KeyError, ValueError, TypeError, RuleError):
        return None


def fields_from_graph(item: dict[str, Any], fallback_tz: str) -> dict[str, Any]:
    all_day = bool(item.get("isAllDay"))
    start = _graph_moment(item["start"])
    end = _graph_moment(item.get("end") or item["start"])
    if all_day:
        start, end = _graph_day(start), _graph_day(end)
    raw_body = item.get("body")
    body: dict[str, Any] = raw_body if isinstance(raw_body, dict) else {}
    content = str(body.get("content") or "")
    if str(body.get("contentType") or "text").lower() == "html":
        content = html_to_text(content)
    raw_location = item.get("location")
    location: dict[str, Any] = raw_location if isinstance(raw_location, dict) else {}
    show = item.get("showAs")
    return {
        "title": str(item.get("subject") or "–")[:300],
        "description": content.strip()[:50_000],
        "location": str(location.get("displayName") or "")[:500],
        "start_at": start,
        "end_at": max(end, start),
        "all_day": all_day,
        "tzid": _zone(item.get("originalStartTimeZone"), fallback_tz),
        "rrule": rrule_from_graph(item.get("recurrence")),
        "status": "tentative" if show == "tentative" else "confirmed",
        "transparency": "transparent" if show == "free" else "opaque",
    }


def _graph_time(event: Event, instant: datetime) -> dict[str, str]:
    if event.all_day:
        day = instant.astimezone(UTC).date().isoformat()
        return {"dateTime": f"{day}T00:00:00", "timeZone": "UTC"}
    local = instant.astimezone(ZoneInfo(event.tzid)).replace(tzinfo=None)
    return {"dateTime": local.isoformat(timespec="seconds"), "timeZone": event.tzid}


def to_graph(event: Event) -> dict[str, Any]:
    if event.transparency == "transparent":
        show = "free"
    else:
        show = "tentative" if event.status == "tentative" else "busy"
    return {
        "subject": event.title,
        "body": {"contentType": "text", "content": event.description or ""},
        "location": {"displayName": event.location or ""},
        "start": _graph_time(event, event.start_at),
        "end": _graph_time(event, event.end_at),
        "isAllDay": event.all_day,
        "showAs": show,
        "recurrence": graph_recurrence(event),
    }


# --- Anbieter -----------------------------------------------------------------------------


def _fail(response: httpx.Response) -> SyncError:
    return SyncError(f"Der Server antwortet mit Status {response.status_code}.")


def _valid_id(value: object) -> str | None:
    return value if isinstance(value, str) and 0 < len(value) <= 1024 else None


class GoogleCalendar:
    unreachable = UNREACHABLE
    exdates = True

    def __init__(self, client: httpx.AsyncClient, calendar_id: str, tzid: str) -> None:
        self.client = client
        self.tzid = tzid
        self.base = f"{GOOGLE_API}/calendars/{quote(calendar_id, safe='')}/events"

    async def _send(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        response = await self.client.request(method, url, **kwargs)
        if response.status_code in (401, 403):
            raise SyncError(REJECTED)
        return response

    def _item(self, item: dict[str, Any]) -> RemoteItem | None:
        remote_id = _valid_id(item.get("id"))
        if remote_id is None:
            return None
        if item.get("recurringEventId"):
            original = item.get("originalStartTime")
            if item.get("status") != "cancelled" or not isinstance(original, dict):
                return None
            try:
                moment, _ = _moment(original, self.tzid)
            except (KeyError, ValueError, TypeError):
                return None
            return RemoteItem(
                remote_id, instance_of=str(item["recurringEventId"]), original_start=moment
            )
        if item.get("status") == "cancelled":
            return RemoteItem(remote_id, deleted=True)
        try:
            return RemoteItem(remote_id, fields=fields_from_google(item, self.tzid))
        except (KeyError, ValueError, TypeError):
            return RemoteItem(remote_id)

    async def changes(self, sync_token: str | None) -> Changes:
        params: dict[str, str] = {"maxResults": "250", "singleEvents": "false"}
        if sync_token:
            params |= {"syncToken": sync_token, "showDeleted": "true"}
        items: list[RemoteItem] = []
        for _ in range(MAX_PAGES):
            response = await self._send("GET", self.base, params=params)
            if response.status_code == 410:
                raise _Gone
            if response.status_code != 200:
                raise _fail(response)
            data = response.json()
            for raw in data.get("items", []):
                if isinstance(raw, dict) and (item := self._item(raw)) is not None:
                    items.append(item)
            page = data.get("nextPageToken")
            if not page:
                token = data.get("nextSyncToken")
                return Changes(items, str(token) if token else None)
            params["pageToken"] = str(page)
        raise SyncError(TOO_MANY)

    async def insert(self, event: Event) -> str:
        response = await self._send("POST", self.base, json=to_google(event))
        if response.status_code not in (200, 201):
            raise _fail(response)
        return str(response.json()["id"])

    async def update(self, remote_id: str, event: Event) -> bool:
        """False: gibt es beim Anbieter nicht mehr."""
        url = f"{self.base}/{quote(remote_id, safe='')}"
        response = await self._send("PATCH", url, json=to_google(event))
        if response.status_code in (404, 410):
            return False
        if response.status_code != 200:
            raise _fail(response)
        return True

    async def delete(self, remote_id: str) -> None:
        response = await self._send("DELETE", f"{self.base}/{quote(remote_id, safe='')}")
        if response.status_code not in (200, 204, 404, 410):
            raise _fail(response)


class OutlookCalendar:
    """Microsoft Graph – Zeiten kommen dank ``Prefer`` in UTC, Beschreibungen als Text."""

    unreachable = OUTLOOK_UNREACHABLE
    exdates = False
    PREFER = 'outlook.timezone="UTC", outlook.body-content-type="text"'
    SELECT = (
        "id,subject,body,location,start,end,isAllDay,recurrence,showAs,type,isCancelled,"
        "originalStartTimeZone"
    )

    def __init__(self, client: httpx.AsyncClient, tzid: str) -> None:
        self.client = client
        self.tzid = tzid

    async def _send(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        headers = {"Prefer": self.PREFER}
        response = await self.client.request(method, url, headers=headers, **kwargs)
        if response.status_code in (401, 403):
            raise SyncError(OUTLOOK_REJECTED)
        return response

    def _item(self, item: dict[str, Any]) -> RemoteItem | None:
        remote_id = _valid_id(item.get("id"))
        if remote_id is None:
            return None
        if item.get("isCancelled"):
            return RemoteItem(remote_id, deleted=True)
        if item.get("type") not in (None, "singleInstance", "seriesMaster"):
            return None  # einzelne Vorkommen und Ausnahmen einer Serie
        try:
            return RemoteItem(remote_id, fields=fields_from_graph(item, self.tzid))
        except (KeyError, ValueError, TypeError):
            return RemoteItem(remote_id)

    async def changes(self, sync_token: str | None) -> Changes:
        url = GRAPH_EVENTS
        params: dict[str, str] | None = {"$top": "100", "$select": self.SELECT}
        items: list[RemoteItem] = []
        for _ in range(GRAPH_PAGES):
            response = await self._send("GET", url, params=params)
            if response.status_code != 200:
                raise _fail(response)
            data = response.json()
            for raw in data.get("value", []):
                if isinstance(raw, dict) and (item := self._item(raw)) is not None:
                    items.append(item)
            next_link = data.get("@odata.nextLink")
            if not next_link:
                return Changes(items, None, complete=True)
            if not str(next_link).startswith(GRAPH_ROOT):  # nur Microsoft folgen (kein SSRF)
                raise SyncError(OUTLOOK_UNREACHABLE)
            url, params = str(next_link), None
        raise SyncError(TOO_MANY)

    async def insert(self, event: Event) -> str:
        response = await self._send("POST", GRAPH_EVENTS, json=to_graph(event))
        if response.status_code not in (200, 201):
            raise _fail(response)
        return str(response.json()["id"])

    async def update(self, remote_id: str, event: Event) -> bool:
        url = f"{GRAPH_EVENTS}/{quote(remote_id, safe='')}"
        response = await self._send("PATCH", url, json=to_graph(event))
        if response.status_code in (404, 410):
            return False
        if response.status_code != 200:
            raise _fail(response)
        return True

    async def delete(self, remote_id: str) -> None:
        response = await self._send("DELETE", f"{GRAPH_EVENTS}/{quote(remote_id, safe='')}")
        if response.status_code not in (200, 204, 404, 410):
            raise _fail(response)


def _client(conn: CalendarConnection, http: httpx.AsyncClient, owner: User) -> CalendarClient:
    if conn.provider == "microsoft":
        return OutlookCalendar(http, owner.timezone)
    return GoogleCalendar(http, conn.remote_calendar_id, owner.timezone)


# --- Abgleich -----------------------------------------------------------------------------


async def _forget(db: AsyncSession, event: Event) -> None:
    """Beim Anbieter schon gelöscht – hier löschen, ohne Grabstein."""
    event.connection_id = None
    await db.delete(event)


async def _pull(
    db: AsyncSession, conn: CalendarConnection, owner: User, api: CalendarClient, now: datetime
) -> None:
    try:
        changes = await api.changes(conn.sync_token)
    except _Gone:
        conn.sync_token = None
        changes = await api.changes(None)
    linked = {
        e.remote_id: e
        for e in (
            await db.scalars(
                select(Event).where(Event.connection_id == conn.id, Event.remote_id.is_not(None))
            )
        ).unique()
    }
    cutoff = now - timedelta(days=PAST_DAYS)
    seen: set[str] = set()
    cancelled: list[RemoteItem] = []
    for item in changes.items:
        if item.instance_of is not None:
            cancelled.append(item)
            continue
        seen.add(item.remote_id)
        event = linked.get(item.remote_id)
        if item.deleted:
            if event is not None:
                await _forget(db, event)
                linked.pop(item.remote_id)
            continue
        fields = item.fields
        if fields is None:
            continue
        if not api.exdates:
            fields.pop("exdates", None)  # Ausnahmen bleiben, wie sie in ToDoch sind
        if event is not None and event.remote_hash == _digest(fields, api.exdates):
            continue  # beim Anbieter unverändert – Änderungen in ToDoch nicht überschreiben
        if event is None:
            if fields["rrule"] is None and fields["end_at"] < cutoff:
                continue
            event = Event(
                area_id=conn.area_id,
                created_by=owner.id,
                uid=f"{uuid.uuid4()}@todoch",
                source=conn.provider,
                connection_id=conn.id,
                remote_id=item.remote_id,
                exdates=[],
                tags=[],
                attendees=[],
                reminders=[],
                sequence=0,
            )
            db.add(event)
            linked[item.remote_id] = event
        for name, value in fields.items():
            setattr(event, name, value)
        event.remote_hash = fingerprint(event, api.exdates)
    if changes.complete:
        for remote_id, event in list(linked.items()):
            if remote_id not in seen:
                await _forget(db, event)
                linked.pop(remote_id)
    for item in cancelled:
        master = linked.get(item.instance_of or "")
        if master is None or not master.rrule or item.original_start is None:
            continue
        if item.original_start not in (master.exdates or []):
            master.exdates = [*(master.exdates or []), item.original_start]
            master.remote_hash = fingerprint(master, api.exdates)
    conn.sync_token = changes.token


async def _push(
    db: AsyncSession, conn: CalendarConnection, api: CalendarClient, now: datetime
) -> None:
    stones = list(
        await db.scalars(
            select(CalendarTombstone)
            .where(CalendarTombstone.connection_id == conn.id)
            .limit(MAX_PUSH)
        )
    )
    for stone in stones:
        await api.delete(stone.remote_id)
        await db.delete(stone)

    moved = (
        await db.scalars(
            select(Event).where(Event.connection_id == conn.id, Event.area_id != conn.area_id)
        )
    ).unique()
    for event in moved:
        if event.remote_id:
            await api.delete(event.remote_id)
        event.connection_id, event.remote_id, event.remote_hash = None, None, None

    candidates = (
        await db.scalars(
            select(Event).where(
                Event.area_id == conn.area_id,
                Event.calendar_id.is_(None),
                Event.series_id.is_(None),
                or_(Event.connection_id.is_(None), Event.connection_id == conn.id),
            )
        )
    ).unique()
    cutoff = now - timedelta(days=PAST_DAYS)
    pushed = 0
    for event in candidates:
        digest = fingerprint(event, api.exdates)
        linked = event.connection_id == conn.id and bool(event.remote_id)
        if linked and event.remote_hash == digest:
            continue
        if not linked and not event.rrule and event.end_at < cutoff:
            continue  # Altes bleibt beim ersten Verbinden in ToDoch
        if pushed >= MAX_PUSH:
            break
        if not (linked and event.remote_id and await api.update(event.remote_id, event)):
            event.remote_id = await api.insert(event)
        event.connection_id = conn.id
        event.remote_hash = digest
        pushed += 1


async def sync_connection(
    db: AsyncSession,
    crypto: Crypto,
    settings: Settings | None,
    conn: CalendarConnection,
    owner: User,
    now: datetime | None = None,
) -> None:
    """Einmal abgleichen. Fehler landen in ``last_error``."""
    now = now or datetime.now(UTC)
    conn.last_synced_at = now
    try:
        refresh = crypto.decrypt_str(conn.token_encrypted, context=token_context(conn.id))
        config = calendar_provider(settings, conn.provider) if settings else None
        if config is None:
            raise SyncError(oauth.NOT_CONFIGURED)
        try:
            tokens = await oauth.refresh_access(config, refresh)
        except oauth.OAuthError as exc:
            raise SyncError(exc.message) from exc
        if tokens.refresh_token and tokens.refresh_token != refresh:
            conn.token_encrypted = crypto.encrypt(
                tokens.refresh_token, context=token_context(conn.id)
            )
        headers = {"Authorization": f"Bearer {tokens.access_token}"}
        async with httpx.AsyncClient(timeout=TIMEOUT, transport=TRANSPORT, headers=headers) as http:
            api = _client(conn, http, owner)
            try:
                await _pull(db, conn, owner, api, now)
                await db.flush()
                await _push(db, conn, api, now)
            except httpx.HTTPError as exc:
                raise SyncError(api.unreachable) from exc
        await db.flush()
        conn.event_count = (
            await db.scalar(
                select(func.count()).select_from(Event).where(Event.connection_id == conn.id)
            )
            or 0
        )
        conn.last_success_at = now
        conn.last_error = None
    except SyncError as exc:
        conn.last_error = exc.message[:300]
    except DecryptionError:
        conn.last_error = "Das gespeicherte Token lässt sich nicht entschlüsseln."
    except httpx.HTTPError:
        conn.last_error = UNREACHABLE
    await db.commit()


async def sync_due_connections(db: AsyncSession, crypto: Crypto, settings: Settings | None) -> int:
    """Für den Worker: alle aktiven Verbindungen abgleichen."""
    connections = list(
        (
            await db.scalars(select(CalendarConnection).where(CalendarConnection.enabled.is_(True)))
        ).unique()
    )
    done = 0
    for conn in connections:
        owner = await db.get(User, conn.owner_id)
        if owner is None or not owner.is_active:
            continue
        try:
            await sync_connection(db, crypto, settings, conn, owner)
        except Exception:  # eine kaputte Verbindung darf die anderen nicht aufhalten
            log.exception("Kalender-Abgleich %s fehlgeschlagen", conn.id)
            await db.rollback()
        done += 1
    return done
