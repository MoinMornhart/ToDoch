"""Termine im Zeitraum auflösen (Serien, Ausnahmen, geänderte Einzeltermine), Konflikte finden,
Serien teilen."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Area, Event, User
from app.policy import visible_areas
from app.services.event_recurrence import (
    RuleError,
    build_rule,
    expand_all_day,
    expand_timed,
    occurrences_before,
    rule_fields,
)

COPY_FIELDS = (
    "area_id", "title", "description", "location", "url", "all_day", "tzid", "status",
    "transparency", "is_fixed", "source", "tags", "attendees", "reminders", "created_by",
    "contact_id", "channel", "agreed_on", "agreed_with", "priority",
)  # fmt: skip


@dataclass
class Occurrence:
    event: Event  # die Zeile, deren Inhalt gilt (Serie, Einzeltermin oder geändertes Vorkommen)
    start: datetime
    end: datetime
    series_id: uuid.UUID | None
    recurrence_id: datetime | None

    @property
    def key(self) -> str:
        if self.recurrence_id is None:
            return str(self.event.id)
        return f"{self.series_id}:{int(self.recurrence_id.timestamp())}"


def midnight_utc(day: date) -> datetime:
    return datetime.combine(day, time(), tzinfo=UTC)


def window(day_start: date, day_end: date, tzid: str) -> tuple[datetime, datetime]:
    tz = ZoneInfo(tzid)
    return (
        datetime.combine(day_start, time(), tzinfo=tz).astimezone(UTC),
        datetime.combine(day_end, time(), tzinfo=tz).astimezone(UTC),
    )


def _overlaps(start: datetime, end: datetime, lo: datetime, hi: datetime) -> bool:
    if end == start:  # Termin ohne Dauer
        return lo <= start < hi
    return start < hi and end > lo


def _overlaps_days(start: datetime, end: datetime, day_start: date, day_end: date) -> bool:
    return start.date() < day_end and end.date() > day_start


def expand(
    event: Event,
    day_start: date,
    day_end: date,
    lo: datetime,
    hi: datetime,
    overridden: set[datetime] | None = None,
) -> list[Occurrence]:
    """Vorkommen eines Termins im Fenster (Tage für ganztägige, [lo, hi) für zeitgebundene)."""
    duration = event.end_at - event.start_at
    if not event.rrule:
        hit = (
            _overlaps_days(event.start_at, event.end_at, day_start, day_end)
            if event.all_day
            else _overlaps(event.start_at, event.end_at, lo, hi)
        )
        if not hit:
            return []
        return [
            Occurrence(event, event.start_at, event.end_at, event.series_id, event.recurrence_id)
        ]

    skip = {d.astimezone(UTC) for d in event.exdates} | (overridden or set())
    result: list[Occurrence] = []
    if event.all_day:
        span = max(duration.days, 1)
        for day in expand_all_day(
            event.rrule, event.start_at.date(), day_start - timedelta(days=span - 1), day_end
        ):
            begin = midnight_utc(day)
            if begin not in skip:
                result.append(Occurrence(event, begin, begin + duration, event.id, begin))
    else:
        for begin in expand_timed(event.rrule, event.start_at, event.tzid, lo - duration, hi):
            if begin not in skip and _overlaps(begin, begin + duration, lo, hi):
                result.append(Occurrence(event, begin, begin + duration, event.id, begin))
    return result


async def occurrences(
    db: AsyncSession,
    user: User,
    day_start: date,
    day_end: date,
    tzid: str,
    *,
    area_id: uuid.UUID | None = None,
) -> list[Occurrence]:
    lo, hi = window(day_start, day_end, tzid)
    wide_lo, wide_hi = lo - timedelta(days=1), hi + timedelta(days=1)
    base = select(Event).join(Area, Event.area_id == Area.id).where(visible_areas(user))
    if area_id is not None:
        base = base.where(Event.area_id == area_id)

    singles = await db.scalars(
        base.where(
            Event.series_id.is_(None),
            Event.rrule.is_(None),
            Event.start_at < wide_hi,
            Event.end_at >= wide_lo,
        )
    )
    masters = list(
        await db.scalars(
            base.where(
                Event.series_id.is_(None), Event.rrule.is_not(None), Event.start_at < wide_hi
            )
        )
    )
    overrides: list[Event] = []
    if masters:
        overrides = list(await db.scalars(base.where(Event.series_id.in_([m.id for m in masters]))))

    overridden: dict[uuid.UUID, set[datetime]] = {}
    for override in overrides:
        assert override.series_id is not None and override.recurrence_id is not None
        overridden.setdefault(override.series_id, set()).add(override.recurrence_id.astimezone(UTC))

    result: list[Occurrence] = []
    for event in singles:
        result += expand(event, day_start, day_end, lo, hi)
    for master in masters:
        result += expand(master, day_start, day_end, lo, hi, overridden.get(master.id))
    for override in overrides:
        if override.status != "cancelled":
            result += expand(override, day_start, day_end, lo, hi)
    result.sort(key=lambda o: (not o.event.all_day, o.start, o.event.title))
    return result


async def find_conflicts(
    db: AsyncSession, user: User, event: Event, start: datetime, end: datetime
) -> list[Occurrence]:
    """Überschneidungen mit anderen Terminen im selben Bereich (nur zeitgebundene, belegende)."""
    if event.all_day or event.transparency == "transparent" or event.status == "cancelled":
        return []
    tz = ZoneInfo(user.timezone)
    day_start = start.astimezone(tz).date()
    day_end = end.astimezone(tz).date() + timedelta(days=1)
    same = {event.id, event.series_id} - {None}
    return [
        occ
        for occ in await occurrences(
            db, user, day_start, day_end, user.timezone, area_id=event.area_id
        )
        if not occ.event.all_day
        and occ.event.transparency == "opaque"
        and occ.event.status != "cancelled"
        and occ.event.id not in same
        and occ.series_id not in same
        and occ.start < end
        and occ.end > start
    ]


def copy_event(source: Event, **changes: object) -> Event:
    values: dict[str, object] = {name: getattr(source, name) for name in COPY_FIELDS}
    values["tags"] = list(source.tags or [])
    values["attendees"] = list(source.attendees or [])
    values["reminders"] = list(source.reminders or [])
    values["area"] = source.area
    values["contact"] = source.contact
    values.update(changes)
    return Event(**values)


def _until_before(master: Event, occurrence: datetime) -> str:
    if master.all_day:
        return (occurrence.date() - timedelta(days=1)).strftime("%Y%m%d")
    return (occurrence - timedelta(seconds=1)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def truncate_rule(master: Event, occurrence: datetime) -> tuple[str, dict[str, str]]:
    """Regel der Serie so kürzen, dass sie vor ``occurrence`` endet.

    Gibt die gekürzte Regel und die Felder für eine Folgeserie ab ``occurrence`` zurück.
    """
    assert master.rrule is not None
    fields = rule_fields(master.rrule)
    following = dict(fields)
    if "COUNT" in fields:
        used = occurrences_before(
            master.rrule, master.start_at, None if master.all_day else master.tzid, occurrence
        )
        remaining = int(fields["COUNT"]) - used
        if used < 1 or remaining < 1:
            raise RuleError("Dieses Vorkommen gehört nicht zur Serie.")
        fields["COUNT"] = str(used)
        following["COUNT"] = str(remaining)
    else:
        fields["UNTIL"] = _until_before(master, occurrence)
    return build_rule(fields), following


async def split_series(db: AsyncSession, master: Event, occurrence: datetime) -> Event:
    """Teilt eine Serie: ``master`` endet vor ``occurrence``, eine neue Serie beginnt dort."""
    truncated, following = truncate_rule(master, occurrence)
    duration = master.end_at - master.start_at
    new = copy_event(
        master,
        uid=f"{uuid.uuid4()}@todoch",
        start_at=occurrence,
        end_at=occurrence + duration,
        rrule=build_rule(following),
        exdates=[d for d in master.exdates if d >= occurrence],
    )
    master.rrule = truncated
    master.exdates = [d for d in master.exdates if d < occurrence]
    master.sequence += 1
    db.add(new)
    await db.flush()
    moved = await db.scalars(
        select(Event).where(Event.series_id == master.id, Event.recurrence_id >= occurrence)
    )
    for override in moved:
        override.series_id = new.id
        override.uid = new.uid
    return new


async def truncate_series(db: AsyncSession, master: Event, occurrence: datetime) -> None:
    """Serie ab ``occurrence`` beenden (inkl. geänderter Vorkommen danach)."""
    master.rrule, _ = truncate_rule(master, occurrence)
    master.exdates = [d for d in master.exdates if d < occurrence]
    master.sequence += 1
    later = await db.scalars(
        select(Event).where(Event.series_id == master.id, Event.recurrence_id >= occurrence)
    )
    for override in later:
        await db.delete(override)
