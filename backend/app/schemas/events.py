from __future__ import annotations

import uuid
from datetime import date, datetime, time
from functools import lru_cache
from typing import Annotated, Literal
from zoneinfo import available_timezones

from pydantic import AfterValidator, BaseModel, EmailStr, Field, StringConstraints, field_validator

from app.schemas.contacts import ContactOut
from app.schemas.tasks import MAX_NOTES, Priority, Tags, TaskOut, Title
from app.services.event_recurrence import normalize_event_rule

Status = Literal["tentative", "confirmed", "cancelled"]
Channel = Literal["phone", "in_person", "mail", "other"]
AgreedWith = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]


@lru_cache(maxsize=1)
def _zones() -> frozenset[str]:
    return frozenset(available_timezones())


def _zone(value: str | None) -> str | None:
    if value is not None and value not in _zones():
        raise ValueError("Unbekannte Zeitzone")
    return value


Zone = Annotated[str | None, Field(max_length=64), AfterValidator(_zone)]
Transparency = Literal["opaque", "transparent"]
Reminder = Annotated[int, Field(ge=0, le=60 * 24 * 28)]
Scope = Literal["this", "following", "all"]


def _rule(value: str | None) -> str | None:
    return normalize_event_rule(value)


Rule = Annotated[str | None, Field(max_length=300), AfterValidator(_rule)]
Url = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]


class AttendeeIn(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] = ""
    email: EmailStr | None = None


class _Fields(BaseModel):
    @field_validator("url", check_fields=False)
    @classmethod
    def _http_url(cls, value: str | None) -> str | None:
        if value and not value.lower().startswith(("https://", "http://")):
            raise ValueError("Link muss mit http:// oder https:// beginnen")
        return value


class EventIn(_Fields):
    title: Title
    description: Annotated[str, Field(max_length=MAX_NOTES)] = ""
    location: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] = ""
    url: Url = ""
    area_id: uuid.UUID | None = None
    all_day: bool = False
    start_date: date
    start_time: time | None = None
    end_date: date | None = None
    end_time: time | None = None
    rrule: Rule = None
    status: Status = "confirmed"
    transparency: Transparency = "opaque"
    is_fixed: bool = False
    tags: Tags = []
    attendees: Annotated[list[AttendeeIn], Field(max_length=50)] = []
    reminders: Annotated[list[Reminder], Field(max_length=10)] = []
    # Leer = Zeitzone des Nutzers
    tzid: Zone = None
    contact_id: uuid.UUID | None = None
    channel: Channel | None = None
    agreed_on: date | None = None
    agreed_with: AgreedWith = ""
    priority: Priority = 0


class EventPatch(_Fields):
    title: Title | None = None
    description: Annotated[str, Field(max_length=MAX_NOTES)] | None = None
    location: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None
    url: Url | None = None
    area_id: uuid.UUID | None = None
    all_day: bool | None = None
    start_date: date | None = None
    start_time: time | None = None
    end_date: date | None = None
    end_time: time | None = None
    rrule: Rule = None
    status: Status | None = None
    transparency: Transparency | None = None
    is_fixed: bool | None = None
    tags: Tags | None = None
    attendees: Annotated[list[AttendeeIn], Field(max_length=50)] | None = None
    reminders: Annotated[list[Reminder], Field(max_length=10)] | None = None
    tzid: Zone = None
    contact_id: uuid.UUID | None = None
    channel: Channel | None = None
    agreed_on: date | None = None
    agreed_with: AgreedWith | None = None
    priority: Priority | None = None


class AttendeeOut(BaseModel):
    name: str
    email: str | None


class LinkedTaskOut(BaseModel):
    id: uuid.UUID
    title: str
    due_date: date | None
    status: str


class EventOut(BaseModel):
    id: uuid.UUID
    uid: str
    series_id: uuid.UUID | None
    recurrence_id: datetime | None
    area_id: uuid.UUID
    title: str
    description: str
    description_html: str
    location: str
    url: str
    all_day: bool
    start_date: date
    start_time: time | None
    end_date: date
    end_time: time | None
    tzid: str
    rrule: str | None
    status: str
    transparency: str
    is_fixed: bool
    source: str
    tags: list[str]
    attendees: list[AttendeeOut]
    reminders: list[int]
    sequence: int
    contact: ContactOut | None
    channel: str | None
    agreed_on: date | None
    agreed_with: str
    priority: int
    tasks: list[LinkedTaskOut] = []
    created_at: datetime
    updated_at: datetime


class OccurrenceOut(BaseModel):
    key: str
    event_id: uuid.UUID
    series_id: uuid.UUID | None
    recurrence_id: datetime | None
    area_id: uuid.UUID
    title: str
    location: str
    all_day: bool
    status: str
    is_fixed: bool
    recurring: bool
    tags: list[str]
    start: datetime
    end: datetime
    start_local: str
    end_local: str


class ConflictOut(BaseModel):
    key: str
    title: str
    start_local: str
    end_local: str


class EventWriteOut(BaseModel):
    event: EventOut
    conflicts: list[ConflictOut]


class EventSearchOut(BaseModel):
    id: uuid.UUID
    title: str
    location: str
    all_day: bool
    recurring: bool
    start_local: str


class SearchOut(BaseModel):
    tasks: list[TaskOut]
    events: list[EventSearchOut]
