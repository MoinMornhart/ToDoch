"""Serverseitige Sitzungen mit Idle- und Absolut-Timeout."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import User, UserSession
from app.security.middleware import CSRF_COOKIE, SESSION_COOKIE

TOUCH_INTERVAL = timedelta(seconds=60)


def hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


def _now() -> datetime:
    return datetime.now(UTC)


async def create_session(
    db: AsyncSession,
    user: User,
    settings: Settings,
    *,
    method: str,
    ip: str | None,
    user_agent: str | None,
) -> tuple[UserSession, str]:
    token = secrets.token_urlsafe(32)
    now = _now()
    session = UserSession(
        user_id=user.id,
        token_hash=hash_token(token),
        auth_method=method,
        ip=ip,
        user_agent=(user_agent or "")[:300] or None,
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(hours=settings.session_absolute_hours),
    )
    db.add(session)
    await db.flush()
    return session, token


def is_session_valid(session: UserSession, settings: Settings, now: datetime | None = None) -> bool:
    now = now or _now()
    if session.revoked_at is not None or session.expires_at <= now:
        return False
    if session.last_seen_at + timedelta(minutes=settings.session_idle_minutes) <= now:
        return False
    return session.user.is_active


async def resolve_session(
    db: AsyncSession, token: str | None, settings: Settings
) -> UserSession | None:
    if not token or len(token) > 128:
        return None
    session = await db.scalar(
        select(UserSession).where(UserSession.token_hash == hash_token(token))
    )
    if session is None or not is_session_valid(session, settings):
        return None
    now = _now()
    if now - session.last_seen_at >= TOUCH_INTERVAL:
        session.last_seen_at = now
        await db.commit()
    return session


async def revoke_session(db: AsyncSession, session: UserSession) -> None:
    session.revoked_at = _now()
    await db.flush()


async def revoke_all_sessions(
    db: AsyncSession, user_id: uuid.UUID, *, except_id: uuid.UUID | None = None
) -> int:
    stmt = (
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=_now())
    )
    if except_id is not None:
        stmt = stmt.where(UserSession.id != except_id)
    result = await db.execute(stmt)
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


def set_session_cookies(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_absolute_hours * 3600,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )
    # Neues CSRF-Token nach jeder Anmeldung (Rotation).
    response.set_cookie(
        CSRF_COOKIE,
        secrets.token_urlsafe(32),
        max_age=60 * 60 * 24 * 30,
        path="/",
        secure=True,
        httponly=False,
        samesite="lax",
    )


def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="lax")
    response.set_cookie(
        CSRF_COOKIE,
        secrets.token_urlsafe(32),
        max_age=60 * 60 * 24 * 30,
        path="/",
        secure=True,
        httponly=False,
        samesite="lax",
    )
