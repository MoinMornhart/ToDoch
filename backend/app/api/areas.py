"""Bereiche (Arbeit, Privat, …)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import ScalarSelect, func, select, update
from sqlalchemy.exc import IntegrityError

from app.api.deps import DB, CurrentUser
from app.models import Area, AreaMember, Task, User
from app.policy import Action, Role, authorize, role_for, visible_areas
from app.schemas.areas import AreaIn, AreaOut, AreaPatch

router = APIRouter(prefix="/api/areas", tags=["areas"])

MAX_AREAS = 50


def area_out(area: Area, user: User, open_count: int = 0, members: int = 0) -> AreaOut:
    role = role_for(user, area)
    return AreaOut(
        shared=members > 0 or role != Role.OWNER,
        id=area.id,
        name=area.name,
        color=area.color,
        icon=area.icon,
        sort_order=area.sort_order,
        open_count=open_count,
        role=role.value if role else "none",
        week_days=area.week_days,
        day_start=area.day_start,
        day_end=area.day_end,
    )


def _open_count() -> ScalarSelect[int]:
    return (
        select(func.count(Task.id))
        .where(Task.area_id == Area.id, Task.status == "open")
        .correlate(Area)
        .scalar_subquery()
    )


@router.get("", response_model=list[AreaOut])
async def list_areas(db: DB, user: CurrentUser) -> list[AreaOut]:
    members = (
        select(func.count(AreaMember.id))
        .where(AreaMember.area_id == Area.id)
        .correlate(Area)
        .scalar_subquery()
    )
    rows = await db.execute(
        select(Area, _open_count(), members)
        .where(visible_areas(user))
        .order_by(Area.sort_order, Area.name)
    )
    return [area_out(area, user, count, shared) for area, count, shared in rows.tuples()]


@router.post("", response_model=AreaOut, status_code=status.HTTP_201_CREATED)
async def create_area(body: AreaIn, db: DB, user: CurrentUser) -> AreaOut:
    owned = await db.scalar(select(func.count()).select_from(Area).where(Area.owner_id == user.id))
    if (owned or 0) >= MAX_AREAS:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Höchstens {MAX_AREAS} Bereiche möglich.")
    area = Area(owner_id=user.id, **body.model_dump())
    db.add(area)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Diesen Bereich gibt es schon.") from exc
    return area_out(area, user)


async def _load(db: DB, user: User, area_id: uuid.UUID, action: Action) -> Area:
    area = await db.get(Area, area_id)
    authorize(user, action, area)
    assert area is not None
    return area


@router.patch("/{area_id}", response_model=AreaOut)
async def update_area(area_id: uuid.UUID, body: AreaPatch, db: DB, user: CurrentUser) -> AreaOut:
    area = await _load(db, user, area_id, Action.MANAGE)
    for field in body.model_fields_set:
        value = getattr(body, field)
        if value is not None:
            setattr(area, field, value)
    if area.day_start >= area.day_end:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Der Kalender muss vor dem Ende beginnen."
        )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Diesen Bereich gibt es schon.") from exc
    count = await db.scalar(
        select(func.count(Task.id)).where(Task.area_id == area.id, Task.status == "open")
    )
    return area_out(area, user, count or 0)


@router.delete("/{area_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_area(
    area_id: uuid.UUID,
    db: DB,
    user: CurrentUser,
    move_to: Annotated[uuid.UUID | None, Query()] = None,
) -> None:
    area = await _load(db, user, area_id, Action.MANAGE)
    if role_for(user, area) != Role.OWNER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Nur der Besitzer kann den Bereich löschen.")
    remaining = await db.scalar(
        select(func.count()).select_from(Area).where(Area.owner_id == user.id, Area.id != area.id)
    )
    if not remaining:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Der letzte Bereich kann nicht gelöscht werden."
        )
    task_count = await db.scalar(select(func.count(Task.id)).where(Task.area_id == area.id))
    if task_count:
        if move_to is None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Der Bereich enthält noch Aufgaben. Bitte einen Zielbereich wählen.",
            )
        target = await db.get(Area, move_to)
        authorize(user, Action.CREATE, target)
        if move_to == area.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Zielbereich muss ein anderer sein.")
        await db.execute(update(Task).where(Task.area_id == area.id).values(area_id=move_to))
    await db.delete(area)
    await db.commit()
