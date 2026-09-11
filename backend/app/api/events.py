"""Termine: Zeitraum-Abfrage, Anlegen, Bearbeiten und Löschen (auch „dieses / folgende / alle“)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import select

from app.api.contacts import contact_out, load_contact
from app.api.deps import DB, CurrentUser
from app.api.tasks import area_for_new_item
from app.markdown import render_markdown
from app.models import Area, Event, Task, User
from app.policy import Action, authorize
from app.schemas.events import (
    AttendeeOut,
    ConflictOut,
    EventIn,
    EventOut,
    EventPatch,
    EventWriteOut,
    LinkedTaskOut,
    OccurrenceOut,
    Scope,
)
from app.services.event_recurrence import RuleError
from app.services.events import (
    Occurrence,
    copy_event,
    find_conflicts,
    midnight_utc,
    occurrences,
    split_series,
    truncate_series,
)
from app.services.ics import build_calendar

router = APIRouter(prefix="/api/events", tags=["events"])

DEFAULT_DURATION = timedelta(minutes=60)
MAX_RANGE_DAYS = 400


def _bad(message: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, message)


# --- Umrechnung zwischen Ortszeit des Nutzers und UTC ---------------------------------------


def resolve_times(
    all_day: bool,
    start_date: date,
    start_time: time | None,
    end_date: date | None,
    end_time: time | None,
    tzid: str,
) -> tuple[datetime, datetime]:
    if all_day:
        last = end_date or start_date
        if last < start_date:
            raise _bad("Das Ende liegt vor dem Beginn.")
        return midnight_utc(start_date), midnight_utc(last + timedelta(days=1))
    if start_time is None:
        raise _bad("Bitte eine Uhrzeit angeben oder „ganztägig“ wählen.")
    tz = ZoneInfo(tzid)
    start = datetime.combine(start_date, start_time, tzinfo=tz)
    if end_time is None:
        end = start + DEFAULT_DURATION
    else:
        end = datetime.combine(end_date or start_date, end_time, tzinfo=tz)
    if end < start:
        raise _bad("Das Ende liegt vor dem Beginn.")
    return start.astimezone(UTC), end.astimezone(UTC)


def _local_text(instant: datetime, all_day: bool, tzid: str) -> str:
    if all_day:
        return instant.date().isoformat()
    return instant.astimezone(ZoneInfo(tzid)).strftime("%Y-%m-%dT%H:%M")


def occurrence_out(occ: Occurrence, tzid: str) -> OccurrenceOut:
    event = occ.event
    return OccurrenceOut(
        key=occ.key,
        event_id=event.id,
        series_id=occ.series_id,
        recurrence_id=occ.recurrence_id,
        area_id=event.area_id,
        title=event.title,
        location=event.location,
        all_day=event.all_day,
        status=event.status,
        is_fixed=event.is_fixed,
        recurring=occ.recurrence_id is not None,
        tags=list(event.tags or []),
        start=occ.start,
        end=occ.end,
        start_local=_local_text(occ.start, event.all_day, tzid),
        end_local=_local_text(occ.end, event.all_day, tzid),
    )


def event_out(
    event: Event,
    tzid: str,
    start: datetime | None = None,
    tasks: list[Task] | None = None,
) -> EventOut:
    begin = start or event.start_at
    end = begin + (event.end_at - event.start_at)
    if event.all_day:
        start_date, start_time = begin.date(), None
        end_date, end_time = (end - timedelta(days=1)).date(), None
    else:
        tz = ZoneInfo(tzid)
        local_start, local_end = begin.astimezone(tz), end.astimezone(tz)
        start_date, start_time = local_start.date(), local_start.time().replace(tzinfo=None)
        end_date, end_time = local_end.date(), local_end.time().replace(tzinfo=None)
    return EventOut(
        id=event.id,
        uid=event.uid,
        series_id=event.series_id,
        recurrence_id=event.recurrence_id,
        area_id=event.area_id,
        title=event.title,
        description=event.description,
        description_html=render_markdown(event.description),
        location=event.location,
        url=event.url,
        all_day=event.all_day,
        start_date=start_date,
        start_time=start_time,
        end_date=end_date,
        end_time=end_time,
        tzid=event.tzid,
        rrule=event.rrule,
        status=event.status,
        transparency=event.transparency,
        is_fixed=event.is_fixed,
        source=event.source,
        tags=list(event.tags or []),
        attendees=[
            AttendeeOut(name=a.get("name", ""), email=a.get("email")) for a in event.attendees
        ],
        reminders=list(event.reminders or []),
        sequence=event.sequence,
        contact=contact_out(event.contact) if event.contact else None,
        channel=event.channel,
        agreed_on=event.agreed_on,
        agreed_with=event.agreed_with,
        priority=event.priority,
        tasks=[
            LinkedTaskOut(id=t.id, title=t.title, due_date=t.due_date, status=t.status)
            for t in tasks or []
        ],
        created_at=event.created_at,
        updated_at=event.updated_at,
    )


def conflicts_out(conflicts: list[Occurrence], tzid: str) -> list[ConflictOut]:
    return [
        ConflictOut(
            key=c.key,
            title=c.event.title,
            start_local=_local_text(c.start, False, tzid),
            end_local=_local_text(c.end, False, tzid),
        )
        for c in conflicts
    ]


# --- Laden ---------------------------------------------------------------------------------


async def _load(db: DB, user: User, event_id: uuid.UUID, action: Action) -> Event:
    event = await db.get(Event, event_id)
    authorize(user, action, event)
    assert event is not None
    return event


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


async def _override(db: DB, master: Event, occurrence: datetime) -> Event | None:
    found: Event | None = await db.scalar(
        select(Event).where(Event.series_id == master.id, Event.recurrence_id == occurrence)
    )
    return found


# --- Endpunkte -----------------------------------------------------------------------------


@router.get("", response_model=list[OccurrenceOut])
async def list_events(
    db: DB,
    user: CurrentUser,
    start: Annotated[date, Query(alias="from")],
    end: Annotated[date, Query(alias="to")],
    area_id: uuid.UUID | None = None,
) -> list[OccurrenceOut]:
    if end <= start or (end - start).days > MAX_RANGE_DAYS:
        raise _bad(f"Zeitraum muss zwischen 1 und {MAX_RANGE_DAYS} Tagen liegen.")
    found = await occurrences(db, user, start, end, user.timezone, area_id=area_id)
    return [occurrence_out(occ, user.timezone) for occ in found]


async def create_event_row(
    db: DB, user: User, body: EventIn, *, source: str = "manual"
) -> tuple[Event, list[Occurrence]]:
    """Legt den Termin an (ohne Commit) und liefert Überschneidungen im selben Bereich."""
    area = await area_for_new_item(db, user, body.area_id)
    contact = await load_contact(db, user, body.contact_id) if body.contact_id else None
    tzid = body.tzid or user.timezone
    start, end = resolve_times(
        body.all_day, body.start_date, body.start_time, body.end_date, body.end_time, tzid
    )
    event = Event(
        area_id=area.id,
        area=area,
        created_by=user.id,
        uid=f"{uuid.uuid4()}@todoch",
        title=body.title,
        description=body.description,
        location=body.location,
        url=body.url,
        start_at=start,
        end_at=end,
        all_day=body.all_day,
        tzid=tzid,
        rrule=body.rrule,
        exdates=[],
        status=body.status,
        transparency=body.transparency,
        is_fixed=body.is_fixed,
        source=source,
        contact_id=contact.id if contact else None,
        contact=contact,
        channel=body.channel,
        agreed_on=body.agreed_on,
        agreed_with=body.agreed_with,
        priority=body.priority,
        tags=body.tags,
        attendees=[a.model_dump(mode="json") for a in body.attendees],
        reminders=sorted(set(body.reminders)),
    )
    db.add(event)
    await db.flush()
    return event, await find_conflicts(db, user, event, start, end)


@router.post("", response_model=EventWriteOut, status_code=status.HTTP_201_CREATED)
async def create_event(body: EventIn, db: DB, user: CurrentUser) -> EventWriteOut:
    event, conflicts = await create_event_row(db, user, body)
    await db.commit()
    return EventWriteOut(
        event=event_out(event, user.timezone),
        conflicts=conflicts_out(conflicts, user.timezone),
    )


async def _linked_tasks(db: DB, event: Event) -> list[Task]:
    """Aufgaben zum Termin – bei Serien die der ganzen Serie."""
    ids = {event.id, event.series_id} - {None}
    found = await db.scalars(
        select(Task)
        .where(Task.event_id.in_(ids), Task.area_id == event.area_id)
        .order_by(Task.due_date.asc().nulls_last(), Task.created_at)
    )
    return list(found.unique())


@router.get("/{event_id}", response_model=EventOut)
async def get_event(
    event_id: uuid.UUID,
    db: DB,
    user: CurrentUser,
    occurrence: datetime | None = None,
) -> EventOut:
    event = await _load(db, user, event_id, Action.VIEW)
    tasks = await _linked_tasks(db, event)
    occ = _utc(occurrence)
    if event.rrule and occ is not None:
        override = await _override(db, event, occ)
        if override is not None:
            return event_out(override, user.timezone, tasks=tasks)
        return event_out(event, user.timezone, start=occ, tasks=tasks)
    return event_out(event, user.timezone, tasks=tasks)


@router.get("/{event_id}/ics")
async def event_ics(
    event_id: uuid.UUID,
    db: DB,
    user: CurrentUser,
    detail: Literal["full", "public"] = "public",
) -> Response:
    """Einzelner Termin (bei Serien mit allen Ausnahmen) als .ics-Datei zum Weitergeben.

    Standard ist ``public``: ohne Beschreibung, damit interne Gesprächsnotizen nicht beim
    Gegenüber landen."""
    event = await _load(db, user, event_id, Action.VIEW)
    if event.series_id is not None:
        event = await _load(db, user, event.series_id, Action.VIEW)
    items = [event]
    if event.rrule:
        items += list(await db.scalars(select(Event).where(Event.series_id == event.id)))
    body = build_calendar(items, name=event.title, detail=detail)
    return Response(
        body,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="termin.ics"',
            "Cache-Control": "no-store",
        },
    )


def _apply_fields(event: Event, body: EventPatch) -> None:
    fields = body.model_fields_set
    simple = (
        "title",
        "description",
        "location",
        "url",
        "status",
        "transparency",
        "is_fixed",
        "agreed_with",
        "priority",
        "tzid",
    )
    for name in simple:
        value = getattr(body, name)
        if name in fields and value is not None:
            setattr(event, name, value)
    for name in ("channel", "agreed_on"):  # dürfen geleert werden
        if name in fields:
            setattr(event, name, getattr(body, name))
    if "tags" in fields and body.tags is not None:
        event.tags = body.tags
    if "attendees" in fields and body.attendees is not None:
        event.attendees = [a.model_dump(mode="json") for a in body.attendees]
    if "reminders" in fields and body.reminders is not None:
        event.reminders = sorted(set(body.reminders))
    if "rrule" in fields and event.series_id is None:
        event.rrule = body.rrule


def _new_times(event: Event, body: EventPatch, tzid: str) -> tuple[datetime, datetime] | None:
    if "start_date" not in body.model_fields_set or body.start_date is None:
        return None
    all_day = event.all_day if body.all_day is None else body.all_day
    return resolve_times(
        all_day, body.start_date, body.start_time, body.end_date, body.end_time, body.tzid or tzid
    )


async def _shift_series(db: DB, master: Event, delta: timedelta) -> None:
    """Alle Vorkommen verschieben: Ausnahmen und geänderte Einzeltermine wandern mit."""
    master.exdates = [d + delta for d in master.exdates]
    for override in await db.scalars(select(Event).where(Event.series_id == master.id)):
        assert override.recurrence_id is not None
        if override.start_at == override.recurrence_id:
            # Nur inhaltlich geändert – die Uhrzeit folgt der Serie.
            override.start_at += delta
            override.end_at += delta
        override.recurrence_id = override.recurrence_id + delta


@router.patch("/{event_id}", response_model=EventWriteOut)
async def update_event(
    event_id: uuid.UUID,
    body: EventPatch,
    db: DB,
    user: CurrentUser,
    scope: Scope = "all",
    occurrence: datetime | None = None,
) -> EventWriteOut:
    event = await _load(db, user, event_id, Action.EDIT)
    occ = _utc(occurrence)

    # Geändertes Vorkommen: „folgende“/„alle“ wirken auf die Serie.
    if event.series_id is not None and scope != "this":
        occ = event.recurrence_id
        event = await _load(db, user, event.series_id, Action.EDIT)

    target = event
    if event.rrule and occ is not None and scope == "this":
        override = await _override(db, event, occ)
        if override is None:
            override = copy_event(
                event,
                uid=event.uid,
                series_id=event.id,
                recurrence_id=occ,
                start_at=occ,
                end_at=occ + (event.end_at - event.start_at),
                rrule=None,
                exdates=[],
            )
            db.add(override)
            await db.flush()
        target = override
    elif event.rrule and occ is not None and scope == "following" and occ > event.start_at:
        try:
            target = await split_series(db, event, occ)
        except RuleError as exc:
            raise _bad(str(exc)) from exc

    if "area_id" in body.model_fields_set and body.area_id and body.area_id != target.area_id:
        new_area = await db.get(Area, body.area_id)
        authorize(user, Action.CREATE, new_area)
        assert new_area is not None
        target.area_id, target.area = new_area.id, new_area

    if "contact_id" in body.model_fields_set and body.contact_id != target.contact_id:
        contact = await load_contact(db, user, body.contact_id) if body.contact_id else None
        target.contact_id, target.contact = (contact.id if contact else None), contact

    _apply_fields(target, body)
    times = _new_times(target, body, user.timezone)
    if times is not None:
        new_start, new_end = times
        all_day = target.all_day if body.all_day is None else body.all_day
        if target is event and event.rrule and occ is not None and all_day == event.all_day:
            # „Alle“ von einem Vorkommen aus: um dieselbe Differenz verschieben.
            delta = new_start - occ
            if delta:
                await _shift_series(db, event, delta)
            event.start_at = event.start_at + delta
            event.end_at = event.start_at + (new_end - new_start)
        else:
            target.start_at, target.end_at = new_start, new_end
        target.all_day = all_day
    target.sequence += 1
    await db.flush()

    conflicts = await find_conflicts(db, user, target, target.start_at, target.end_at)
    await db.commit()
    await db.refresh(target)
    return EventWriteOut(
        event=event_out(target, user.timezone, tasks=await _linked_tasks(db, target)),
        conflicts=conflicts_out(conflicts, user.timezone),
    )


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: uuid.UUID,
    db: DB,
    user: CurrentUser,
    scope: Scope = "all",
    occurrence: datetime | None = None,
) -> None:
    event = await _load(db, user, event_id, Action.DELETE)
    occ = _utc(occurrence)

    if event.series_id is not None:  # geändertes Vorkommen
        master = await _load(db, user, event.series_id, Action.DELETE)
        assert event.recurrence_id is not None
        if scope == "this":
            master.exdates = [*master.exdates, event.recurrence_id]
            await db.delete(event)
        elif scope == "following":
            await _truncate_or_delete(db, master, event.recurrence_id)
        else:
            await db.delete(master)
    elif event.rrule and occ is not None and scope == "this":
        event.exdates = [*event.exdates, occ]
        event.sequence += 1
        override = await _override(db, event, occ)
        if override is not None:
            await db.delete(override)
    elif event.rrule and occ is not None and scope == "following":
        await _truncate_or_delete(db, event, occ)
    else:
        await db.delete(event)
    await db.commit()


async def _truncate_or_delete(db: DB, master: Event, occurrence: datetime) -> None:
    if occurrence <= master.start_at:
        await db.delete(master)
        return
    try:
        await truncate_series(db, master, occurrence)
    except RuleError as exc:
        raise _bad(str(exc)) from exc
