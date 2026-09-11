from __future__ import annotations

import uuid
from datetime import date, datetime, time
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, StringConstraints, model_validator

from app.services.recurrence import normalize_recurrence

MAX_NOTES = 50_000

Tag = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, to_lower=True, min_length=1, max_length=40, pattern=r"^[\w-]+$"
    ),
]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
Priority = Annotated[int, Field(ge=0, le=3)]
Status = Literal["open", "done", "archived"]


def _dedupe(tags: list[str]) -> list[str]:
    return list(dict.fromkeys(tags))


def _recurrence(value: str | None) -> str | None:
    return normalize_recurrence(value)


Tags = Annotated[list[Tag], Field(max_length=20), AfterValidator(_dedupe)]
RecurrenceRule = Annotated[str | None, Field(max_length=200), AfterValidator(_recurrence)]


class ChecklistItemIn(BaseModel):
    id: uuid.UUID | None = None
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
    done: bool = False


class ChecklistItemOut(BaseModel):
    id: uuid.UUID
    text: str
    done: bool


class _TaskFields(BaseModel):
    @model_validator(mode="after")
    def _time_needs_date(self) -> _TaskFields:
        time_without_date = (
            getattr(self, "due_time", None) is not None and getattr(self, "due_date", None) is None
        )
        if time_without_date and ("due_date" in self.model_fields_set or isinstance(self, TaskIn)):
            raise ValueError("Eine Uhrzeit braucht ein Datum.")
        return self


class TaskIn(_TaskFields):
    title: Title
    notes: Annotated[str, Field(max_length=MAX_NOTES)] = ""
    area_id: uuid.UUID | None = None
    due_date: date | None = None
    due_time: time | None = None
    priority: Priority = 0
    tags: Tags = []
    recurrence: RecurrenceRule = None
    checklist: Annotated[list[ChecklistItemIn], Field(max_length=100)] = []


class TaskPatch(_TaskFields):
    title: Title | None = None
    notes: Annotated[str, Field(max_length=MAX_NOTES)] | None = None
    area_id: uuid.UUID | None = None
    due_date: date | None = None
    due_time: time | None = None
    priority: Priority | None = None
    tags: Tags | None = None
    recurrence: RecurrenceRule = None
    status: Status | None = None
    checklist: Annotated[list[ChecklistItemIn], Field(max_length=100)] | None = None
    sort_order: Annotated[int, Field(ge=0, le=1_000_000)] | None = None


class TaskOut(BaseModel):
    id: uuid.UUID
    area_id: uuid.UUID
    title: str
    notes: str
    notes_html: str
    due_date: date | None
    due_time: time | None
    priority: int
    status: str
    completed_at: datetime | None
    tags: list[str]
    recurrence: str | None
    source: str
    event_id: uuid.UUID | None
    sort_order: int
    checklist: list[ChecklistItemOut]
    created_at: datetime
    updated_at: datetime


class CompleteOut(BaseModel):
    task: TaskOut
    next: TaskOut | None


class QuickAddIn(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    area_id: uuid.UUID | None = None


class QuickAddPreview(BaseModel):
    title: str
    due_date: date | None
    due_time: time | None
    priority: int
    tags: list[str]
    area_id: uuid.UUID | None
    area_name: str | None
    area_unknown: bool
    recurrence: str | None
    tokens: list[str]
