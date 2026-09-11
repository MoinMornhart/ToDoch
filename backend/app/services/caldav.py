"""CalDAV (Nextcloud, iCloud, mailbox.org, Posteo, GMX, WEB.DE …) – Zwei-Wege-Abgleich ohne
App-Registrierung: Adresse, Benutzername und (App-)Passwort genügen.

Finden: Die Adresse darf ein Kalender sein oder nur der Server – dann geht es über
``/.well-known/caldav`` zum Nutzer (current-user-principal), zu seinen Kalendern
(calendar-home-set) und zu allen Kalendern, die Termine (VEVENT) können.

Abgleich über den gemeinsamen Kern in calendar_sync.py: ToDoch holt die vollständige Liste
(REPORT calendar-query) und schreibt einzelne Termine per PUT/DELETE. Beim Ändern bleibt die UID
des Termins beim Anbieter erhalten.

Sicherheit: Jede Adresse (auch nach Weiterleitungen) wird vor dem Verbinden geprüft wie bei
Kalender-Abos (kein Loopback, keine Cloud-Metadaten, Heimnetz nur für Admins); unverschlüsseltes
``http://`` nur im eigenen Netz. XML wird mit defusedxml gelesen (keine Entity-Bomben), Antworten
sind auf 5 MB begrenzt.
"""

from __future__ import annotations

import ipaddress
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urljoin, urlsplit
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

import httpx
from defusedxml import ElementTree  # type: ignore[import-untyped]
from icalendar import Calendar, vRecur
from icalendar import Event as VEvent

from app.models import Event
from app.services import external_calendars as feeds
from app.services.calendar_sync import TOO_MANY, Changes, RemoteItem, SyncError

NS = {"d": "DAV:", "c": "urn:ietf:params:xml:ns:caldav"}
MAX_BYTES = 5_000_000
MAX_REDIRECTS = 3
MAX_EVENTS = 5000

UNREACHABLE = "Der CalDAV-Kalender ist nicht erreichbar."
REJECTED = "Der CalDAV-Server hat die Anmeldung abgelehnt. Benutzername und App-Passwort prüfen."
UNEXPECTED = "Der CalDAV-Server antwortet nicht wie erwartet."
NO_CALENDAR = "Unter dieser Adresse wurde kein Kalender gefunden."
PLAIN_HTTP = "Ohne Verschlüsselung (http://) ist CalDAV nur im eigenen Netz erlaubt."

_XML = '<?xml version="1.0" encoding="utf-8"?>'
_DAV = 'xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"'
PROPFIND_PRINCIPAL = (
    f"{_XML}<d:propfind {_DAV}><d:prop><d:current-user-principal/></d:prop></d:propfind>"
)
PROPFIND_HOME = f"{_XML}<d:propfind {_DAV}><d:prop><c:calendar-home-set/></d:prop></d:propfind>"
PROPFIND_CALENDARS = (
    f"{_XML}<d:propfind {_DAV}><d:prop><d:resourcetype/><d:displayname/>"
    "<c:supported-calendar-component-set/></d:prop></d:propfind>"
)
REPORT_EVENTS = (
    f"{_XML}<c:calendar-query {_DAV}><d:prop><d:getetag/><c:calendar-data/></d:prop>"
    '<c:filter><c:comp-filter name="VCALENDAR"><c:comp-filter name="VEVENT"/></c:comp-filter>'
    "</c:filter></c:calendar-query>"
)
XML_TYPE = {"Content-Type": "application/xml; charset=utf-8"}
ICS_TYPE = {"Content-Type": "text/calendar; charset=utf-8"}


@dataclass
class FoundCalendar:
    url: str
    name: str


def _fail(status: int) -> SyncError:
    return SyncError(f"Der Server antwortet mit Status {status}.")


def _private(text: str) -> bool:
    return ipaddress.ip_address(text.split("%", 1)[0]).is_private


def responses(data: bytes) -> list[tuple[str, Any]]:
    """Multistatus → [(href, <prop> mit Status 200)]."""
    try:
        root = ElementTree.fromstring(data)
    except Exception as exc:  # kaputtes XML oder verbotene Entities (defusedxml)
        raise SyncError(UNEXPECTED) from exc
    found: list[tuple[str, Any]] = []
    for response in root.findall("d:response", NS):
        href = (response.findtext("d:href", default="", namespaces=NS) or "").strip()
        for propstat in response.findall("d:propstat", NS):
            status = propstat.findtext("d:status", default="", namespaces=NS) or ""
            prop = propstat.find("d:prop", NS)
            if " 200" in status and prop is not None:
                found.append((href, prop))
    return found


class CalDav:
    """HTTP zu einem CalDAV-Server – jede Adresse geprüft, Weiterleitungen von Hand."""

    def __init__(self, http: httpx.AsyncClient, *, allow_private: bool) -> None:
        self.http = http
        self.allow_private = allow_private

    async def _check(self, url: str) -> None:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise SyncError(NO_CALENDAR)
        port = parts.port or (443 if parts.scheme == "https" else 80)
        try:
            addresses = await feeds.check_address(
                parts.hostname, port, allow_private=self.allow_private
            )
        except feeds.FeedError as exc:
            raise SyncError(exc.message) from exc
        if parts.scheme == "http" and not all(_private(a) for a in addresses):
            raise SyncError(PLAIN_HTTP)

    async def request(
        self,
        method: str,
        url: str,
        *,
        body: str | bytes | None = None,
        depth: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, bytes, str]:
        """(Status, Inhalt, endgültige Adresse)."""
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            await self._check(current)
            send = {**(XML_TYPE if isinstance(body, str) else {}), **(headers or {})}
            if depth is not None:
                send["Depth"] = depth
            content = body.encode() if isinstance(body, str) else body
            async with self.http.stream(method, current, content=content, headers=send) as reply:
                location = reply.headers.get("location")
                if reply.status_code in (301, 302, 303, 307, 308) and location:
                    current = urljoin(current, location)
                    continue
                if reply.status_code == 401:
                    raise SyncError(REJECTED)
                data = bytearray()
                async for chunk in reply.aiter_bytes():
                    data += chunk
                    if len(data) > MAX_BYTES:
                        raise SyncError(TOO_MANY)
                return reply.status_code, bytes(data), current
        raise SyncError(UNEXPECTED)

    async def _href(self, url: str, body: str, path: str) -> str | None:
        status, data, final = await self.request("PROPFIND", url, body=body, depth="0")
        if status != 207:
            return None
        for _, prop in responses(data):
            element = prop.find(path, NS)
            if element is not None and (element.text or "").strip():
                target: str = str(element.text).strip()
                return urljoin(final, target)
        return None

    async def _calendars(self, url: str, depth: str) -> list[FoundCalendar]:
        status, data, final = await self.request(
            "PROPFIND", url, body=PROPFIND_CALENDARS, depth=depth
        )
        if status != 207:
            return []
        found: list[FoundCalendar] = []
        for href, prop in responses(data):
            if prop.find("d:resourcetype/c:calendar", NS) is None:
                continue
            components = prop.findall("c:supported-calendar-component-set/c:comp", NS)
            if components and not any(c.get("name") == "VEVENT" for c in components):
                continue  # z. B. reine Aufgabenlisten
            full = urljoin(final, href)
            name = (prop.findtext("d:displayname", default="", namespaces=NS) or "").strip()
            found.append(FoundCalendar(full, name or full.rstrip("/").rsplit("/", 1)[-1]))
        return found

    async def discover(self, url: str) -> list[FoundCalendar]:
        """Kalender unter einer Adresse finden – direkt oder über den Server."""
        direct = await self._calendars(url, "0")
        if direct:
            return direct
        principal = await self._href(url, PROPFIND_PRINCIPAL, "d:current-user-principal/d:href")
        if principal is None:
            parts = urlsplit(url)
            known = f"{parts.scheme}://{parts.netloc}/.well-known/caldav"
            principal = await self._href(
                known, PROPFIND_PRINCIPAL, "d:current-user-principal/d:href"
            )
        if principal is None:
            raise SyncError(NO_CALENDAR)
        home = await self._href(principal, PROPFIND_HOME, "c:calendar-home-set/d:href")
        found = await self._calendars(home, "1") if home else []
        if not found:
            raise SyncError(NO_CALENDAR)
        return found


# --- Termine ------------------------------------------------------------------------------


def fields_from_ics(data: bytes, tzid: str) -> dict[str, Any] | None:
    try:
        events = feeds.parse_ics(data, tzid)
    except feeds.FeedError:
        return None
    if not events:
        return None
    first = events[0]
    return {
        "title": first.title,
        "description": first.description,
        "location": first.location,
        "start_at": first.start_at,
        "end_at": first.end_at,
        "all_day": first.all_day,
        "tzid": tzid,
        "rrule": first.rrule,
        "exdates": first.exdates if first.rrule else [],
        "status": first.status,
        "transparency": first.transparency,
    }


def _uid_of(data: bytes) -> str | None:
    try:
        calendar = Calendar.from_ical(data)
    except ValueError:
        return None
    for component in calendar.walk("VEVENT"):
        uid = component.get("UID")
        if uid:
            return str(uid)
    return None


def _moment(event: Event, instant: datetime) -> date | datetime:
    return (
        instant.astimezone(UTC).date()
        if event.all_day
        else instant.astimezone(ZoneInfo(event.tzid))
    )


def event_ics(event: Event, uid: str) -> bytes:
    """Ein Termin als Kalenderobjekt für PUT (ohne METHOD, RFC 4791)."""
    calendar = Calendar()
    calendar.add("prodid", "-//Todoch//Todoch//DE")
    calendar.add("version", "2.0")
    item = VEvent()
    item.add("uid", uid)
    item.add("dtstamp", datetime.now(UTC))
    item.add("sequence", event.sequence or 0)
    item.add("dtstart", _moment(event, event.start_at))
    item.add("dtend", _moment(event, event.end_at))
    if event.rrule:
        item.add("rrule", vRecur.from_ical(event.rrule))
        if event.exdates:
            item.add("exdate", [_moment(event, d) for d in sorted(event.exdates)])
    item.add("summary", event.title)
    if event.description:
        item.add("description", event.description)
    if event.location:
        item.add("location", event.location)
    item.add("status", event.status.upper())
    item.add("transp", "TRANSPARENT" if event.transparency == "transparent" else "OPAQUE")
    calendar.add_component(item)
    calendar.add_missing_timezones()
    return bytes(calendar.to_ical())


class CalDavCalendar:
    unreachable = UNREACHABLE
    exdates = True

    def __init__(self, dav: CalDav, url: str, tzid: str) -> None:
        self.dav = dav
        self.url = url if url.endswith("/") else url + "/"
        parts = urlsplit(self.url)
        self.origin = f"{parts.scheme}://{parts.netloc}"
        self.tzid = tzid

    def _absolute(self, path: str) -> str:
        return urljoin(self.origin, path)

    async def changes(self, sync_token: str | None) -> Changes:
        status, data, final = await self.dav.request(
            "REPORT", self.url, body=REPORT_EVENTS, depth="1"
        )
        if status != 207:
            raise _fail(status)
        items: list[RemoteItem] = []
        for href, prop in responses(data):
            ics = prop.findtext("c:calendar-data", default="", namespaces=NS) or ""
            path = urlsplit(urljoin(final, href)).path
            if not ics.strip() or not path or len(path) > 1024:
                continue
            items.append(RemoteItem(path, fields=fields_from_ics(ics.encode(), self.tzid)))
            if len(items) > MAX_EVENTS:
                raise SyncError(TOO_MANY)
        return Changes(items, None, complete=True)

    async def insert(self, event: Event) -> str:
        url = f"{self.url}{uuid.uuid4()}.ics"
        headers = {**ICS_TYPE, "If-None-Match": "*"}
        status, _, _ = await self.dav.request(
            "PUT", url, body=event_ics(event, event.uid), headers=headers
        )
        if status not in (200, 201, 204):
            raise _fail(status)
        return urlsplit(url).path

    async def update(self, remote_id: str, event: Event) -> bool:
        url = self._absolute(remote_id)
        status, data, _ = await self.dav.request("GET", url)
        if status in (404, 410):
            return False
        if status != 200:
            raise _fail(status)
        uid = _uid_of(data) or event.uid  # die UID beim Anbieter bleibt
        status, _, _ = await self.dav.request(
            "PUT", url, body=event_ics(event, uid), headers=ICS_TYPE
        )
        if status in (404, 410):
            return False
        if status not in (200, 201, 204):
            raise _fail(status)
        return True

    async def delete(self, remote_id: str) -> None:
        status, _, _ = await self.dav.request("DELETE", self._absolute(remote_id))
        if status not in (200, 204, 404, 410):
            raise _fail(status)


def calendar_data(ics: bytes) -> str:
    """Für Tests und Nachbauten: ICS sicher in XML einbetten."""
    return escape(ics.decode())
