from __future__ import annotations

import uuid
from typing import Annotated

from pydantic import BaseModel, Field

from app.schemas.contacts import ContactIn, ContactOut
from app.schemas.events import ConflictOut, EventIn, EventOut
from app.schemas.tasks import Priority, TaskOut, Title


class FollowUpIn(BaseModel):
    """Folgeaufgabe, z. B. „Unterlagen vorbereiten“ – fällig X Tage vor dem Termin."""

    title: Title
    days_before: Annotated[int, Field(ge=0, le=365)] = 1
    priority: Priority = 0


class AppointmentIn(BaseModel):
    """Telefontermin: Kontakt (vorhanden oder neu), Termin und optionale Folgeaufgabe."""

    contact_id: uuid.UUID | None = None
    contact: ContactIn | None = None
    event: EventIn
    follow_up: FollowUpIn | None = None


class AppointmentOut(BaseModel):
    event: EventOut
    task: TaskOut | None
    contact: ContactOut | None
    conflicts: list[ConflictOut]
