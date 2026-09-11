"""Aufgaben: Listen-Ansichten, CRUD, Schnellerfassung, Abhaken, Suche."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import Select, func, or_, select

from app.api.deps import DB, CurrentUser, user_now, user_today
from app.markdown import render_markdown
from app.models import Area, ChecklistItem, Event, Task, User
from app.policy import Action, authorize, visible_areas
from app.quickadd import parse_quick_add
from app.schemas.events import EventSearchOut, SearchOut
from app.schemas.tasks import (
    ChecklistItemIn,
    ChecklistItemOut,
    CompleteOut,
    QuickAddIn,
    QuickAddPreview,
    TaskIn,
    TaskOut,
    TaskPatch,
)
from app.services.recurrence import parse_recurrence

router = APIRouter(prefix="/api", tags=["tasks"])

View = Literal["today", "upcoming", "open", "done", "archived", "all"]


def task_out(task: Task) -> TaskOut:
    return TaskOut(
        id=task.id,
        area_id=task.area_id,
        title=task.title,
        notes=task.notes,
        notes_html=render_markdown(task.notes),
        due_date=task.due_date,
        due_time=task.due_time,
        priority=task.priority,
        status=task.status,
        completed_at=task.completed_at,
        tags=list(task.tags or []),
        recurrence=task.recurrence,
        source=task.source,
        event_id=task.event_id,
        sort_order=task.sort_order,
        checklist=[ChecklistItemOut(id=i.id, text=i.text, done=i.done) for i in task.checklist],
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _visible_tasks(user: User) -> Select[tuple[Task]]:
    return select(Task).join(Area, Task.area_id == Area.id).where(visible_areas(user))


async def _default_area(db: DB, user: User) -> Area:
    area = await db.scalar(
        select(Area).where(visible_areas(user)).order_by(Area.sort_order, Area.name).limit(1)
    )
    if area is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Bitte zuerst einen Bereich anlegen.")
    return area


async def area_for_new_item(db: DB, user: User, area_id: uuid.UUID | None) -> Area:
    if area_id is None:
        area = await _default_area(db, user)
    else:
        found = await db.get(Area, area_id)
        authorize(user, Action.CREATE, found)
        assert found is not None
        area = found
    authorize(user, Action.CREATE, area)
    return area


async def _load_task(db: DB, user: User, task_id: uuid.UUID, action: Action) -> Task:
    task = await db.get(Task, task_id)
    authorize(user, action, task)
    assert task is not None
    return task


def _apply_checklist(task: Task, items: list[ChecklistItemIn]) -> None:
    existing = {item.id: item for item in task.checklist}
    updated: list[ChecklistItem] = []
    for position, incoming in enumerate(items):
        item = existing.pop(incoming.id, None) if incoming.id else None
        if item is None:
            item = ChecklistItem(text=incoming.text, done=incoming.done, position=position)
        else:
            item.text, item.done, item.position = incoming.text, incoming.done, position
        updated.append(item)
    task.checklist = updated


@router.get("/tasks", response_model=list[TaskOut])
async def list_tasks(
    db: DB,
    user: CurrentUser,
    view: View = "open",
    area_id: uuid.UUID | None = None,
    day: date | None = None,
    tag: str | None = Query(default=None, max_length=40),
    limit: int = Query(default=300, ge=1, le=1000),
    start: Annotated[date | None, Query(alias="from")] = None,
    end: Annotated[date | None, Query(alias="to")] = None,
) -> list[TaskOut]:
    today = user_today(user)
    query = _visible_tasks(user)
    if area_id is not None:
        query = query.where(Task.area_id == area_id)
    if tag:
        query = query.where(Task.tags.contains([tag.lower()]))

    open_order = (
        Task.due_date.asc().nulls_last(),
        Task.due_time.asc().nulls_last(),
        Task.priority.desc(),
        Task.sort_order,
        Task.created_at,
    )
    if start is not None and end is not None:
        # Zeitraum (z. B. für den Kalender): offene und erledigte Aufgaben mit Fälligkeit darin
        query = query.where(
            Task.due_date >= start, Task.due_date < end, Task.status != "archived"
        ).order_by(*open_order)
    elif day is not None:
        query = query.where(Task.due_date == day, Task.status != "archived").order_by(
            Task.status.desc(), *open_order
        )
    elif view == "today":
        query = query.where(Task.status == "open", Task.due_date <= today).order_by(*open_order)
    elif view == "upcoming":
        query = query.where(
            Task.status == "open",
            Task.due_date > today,
            Task.due_date <= today + timedelta(days=7),
        ).order_by(*open_order)
    elif view == "open":
        query = query.where(Task.status == "open").order_by(*open_order)
    elif view in ("done", "archived"):
        query = query.where(Task.status == view).order_by(Task.completed_at.desc().nulls_last())
    else:
        query = query.order_by(Task.created_at.desc())
    tasks = (await db.scalars(query.limit(limit))).unique()
    return [task_out(t) for t in tasks]


@router.post("/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(body: TaskIn, db: DB, user: CurrentUser) -> TaskOut:
    area = await area_for_new_item(db, user, body.area_id)
    task = Task(
        area_id=area.id,
        area=area,
        created_by=user.id,
        title=body.title,
        notes=body.notes,
        due_date=body.due_date,
        due_time=body.due_time,
        priority=body.priority,
        tags=body.tags,
        recurrence=body.recurrence,
        checklist=[],
    )
    _apply_checklist(task, body.checklist)
    db.add(task)
    await db.commit()
    return task_out(task)


async def _resolve_quick_area(
    db: DB, user: User, name: str | None, fallback: uuid.UUID | None
) -> tuple[Area, bool]:
    if name:
        areas = list(await db.scalars(select(Area).where(visible_areas(user))))
        wanted = name.casefold()
        exact = [a for a in areas if a.name.casefold() == wanted]
        prefix = [a for a in areas if a.name.casefold().startswith(wanted)]
        match = exact or (prefix if len(prefix) == 1 else [])
        if match:
            authorize(user, Action.CREATE, match[0])
            return match[0], False
        return await area_for_new_item(db, user, fallback), True
    return await area_for_new_item(db, user, fallback), False


@router.post("/tasks/quick/preview", response_model=QuickAddPreview)
async def quick_add_preview(body: QuickAddIn, db: DB, user: CurrentUser) -> QuickAddPreview:
    parsed = parse_quick_add(body.text, user_now(user))
    area, unknown = await _resolve_quick_area(db, user, parsed.area, body.area_id)
    return QuickAddPreview(
        title=parsed.title,
        due_date=parsed.due_date,
        due_time=parsed.due_time,
        priority=parsed.priority,
        tags=parsed.tags,
        area_id=area.id,
        area_name=area.name,
        area_unknown=unknown,
        recurrence=parsed.recurrence,
        tokens=parsed.tokens,
    )


@router.post("/tasks/quick", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def quick_add(body: QuickAddIn, db: DB, user: CurrentUser) -> TaskOut:
    parsed = parse_quick_add(body.text, user_now(user))
    area, _ = await _resolve_quick_area(db, user, parsed.area, body.area_id)
    task = Task(
        area_id=area.id,
        area=area,
        created_by=user.id,
        title=parsed.title,
        due_date=parsed.due_date,
        due_time=parsed.due_time,
        priority=parsed.priority,
        tags=parsed.tags,
        recurrence=parsed.recurrence,
        checklist=[],
    )
    db.add(task)
    await db.commit()
    return task_out(task)


@router.get("/tasks/{task_id}", response_model=TaskOut)
async def get_task(task_id: uuid.UUID, db: DB, user: CurrentUser) -> TaskOut:
    return task_out(await _load_task(db, user, task_id, Action.VIEW))


@router.patch("/tasks/{task_id}", response_model=TaskOut)
async def update_task(task_id: uuid.UUID, body: TaskPatch, db: DB, user: CurrentUser) -> TaskOut:
    task = await _load_task(db, user, task_id, Action.EDIT)
    fields = body.model_fields_set
    nullable = {"due_date", "due_time", "recurrence"}

    if "area_id" in fields and body.area_id is not None and body.area_id != task.area_id:
        target = await db.get(Area, body.area_id)
        authorize(user, Action.CREATE, target)
        assert target is not None
        task.area_id, task.area = target.id, target

    for field in ("title", "notes", "priority", "tags", "sort_order", *nullable):
        if field not in fields:
            continue
        value = getattr(body, field)
        if value is None and field not in nullable:
            continue
        setattr(task, field, value)

    if "status" in fields and body.status is not None and body.status != task.status:
        task.status = body.status
        task.completed_at = datetime.now(UTC) if body.status == "done" else None
    if "checklist" in fields and body.checklist is not None:
        _apply_checklist(task, body.checklist)
    if task.due_time is not None and task.due_date is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Eine Uhrzeit braucht ein Datum."
        )
    await db.commit()
    return task_out(task)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: uuid.UUID, db: DB, user: CurrentUser) -> None:
    task = await _load_task(db, user, task_id, Action.DELETE)
    await db.delete(task)
    await db.commit()


@router.post("/tasks/{task_id}/complete", response_model=CompleteOut)
async def complete_task(task_id: uuid.UUID, db: DB, user: CurrentUser) -> CompleteOut:
    task = await _load_task(db, user, task_id, Action.EDIT)
    if task.status == "done":
        return CompleteOut(task=task_out(task), next=None)
    task.status = "done"
    task.completed_at = datetime.now(UTC)

    following: Task | None = None
    if task.recurrence:
        rule = parse_recurrence(task.recurrence)
        today = user_today(user)
        next_date = rule.next_after(task.due_date or today, today)
        if next_date is not None:
            following = Task(
                area_id=task.area_id,
                area=task.area,
                created_by=user.id,
                title=task.title,
                notes=task.notes,
                due_date=next_date,
                due_time=task.due_time,
                priority=task.priority,
                tags=list(task.tags or []),
                recurrence=task.recurrence,
                source=task.source,
                sort_order=task.sort_order,
                checklist=[
                    ChecklistItem(text=i.text, done=False, position=i.position)
                    for i in task.checklist
                ],
            )
            db.add(following)
        # Die Wiederholung wandert zur nächsten Aufgabe – so entsteht nie ein Duplikat.
        task.recurrence = None
    await db.commit()
    return CompleteOut(task=task_out(task), next=task_out(following) if following else None)


@router.post("/tasks/{task_id}/reopen", response_model=TaskOut)
async def reopen_task(task_id: uuid.UUID, db: DB, user: CurrentUser) -> TaskOut:
    task = await _load_task(db, user, task_id, Action.EDIT)
    task.status = "open"
    task.completed_at = None
    await db.commit()
    return task_out(task)


def _event_search_out(event: Event, tzid: str) -> EventSearchOut:
    start = (
        event.start_at.date().isoformat()
        if event.all_day
        else event.start_at.astimezone(ZoneInfo(tzid)).strftime("%Y-%m-%dT%H:%M")
    )
    return EventSearchOut(
        id=event.id,
        title=event.title,
        location=event.location,
        all_day=event.all_day,
        recurring=event.rrule is not None,
        start_local=start,
    )


@router.get("/search", response_model=SearchOut)
async def search(
    db: DB,
    user: CurrentUser,
    q: str = Query(min_length=1, max_length=200),
    area_id: uuid.UUID | None = None,
) -> SearchOut:
    terms = re.findall(r"\w+", q.lower())[:8]
    if not terms:
        return SearchOut(tasks=[], events=[])
    ts_query = func.to_tsquery("simple", " & ".join(f"{t}:*" for t in terms))
    tasks = _visible_tasks(user).where(
        or_(Task.search_vector.op("@@")(ts_query), Task.tags.overlap(terms))
    )
    events = (
        select(Event)
        .join(Area, Event.area_id == Area.id)
        .where(visible_areas(user), Event.series_id.is_(None))
        .where(or_(Event.search_vector.op("@@")(ts_query), Event.tags.overlap(terms)))
    )
    if area_id is not None:
        tasks = tasks.where(Task.area_id == area_id)
        events = events.where(Event.area_id == area_id)
    tasks = tasks.order_by(
        (Task.status == "open").desc(), func.ts_rank(Task.search_vector, ts_query).desc()
    ).limit(50)
    events = events.order_by(Event.start_at.desc()).limit(20)
    return SearchOut(
        tasks=[task_out(t) for t in (await db.scalars(tasks)).unique()],
        events=[_event_search_out(e, user.timezone) for e in await db.scalars(events)],
    )
