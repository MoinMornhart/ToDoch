from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

Detail = Literal["full", "title", "busy"]


class FeedIn(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    area_id: uuid.UUID | None = None
    detail: Detail = "full"


class FeedOut(BaseModel):
    id: uuid.UUID
    name: str
    area_id: uuid.UUID | None
    area_name: str | None
    detail: str
    created_at: datetime
    last_used_at: datetime | None


class FeedCreatedOut(BaseModel):
    feed: FeedOut
    url: str
    webcal_url: str
