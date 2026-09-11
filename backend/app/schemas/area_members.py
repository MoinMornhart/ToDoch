from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

MemberRole = Literal["admin", "member", "viewer"]
InviteToken = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=20, max_length=100)
]


class MemberOut(BaseModel):
    id: uuid.UUID | None  # None: Besitzer (kein eigener Eintrag)
    display_name: str
    role: str
    you: bool


class MemberPatch(BaseModel):
    role: MemberRole | None = None


class InviteIn(BaseModel):
    role: MemberRole = "member"


class InviteOut(BaseModel):
    id: uuid.UUID
    role: str
    created_at: datetime
    expires_at: datetime


class InviteCreatedOut(BaseModel):
    invite: InviteOut
    url: str


class InviteTokenIn(BaseModel):
    token: InviteToken


class InvitePreviewOut(BaseModel):
    area_name: str
    role: str
    invited_by: str
    already_member: bool
