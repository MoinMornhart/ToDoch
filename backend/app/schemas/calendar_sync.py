from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints


class ConnectionOut(BaseModel):
    id: uuid.UUID
    provider: str
    account_email: str
    area_id: uuid.UUID
    area_name: str
    enabled: bool
    event_count: int
    last_synced_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None
    created_at: datetime
    # Nur bei CalDAV: Server, z. B. „cloud.example.de“
    server: str | None = None


CalDavUrl = Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=2000)]


class CalDavLogin(BaseModel):
    url: CalDavUrl
    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=320)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=500)]


class CalDavConnectIn(CalDavLogin):
    calendar_url: CalDavUrl
    area_id: uuid.UUID | None = None


class CalDavCalendarOut(BaseModel):
    url: str
    name: str


class ConnectStartIn(BaseModel):
    area_id: uuid.UUID | None = None


class ConnectionPatch(BaseModel):
    enabled: bool | None = None
