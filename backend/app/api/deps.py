"""FastAPI-Abhängigkeiten: Datenbank, Ressourcen, angemeldeter Nutzer."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AreaMember, User, UserSession
from app.resources import Resources
from app.security.middleware import SESSION_COOKIE
from app.security.sessions import resolve_session


def get_resources(request: Request) -> Resources:
    resources: Resources = request.app.state.resources
    return resources


Res = Annotated[Resources, Depends(get_resources)]


async def get_db(res: Res) -> AsyncIterator[AsyncSession]:
    async with res.sessionmaker() as session:
        yield session


DB = Annotated[AsyncSession, Depends(get_db)]


async def get_current_session(request: Request, db: DB, res: Res) -> UserSession:
    session = await resolve_session(db, request.cookies.get(SESSION_COOKIE), res.settings)
    if session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bitte anmelden.")
    return session


CurrentSession = Annotated[UserSession, Depends(get_current_session)]


async def get_current_user(session: CurrentSession, db: DB) -> User:
    """Der angemeldete Nutzer – samt seiner Rollen in geteilten Bereichen (für app/policy.py)."""
    user = session.user
    await load_member_roles(db, user)
    return user


async def load_member_roles(db: AsyncSession, user: User) -> None:
    rows = await db.execute(
        select(AreaMember.area_id, AreaMember.role).where(AreaMember.user_id == user.id)
    )
    # Nur für diese Anfrage am Objekt – kein gespeichertes Feld
    object.__setattr__(user, "area_roles", {area_id: role for area_id, role in rows.tuples()})


CurrentUser = Annotated[User, Depends(get_current_user)]


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def user_now(user: User) -> datetime:
    return datetime.now(ZoneInfo(user.timezone))


def user_today(user: User) -> date:
    return user_now(user).date()
