"""Kalender mit Google abgleichen (zwei Richtungen): verbinden, anzeigen, abgleichen, trennen."""

from __future__ import annotations

import json
import uuid
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import func, select, update

from app.api.deps import DB, CurrentUser, Res, client_ip
from app.api.tasks import area_for_new_item
from app.i18n import language_from, translate
from app.models import CalendarConnection, Event, User
from app.schemas.calendar_sync import ConnectionOut, ConnectionPatch, ConnectStartIn
from app.schemas.mail import OAuthStartOut
from app.services import audit
from app.services import calendar_sync as sync
from app.services import mail_oauth as oauth

router = APIRouter(prefix="/api/calendar-sync", tags=["calendars"])

MAX_CONNECTIONS = 5
STATE_PREFIX = "mailoauth:"  # derselbe Rücksprung wie beim Postfach (api/mail_oauth.py)


def connection_out(conn: CalendarConnection, language: str = "de") -> ConnectionOut:
    return ConnectionOut(
        id=conn.id,
        provider=conn.provider,
        account_email=conn.account_email,
        area_id=conn.area_id,
        area_name=conn.area.name,
        enabled=conn.enabled,
        event_count=conn.event_count,
        last_synced_at=conn.last_synced_at,
        last_success_at=conn.last_success_at,
        last_error=translate(conn.last_error, language) if conn.last_error else None,
        created_at=conn.created_at,
    )


def _language(request: Request) -> str:
    return language_from(request.headers.get("accept-language"))


async def _own(db: DB, user: User, connection_id: uuid.UUID) -> CalendarConnection:
    conn = await db.get(CalendarConnection, connection_id)
    if conn is None or conn.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nicht gefunden.")
    return conn


@router.get("", response_model=list[ConnectionOut])
async def list_connections(request: Request, db: DB, user: CurrentUser) -> list[ConnectionOut]:
    rows = await db.scalars(
        select(CalendarConnection)
        .where(CalendarConnection.owner_id == user.id)
        .order_by(CalendarConnection.created_at)
    )
    return [connection_out(c, _language(request)) for c in rows.unique()]


@router.post("/{provider}/start", response_model=OAuthStartOut)
async def start(
    provider: Literal["google", "microsoft"],
    body: ConnectStartIn,
    db: DB,
    res: Res,
    user: CurrentUser,
) -> OAuthStartOut:
    config = sync.calendar_provider(res.settings, provider)
    if config is None:
        raise HTTPException(status.HTTP_409_CONFLICT, oauth.NOT_CONFIGURED)
    area = await area_for_new_item(db, user, body.area_id)
    await res.limiter.enforce("calendar-oauth", str(user.id), limit=20, window=600)
    state = oauth.new_state()
    verifier, challenge = oauth.new_pkce()
    record = {
        "user": str(user.id),
        "provider": provider,
        "verifier": verifier,
        "purpose": "calendar",
        "area": str(area.id),
    }
    await res.redis.set(STATE_PREFIX + state, json.dumps(record), ex=oauth.STATE_TTL)
    redirect = oauth.redirect_uri(res.settings, provider)
    return OAuthStartOut(url=oauth.authorization_url(config, redirect, state, challenge))


async def finish(
    db: DB,
    res: Res,
    user: User,
    provider: str,
    record: dict[str, Any],
    tokens: oauth.Tokens,
    request: Request,
) -> str | None:
    """Rücksprung aus api/mail_oauth.py: Verbindung anlegen und gleich abgleichen."""
    if not tokens.refresh_token:
        return "failed"
    try:
        area = await area_for_new_item(db, user, uuid.UUID(str(record.get("area"))))
    except (HTTPException, ValueError):
        return "failed"
    existing = await db.scalar(
        select(CalendarConnection).where(
            CalendarConnection.owner_id == user.id,
            CalendarConnection.provider == provider,
            CalendarConnection.area_id == area.id,
            CalendarConnection.account_email == (tokens.email or ""),
        )
    )
    if existing is None:
        count = await db.scalar(
            select(func.count())
            .select_from(CalendarConnection)
            .where(CalendarConnection.owner_id == user.id)
        )
        if (count or 0) >= MAX_CONNECTIONS:
            return "limit"
        conn_id = uuid.uuid4()
        existing = CalendarConnection(
            id=conn_id,
            owner_id=user.id,
            area_id=area.id,
            area=area,
            provider=provider,
            account_email=tokens.email or "",
            remote_calendar_id="primary",
            token_encrypted="",
            enabled=True,
            event_count=0,
        )
        db.add(existing)
    existing.token_encrypted = res.crypto.encrypt(
        tokens.refresh_token, context=sync.token_context(existing.id)
    )
    existing.enabled = True
    audit.record(
        db,
        "calendar.connected",
        user_id=user.id,
        ip=client_ip(request),
        connection=str(existing.id),
        provider=provider,
    )
    await db.flush()
    await sync.sync_connection(db, res.crypto, res.settings, existing, user)
    return None


@router.post("/{connection_id}/sync", response_model=ConnectionOut)
async def sync_now(
    connection_id: uuid.UUID, request: Request, db: DB, res: Res, user: CurrentUser
) -> ConnectionOut:
    conn = await _own(db, user, connection_id)
    await res.limiter.enforce("calendar-sync-now", str(conn.id), limit=20, window=600)
    await sync.sync_connection(db, res.crypto, res.settings, conn, user)
    await db.refresh(conn)
    return connection_out(conn, _language(request))


@router.patch("/{connection_id}", response_model=ConnectionOut)
async def update_connection(
    connection_id: uuid.UUID, body: ConnectionPatch, request: Request, db: DB, user: CurrentUser
) -> ConnectionOut:
    conn = await _own(db, user, connection_id)
    if body.enabled is not None:
        conn.enabled = body.enabled
    await db.commit()
    await db.refresh(conn)
    return connection_out(conn, _language(request))


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    connection_id: uuid.UUID, request: Request, db: DB, user: CurrentUser
) -> None:
    """Trennt die Verbindung – die Termine bleiben in ToDoch und bei Google."""
    conn = await _own(db, user, connection_id)
    await db.execute(
        update(Event)
        .where(Event.connection_id == conn.id)
        .values(connection_id=None, remote_id=None, remote_hash=None)
    )
    await db.delete(conn)
    audit.record(
        db,
        "calendar.disconnected",
        user_id=user.id,
        ip=client_ip(request),
        connection=str(connection_id),
    )
    await db.commit()
