from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

CalendarName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
CalendarUrl = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=8, max_length=2000)
]
Refresh = Annotated[int, Field(ge=15, le=1440)]


class CalendarIn(BaseModel):
    name: CalendarName
    url: CalendarUrl
    area_id: uuid.UUID | None = None
    refresh_minutes: Refresh = 60


class CalendarPatch(BaseModel):
    name: CalendarName | None = None
    url: CalendarUrl | None = None
    area_id: uuid.UUID | None = None
    refresh_minutes: Refresh | None = None
    enabled: bool | None = None


class CalendarOut(BaseModel):
    id: uuid.UUID
    name: str
    host: str
    area_id: uuid.UUID
    area_name: str
    refresh_minutes: int
    enabled: bool
    event_count: int
    last_synced_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None
    created_at: datetime
