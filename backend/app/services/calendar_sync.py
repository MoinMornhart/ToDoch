"""Zwei-Wege-Abgleich mit Google Kalender.

Verbinden: „Google Kalender verbinden“ im Bereich – OAuth wie beim Postfach (dieselbe
Rücksprungadresse), aber nur mit dem Recht auf Termine. Jede Verbindung gehört zu einem Bereich:
Termine dieses Bereichs gehen zu Google, Termine aus Google landen in diesem Bereich.

Abgleich (Worker alle 5 Minuten oder auf Knopfdruck):

1. Holen – nur Änderungen seit dem letzten Mal (``syncToken``). Beim ersten Mal kommt alles,
   übernommen werden aber nur Serien und Termine der letzten 90 Tage und der Zukunft. Bei Google
   gelöschte Termine verschwinden auch hier, abgesagte Vorkommen werden Ausnahmen der Serie.
2. Senden – neue und geänderte Termine des Bereichs (erkannt am Fingerabdruck der Inhalte), in
   ToDoch gelöschte Termine (Grabsteine) und Termine, die in einen anderen Bereich wanderten.

Wurde ein Termin auf beiden Seiten geändert, gewinnt Google. Einzelne geänderte Vorkommen einer
Serie werden noch nicht abgeglichen.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import CalendarConnection, CalendarTombstone, Event, User
from app.security.crypto import Crypto, DecryptionError
from app.services import mail_oauth as oauth
from app.services.event_recurrence import RuleError, normalize_event_rule
from app.services.events import midnight_utc

log = logging.getLogger(__name__)

API = "https://www.googleapis.com/calendar/v3"
SCOPE = "openid email https://www.googleapis.com/auth/calendar.events"
TIMEOUT = httpx.Timeout(20.0, connect=10.0)
# Tests setzen hier einen Nachbau von Google Kalender ein
TRANSPORT: httpx.AsyncBaseTransport | None = None
MAX_PAGES = 20
MAX_PUSH = 200
PAST_DAYS = 90

UNREACHABLE = "Google Kalender ist nicht erreichbar."
REJECTED = "Google Kalender hat die Anmeldung abgelehnt. Bitte neu verbinden."


class SyncError(Exception):
    """Verständliche Fehlermeldung (Deutsch; übersetzt in app/i18n.py)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class _Gone(Exception):
    """Der syncToken ist abgelaufen – alles neu holen."""


def token_context(connection_id: object) -> str:
    return f"calendar_connection:{connection_id}:token"


def calendar_provider(settings: Settings, name: str) -> oauth.Provider | None:
    """Wie der Anbieter fürs Postfach, aber nur mit dem Recht auf Termine."""
    base = oauth.provider(settings, name)
    if base is None or name != "google":
        return None
    return replace(base, scope=SCOPE)


# --- Umrechnung ---------------------------------------------------------------------------


def fingerprint(event: Event) -> str:
    """Fingerabdruck der abgeglichenen Inhalte – ändert er sich, muss der Termin zu Google."""
    parts = [
        event.title,
        event.description or "",
        event.location or "",
        event.start_at.astimezone(UTC).isoformat(),
        event.end_at.astimezone(UTC).isoformat(),
        str(event.all_day),
        event.tzid,
        event.rrule or "",
        ",".join(sorted(d.astimezone(UTC).isoformat() for d in event.exdates or [])),
        event.status,
        event.transparency,
    ]
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


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


# --- Google Kalender ----------------------------------------------------------------------


class GoogleCalendar:
    def __init__(self, client: httpx.AsyncClient, calendar_id: str) -> None:
        self.client = client
        self.base = f"{API}/calendars/{quote(calendar_id, safe='')}/events"

    async def _send(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        response = await self.client.request(method, url, **kwargs)
        if response.status_code in (401, 403):
            raise SyncError(REJECTED)
        return response

    @staticmethod
    def _fail(response: httpx.Response) -> SyncError:
        return SyncError(f"Der Server antwortet mit Status {response.status_code}.")

    async def changes(self, sync_token: str | None) -> tuple[list[dict[str, Any]], str | None]:
        params: dict[str, str] = {"maxResults": "250", "singleEvents": "false"}
        if sync_token:
            params |= {"syncToken": sync_token, "showDeleted": "true"}
        items: list[dict[str, Any]] = []
        for _ in range(MAX_PAGES):
            response = await self._send("GET", self.base, params=params)
            if response.status_code == 410:
                raise _Gone
            if response.status_code != 200:
                raise self._fail(response)
            data = response.json()
            items.extend(i for i in data.get("items", []) if isinstance(i, dict))
            page = data.get("nextPageToken")
            if not page:
                token = data.get("nextSyncToken")
                return items, str(token) if token else None
            params["pageToken"] = str(page)
        raise SyncError("Der Kalender enthält zu viele Termine (höchstens 5000).")

    async def insert(self, body: dict[str, Any]) -> str:
        response = await self._send("POST", self.base, json=body)
        if response.status_code not in (200, 201):
            raise self._fail(response)
        return str(response.json()["id"])

    async def update(self, remote_id: str, body: dict[str, Any]) -> bool:
        """False: gibt es bei Google nicht mehr."""
        response = await self._send("PATCH", f"{self.base}/{quote(remote_id, safe='')}", json=body)
        if response.status_code in (404, 410):
            return False
        if response.status_code != 200:
            raise self._fail(response)
        return True

    async def delete(self, remote_id: str) -> None:
        response = await self._send("DELETE", f"{self.base}/{quote(remote_id, safe='')}")
        if response.status_code not in (200, 204, 404, 410):
            raise self._fail(response)


# --- Abgleich -----------------------------------------------------------------------------


async def _pull(
    db: AsyncSession, conn: CalendarConnection, owner: User, api: GoogleCalendar, now: datetime
) -> None:
    try:
        items, token = await api.changes(conn.sync_token)
    except _Gone:
        conn.sync_token = None
        items, token = await api.changes(None)
    linked = {
        e.remote_id: e
        for e in (
            await db.scalars(
                select(Event).where(Event.connection_id == conn.id, Event.remote_id.is_not(None))
            )
        ).unique()
    }
    cutoff = now - timedelta(days=PAST_DAYS)
    cancelled_instances: list[tuple[str, dict[str, Any]]] = []
    for item in items:
        remote_id = item.get("id")
        if not isinstance(remote_id, str) or not remote_id or len(remote_id) > 1024:
            continue
        if item.get("recurringEventId"):
            if item.get("status") == "cancelled" and isinstance(
                item.get("originalStartTime"), dict
            ):
                cancelled_instances.append(
                    (str(item["recurringEventId"]), item["originalStartTime"])
                )
            continue
        event = linked.get(remote_id)
        if item.get("status") == "cancelled":
            if event is not None:
                event.connection_id = None  # bei Google schon weg – kein Grabstein nötig
                await db.delete(event)
                linked.pop(remote_id)
            continue
        try:
            fields = fields_from_google(item, owner.timezone)
        except (KeyError, ValueError, TypeError):
            continue
        if event is None:
            if fields["rrule"] is None and fields["end_at"] < cutoff:
                continue
            event = Event(
                area_id=conn.area_id,
                created_by=owner.id,
                uid=f"{uuid.uuid4()}@todoch",
                source="google",
                connection_id=conn.id,
                remote_id=remote_id,
                tags=[],
                attendees=[],
                reminders=[],
                sequence=0,
            )
            db.add(event)
            linked[remote_id] = event
        for name, value in fields.items():
            setattr(event, name, value)
        event.remote_hash = fingerprint(event)
    for master_id, original in cancelled_instances:
        master = linked.get(master_id)
        if master is None or not master.rrule:
            continue
        try:
            moment, _ = _moment(original, master.tzid)
        except (KeyError, ValueError, TypeError):
            continue
        if moment not in (master.exdates or []):
            master.exdates = [*(master.exdates or []), moment]
            master.remote_hash = fingerprint(master)
    conn.sync_token = token


async def _push(
    db: AsyncSession, conn: CalendarConnection, api: GoogleCalendar, now: datetime
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
        digest = fingerprint(event)
        linked = event.connection_id == conn.id and bool(event.remote_id)
        if linked and event.remote_hash == digest:
            continue
        if not linked and not event.rrule and event.end_at < cutoff:
            continue  # Altes bleibt beim ersten Verbinden in ToDoch
        if pushed >= MAX_PUSH:
            break
        body = to_google(event)
        if not (linked and event.remote_id and await api.update(event.remote_id, body)):
            event.remote_id = await api.insert(body)
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
        async with httpx.AsyncClient(
            timeout=TIMEOUT, transport=TRANSPORT, headers=headers
        ) as client:
            api = GoogleCalendar(client, conn.remote_calendar_id)
            await _pull(db, conn, owner, api, now)
            await db.flush()
            await _push(db, conn, api, now)
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
