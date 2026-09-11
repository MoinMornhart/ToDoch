"""Abonnierte Kalender (ICS) verwalten – z. B. Streamo mit Filmen, Sehplänen und neuen Folgen."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import func, select, update

from app.api.deps import DB, CurrentUser, Res, client_ip
from app.api.tasks import area_for_new_item
from app.i18n import language_from, translate
from app.models import Event, ExternalCalendar, User
from app.schemas.calendars import CalendarIn, CalendarOut, CalendarPatch
from app.services import audit
from app.services import external_calendars as feeds

router = APIRouter(prefix="/api/calendars", tags=["calendars"])

MAX_CALENDARS = 20


def calendar_out(calendar: ExternalCalendar, language: str = "de") -> CalendarOut:
    return CalendarOut(
        id=calendar.id,
        name=calendar.name,
        host=calendar.url_host,
        area_id=calendar.area_id,
        area_name=calendar.area.name,
        refresh_minutes=calendar.refresh_minutes,
        enabled=calendar.enabled,
        event_count=calendar.event_count,
        last_synced_at=calendar.last_synced_at,
        last_success_at=calendar.last_success_at,
        last_error=translate(calendar.last_error, language) if calendar.last_error else None,
        created_at=calendar.created_at,
    )


def _language(request: Request) -> str:
    return language_from(request.headers.get("accept-language"))


async def _own(db: DB, user: User, calendar_id: uuid.UUID) -> ExternalCalendar:
    calendar = await db.get(ExternalCalendar, calendar_id)
    if calendar is None or calendar.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nicht gefunden.")
    return calendar


async def _checked_host(url: str, user: User) -> str:
    try:
        return await feeds.check_url(url, allow_private=user.is_admin)
    except feeds.FeedError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, exc.message) from exc


@router.get("", response_model=list[CalendarOut])
async def list_calendars(request: Request, db: DB, user: CurrentUser) -> list[CalendarOut]:
    rows = await db.scalars(
        select(ExternalCalendar)
        .where(ExternalCalendar.owner_id == user.id)
        .order_by(ExternalCalendar.created_at)
    )
    return [calendar_out(c, _language(request)) for c in rows.unique()]


@router.post("", response_model=CalendarOut, status_code=status.HTTP_201_CREATED)
async def add_calendar(
    body: CalendarIn, request: Request, db: DB, res: Res, user: CurrentUser
) -> CalendarOut:
    await res.limiter.enforce("calendar-add", str(user.id), limit=10, window=600)
    count = await db.scalar(
        select(func.count())
        .select_from(ExternalCalendar)
        .where(ExternalCalendar.owner_id == user.id)
    )
    if (count or 0) >= MAX_CALENDARS:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Höchstens {MAX_CALENDARS} Kalender möglich."
        )
    area = await area_for_new_item(db, user, body.area_id)
    url = feeds.normalize_url(body.url)
    host = await _checked_host(url, user)

    calendar_id = uuid.uuid4()
    calendar = ExternalCalendar(
        id=calendar_id,
        owner_id=user.id,
        area_id=area.id,
        area=area,
        name=body.name,
        url_encrypted=res.crypto.encrypt(url, context=feeds.url_context(calendar_id)),
        url_host=host,
        refresh_minutes=body.refresh_minutes,
        enabled=True,
        event_count=0,
    )
    db.add(calendar)
    audit.record(
        db, "calendar.added", user_id=user.id, ip=client_ip(request), calendar=str(calendar_id)
    )
    await db.flush()
    # Gleich einmal abgleichen – dann sieht man sofort, ob die Adresse stimmt
    await feeds.sync_calendar(db, res.crypto, calendar, user)
    await db.refresh(calendar)
    return calendar_out(calendar, _language(request))


@router.patch("/{calendar_id}", response_model=CalendarOut)
async def update_calendar(
    calendar_id: uuid.UUID,
    body: CalendarPatch,
    request: Request,
    db: DB,
    res: Res,
    user: CurrentUser,
) -> CalendarOut:
    calendar = await _own(db, user, calendar_id)
    fields = body.model_fields_set
    if "name" in fields and body.name is not None:
        calendar.name = body.name
    if "refresh_minutes" in fields and body.refresh_minutes is not None:
        calendar.refresh_minutes = body.refresh_minutes
    if "enabled" in fields and body.enabled is not None:
        calendar.enabled = body.enabled
    if "area_id" in fields and body.area_id is not None and body.area_id != calendar.area_id:
        area = await area_for_new_item(db, user, body.area_id)
        calendar.area_id, calendar.area = area.id, area
        await db.execute(
            update(Event).where(Event.calendar_id == calendar.id).values(area_id=area.id)
        )
    resync = False
    if "url" in fields and body.url is not None:
        url = feeds.normalize_url(body.url)
        calendar.url_host = await _checked_host(url, user)
        calendar.url_encrypted = res.crypto.encrypt(url, context=feeds.url_context(calendar.id))
        calendar.etag = None
        resync = True
    await db.flush()
    if resync:
        await feeds.sync_calendar(db, res.crypto, calendar, user)
    else:
        await db.commit()
    await db.refresh(calendar)
    return calendar_out(calendar, _language(request))


@router.post("/{calendar_id}/sync", response_model=CalendarOut)
async def sync_now(
    calendar_id: uuid.UUID, request: Request, db: DB, res: Res, user: CurrentUser
) -> CalendarOut:
    calendar = await _own(db, user, calendar_id)
    await res.limiter.enforce("calendar-sync", str(calendar.id), limit=10, window=600)
    await feeds.sync_calendar(db, res.crypto, calendar, user)
    await db.refresh(calendar)
    return calendar_out(calendar, _language(request))


@router.delete("/{calendar_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_calendar(
    calendar_id: uuid.UUID, request: Request, db: DB, user: CurrentUser
) -> None:
    """Entfernt das Abo samt seiner Termine (ON DELETE CASCADE)."""
    calendar = await _own(db, user, calendar_id)
    await db.delete(calendar)
    audit.record(
        db, "calendar.removed", user_id=user.id, ip=client_ip(request), calendar=str(calendar_id)
    )
    await db.commit()
