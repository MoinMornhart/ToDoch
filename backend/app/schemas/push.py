from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, StringConstraints

from app.services.push import endpoint_allowed

_B64URL = r"^[A-Za-z0-9_-]+=*$"


def _allowed(url: str) -> str:
    if not endpoint_allowed(url):
        raise ValueError("Unbekannter Push-Dienst")
    return url


Endpoint = Annotated[str, StringConstraints(max_length=1000), AfterValidator(_allowed)]


class SubscriptionKeys(BaseModel):
    p256dh: Annotated[str, StringConstraints(pattern=_B64URL, min_length=40, max_length=200)]
    auth: Annotated[str, StringConstraints(pattern=_B64URL, min_length=16, max_length=64)]


class SubscriptionIn(BaseModel):
    endpoint: Endpoint
    keys: SubscriptionKeys


class UnsubscribeIn(BaseModel):
    endpoint: Annotated[str, StringConstraints(max_length=1000)]


class SubscriptionOut(BaseModel):
    id: uuid.UUID
    user_agent: str | None
    created_at: datetime
    last_success_at: datetime | None


class PushKeyOut(BaseModel):
    public_key: str


class PushTestOut(BaseModel):
    delivered: int
