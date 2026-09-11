"""Abonnierte Kalender (ICS): sicher abrufen, zerlegen und mit den Terminen abgleichen.

Abruf: nur http(s), jede Adresse (auch nach Weiterleitungen) wird vor dem Verbinden
aufgelöst und geprüft – Loopback, Link-Local (Cloud-Metadaten), Multicast und reservierte
Bereiche sind gesperrt, Adressen im eigenen Netz (z. B. Streamo im Heimnetz) nur für Admins.
Höchstens 2 MB, 15 Sekunden, 3 Weiterleitungen, 5000 Termine.

Abgleich: Der Feed ist die Quelle. Neue Termine kommen dazu, geänderte werden aktualisiert,
fehlende gelöscht. Uhrzeiten ohne Zeitzone („schwebend“, so liefert Streamo) gelten in der
Zeitzone des Nutzers.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

import anyio.to_thread
import httpx
from icalendar import Calendar
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, ExternalCalendar, User
from app.security.crypto import Crypto, DecryptionError
from app.services.event_recurrence import RuleError, normalize_event_rule
from app.services.events import midnight_utc

log = logging.getLogger(__name__)

MAX_BYTES = 2_000_000
MAX_EVENTS = 5000
MAX_REDIRECTS = 3
TIMEOUT = httpx.Timeout(15.0, connect=10.0)
USER_AGENT = "ToDoch-Kalenderabo/1.0"
STATUSES = ("tentative", "confirmed", "cancelled")


class FeedError(Exception):
    """Verständliche Fehlermeldung (Deutsch; übersetzt in app/i18n.py)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def url_context(calendar_id: object) -> str:
    return f"external_calendar:{calendar_id}:url"


def normalize_url(url: str) -> str:
    """webcal:// ist dieselbe Adresse wie https:// – so verlinken Apple & Co. Abos."""
    url = url.strip()
    if url.lower().startswith("webcal://"):
        return "https://" + url[len("webcal://") :]
    return url


# --- Abruf ---------------------------------------------------------------------------------


async def resolve(host: str, port: int) -> list[str]:
    infos = await anyio.to_thread.run_sync(
        lambda: socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    )
    return sorted({str(info[4][0]) for info in infos})


def _blocked(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    return (
        addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_unspecified
        or addr.is_reserved
    )


async def check_url(url: str, *, allow_private: bool) -> str:
    """Prüft Schema und Ziel einer Adresse und liefert den Hostnamen (für die Anzeige)."""
    try:
        parts = urlsplit(url)
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError as exc:
        raise FeedError("Die Adresse ist ungültig.") from exc
    host = parts.hostname or ""
    if parts.scheme not in ("http", "https") or not host:
        raise FeedError("Die Adresse muss mit http:// oder https:// beginnen.")
    try:
        addresses = await resolve(host, port)
    except OSError as exc:
        raise FeedError("Der Name der Adresse lässt sich nicht auflösen.") from exc
    if not addresses:
        raise FeedError("Der Name der Adresse lässt sich nicht auflösen.")
    for text in addresses:
        addr = ipaddress.ip_address(text.split("%", 1)[0])
        if _blocked(addr):
            raise FeedError("Diese Adresse ist nicht erlaubt.")
        if addr.is_private and not allow_private:
            raise FeedError("Adressen im eigenen Netz kann nur ein Admin einbinden.")
    return host.lower()


async def fetch_ics(
    url: str,
    *,
    allow_private: bool,
    etag: str | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[bytes | None, str | None]:
    """Lädt den Kalender. ``(None, etag)`` heißt: unverändert seit dem letzten Abruf."""
    headers = {"User-Agent": USER_AGENT, "Accept": "text/calendar, */*;q=0.1"}
    current = url
    try:
        async with httpx.AsyncClient(
            timeout=TIMEOUT, follow_redirects=False, headers=headers, transport=transport
        ) as client:
            for _ in range(MAX_REDIRECTS + 1):
                await check_url(current, allow_private=allow_private)
                extra = {"If-None-Match": etag} if etag else {}
                async with client.stream("GET", current, headers=extra) as response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get("location")
                        if not location:
                            raise FeedError("Der Kalender ist nicht erreichbar.")
                        current = urljoin(current, location)
                        continue
                    if response.status_code == 304:
                        return None, etag
                    if response.status_code != 200:
                        raise FeedError(f"Der Server antwortet mit Status {response.status_code}.")
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body += chunk
                        if len(body) > MAX_BYTES:
                            raise FeedError("Der Kalender ist zu groß (höchstens 2 MB).")
                    return bytes(body), response.headers.get("etag")
    except httpx.HTTPError as exc:
        raise FeedError("Der Kalender ist nicht erreichbar.") from exc
    raise FeedError("Zu viele Weiterleitungen.")


# --- Zerlegen ------------------------------------------------------------------------------


@dataclass
class ParsedEvent:
    uid: str
    title: str
    start_at: datetime
    end_at: datetime
    all_day: bool
    description: str = ""
    location: str = ""
    url: str = ""
    rrule: str | None = None
    exdates: list[datetime] = field(default_factory=list)
    status: str = "confirmed"
    transparency: str = "opaque"


def _utc(value: datetime, tzid: str) -> datetime:
    if value.tzinfo is None:  # schwebende Ortszeit
        value = value.replace(tzinfo=ZoneInfo(tzid))
    return value.astimezone(UTC)


def _moment(value: Any, tzid: str) -> datetime:
    if isinstance(value, datetime):
        return _utc(value, tzid)
    if isinstance(value, date):
        return midnight_utc(value)
    raise TypeError("kein Datum")


def _text(component: Any, name: str, limit: int) -> str:
    value = component.get(name)
    return str(value).strip()[:limit] if value is not None else ""


def _exdates(component: Any, tzid: str) -> list[datetime]:
    raw = component.get("EXDATE")
    if raw is None:
        return []
    groups = raw if isinstance(raw, list) else [raw]
    found: list[datetime] = []
    for group in groups:
        for item in getattr(group, "dts", []):
            try:
                found.append(_moment(item.dt, tzid))
            except TypeError:
                continue
    return sorted(set(found))


def _rule(component: Any) -> str | None:
    raw = component.get("RRULE")
    if raw is None:
        return None
    try:
        return normalize_event_rule(raw.to_ical().decode("utf-8"))
    except (RuleError, ValueError):
        return None  # unbekannte Regel: nur das erste Vorkommen übernehmen


def parse_ics(data: bytes, tzid: str) -> list[ParsedEvent]:
    try:
        calendar = Calendar.from_ical(data)
    except ValueError as exc:
        raise FeedError("Das ist keine gültige Kalenderdatei (ICS).") from exc
    if not isinstance(calendar, Calendar):
        raise FeedError("Das ist keine gültige Kalenderdatei (ICS).")

    events: list[ParsedEvent] = []
    for component in calendar.walk("VEVENT"):
        # Geänderte Einzeltermine einer Serie werden (noch) nicht übernommen
        if component.get("RECURRENCE-ID") is not None:
            continue
        uid = _text(component, "UID", 200)
        start_prop = component.get("DTSTART")
        if not uid or start_prop is None:
            continue
        start = start_prop.dt
        end_prop = component.get("DTEND")
        duration = component.get("DURATION")
        all_day = isinstance(start, date) and not isinstance(start, datetime)
        try:
            if all_day:
                end_day = end_prop.dt if end_prop is not None else None
                if isinstance(end_day, datetime):
                    end_day = end_day.date()
                if end_day is None and duration is not None:
                    end_day = start + duration.dt
                if end_day is None or end_day <= start:
                    end_day = start + timedelta(days=1)
                start_at, end_at = midnight_utc(start), midnight_utc(end_day)
            else:
                start_at = _utc(start, tzid)
                if end_prop is not None:
                    end_value = end_prop.dt
                    if not isinstance(end_value, datetime):
                        end_value = datetime.combine(end_value, time())
                    end_at = _utc(end_value, tzid)
                elif duration is not None:
                    end_at = start_at + duration.dt
                else:
                    end_at = start_at
                end_at = max(end_at, start_at)
        except (TypeError, ValueError, AttributeError):
            continue

        url = _text(component, "URL", 1000)
        status = _text(component, "STATUS", 20).lower()
        events.append(
            ParsedEvent(
                uid=uid,
                title=_text(component, "SUMMARY", 300) or "–",
                start_at=start_at,
                end_at=end_at,
                all_day=all_day,
                description=_text(component, "DESCRIPTION", 50_000),
                location=_text(component, "LOCATION", 500),
                url=url if url.lower().startswith(("https://", "http://")) else "",
                rrule=_rule(component),
                exdates=_exdates(component, tzid),
                status=status if status in STATUSES else "confirmed",
                transparency=(
                    "transparent"
                    if _text(component, "TRANSP", 20).upper() == "TRANSPARENT"
                    else "opaque"
                ),
            )
        )
        if len(events) > MAX_EVENTS:
            raise FeedError("Der Kalender enthält zu viele Termine (höchstens 5000).")
    return events


# --- Abgleich ------------------------------------------------------------------------------


FIELDS = (
    "title",
    "description",
    "location",
    "url",
    "start_at",
    "end_at",
    "all_day",
    "rrule",
    "exdates",
    "status",
    "transparency",
)


async def apply_events(
    db: AsyncSession, calendar: ExternalCalendar, owner: User, parsed: list[ParsedEvent]
) -> None:
    existing = {
        event.uid: event
        for event in (
            await db.scalars(select(Event).where(Event.calendar_id == calendar.id))
        ).unique()
    }
    seen: set[str] = set()
    for item in parsed:
        uid = f"{calendar.id}:{item.uid}"
        if uid in seen:
            continue
        seen.add(uid)
        event = existing.get(uid)
        if event is None:
            event = Event(
                area_id=calendar.area_id,
                created_by=owner.id,
                uid=uid,
                calendar_id=calendar.id,
                source="ics",
                tzid=owner.timezone,
                tags=[],
                attendees=[],
                reminders=[],
            )
            db.add(event)
        changed = event.area_id != calendar.area_id
        event.area_id = calendar.area_id
        for name in FIELDS:
            value = getattr(item, name)
            if getattr(event, name, None) != value:
                setattr(event, name, value)
                changed = True
        if changed and event.id is not None:
            event.sequence = (event.sequence or 0) + 1
    for uid, event in existing.items():
        if uid not in seen:
            await db.delete(event)
    calendar.event_count = len(seen)


async def sync_calendar(
    db: AsyncSession, crypto: Crypto, calendar: ExternalCalendar, owner: User
) -> None:
    """Einmal abgleichen. Fehler landen in ``last_error``, Termine bleiben dann unverändert."""
    now = datetime.now(UTC)
    calendar.last_synced_at = now
    try:
        url = crypto.decrypt_str(calendar.url_encrypted, context=url_context(calendar.id))
        body, etag = await fetch_ics(url, allow_private=owner.is_admin, etag=calendar.etag)
        if body is not None:
            parsed = parse_ics(body, owner.timezone)
            await apply_events(db, calendar, owner, parsed)
            calendar.etag = etag
        calendar.last_success_at = now
        calendar.last_error = None
    except FeedError as exc:
        calendar.last_error = exc.message[:300]
    except DecryptionError:
        calendar.last_error = "Die gespeicherte Adresse lässt sich nicht entschlüsseln."
    await db.commit()


async def sync_due_calendars(db: AsyncSession, crypto: Crypto) -> int:
    """Für den Worker: alle fälligen Kalender abgleichen."""
    now = datetime.now(UTC)
    calendars = list(
        (
            await db.scalars(select(ExternalCalendar).where(ExternalCalendar.enabled.is_(True)))
        ).unique()
    )
    done = 0
    for calendar in calendars:
        due = (
            calendar.last_synced_at is None
            or calendar.last_synced_at + timedelta(minutes=calendar.refresh_minutes) <= now
        )
        if not due:
            continue
        owner = await db.get(User, calendar.owner_id)
        if owner is None or not owner.is_active:
            continue
        try:
            await sync_calendar(db, crypto, calendar, owner)
        except Exception:  # ein kaputter Kalender darf die anderen nicht aufhalten
            log.exception("Abgleich von Kalender %s fehlgeschlagen", calendar.id)
            await db.rollback()
        done += 1
    return done
