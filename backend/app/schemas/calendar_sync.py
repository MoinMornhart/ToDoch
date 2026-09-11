from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


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


class ConnectStartIn(BaseModel):
    area_id: uuid.UUID | None = None


class ConnectionPatch(BaseModel):
    enabled: bool | None = None
