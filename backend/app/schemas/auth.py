from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, StringConstraints

_TZ_PATTERN = re.compile(r"^(UTC|[A-Za-z_]+(/[A-Za-z0-9_+\-]+){1,2})$")


def _check_timezone(value: str) -> str:
    if not _TZ_PATTERN.match(value):
        raise ValueError("Unbekannte Zeitzone")
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("Unbekannte Zeitzone") from exc
    return value


def _normalize_email(value: str) -> str:
    return value.strip().lower()


Email = Annotated[EmailStr, AfterValidator(_normalize_email)]
Timezone = Annotated[str, Field(max_length=64), AfterValidator(_check_timezone)]
DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Password = Annotated[str, Field(min_length=1, max_length=256)]
Locale = Literal["de", "en"]


class MetaOut(BaseModel):
    version: str
    setup_required: bool
    rp_id: str


class SetupIn(BaseModel):
    setup_token: str | None = Field(default=None, max_length=200)
    email: Email
    display_name: DisplayName
    password: Password
    timezone: Timezone = "Europe/Berlin"
    locale: Locale = "de"


class LoginIn(BaseModel):
    email: Email
    password: Password


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    is_admin: bool
    timezone: str
    locale: str


class MePatch(BaseModel):
    display_name: DisplayName | None = None
    timezone: Timezone | None = None
    locale: Locale | None = None


class PasswordChangeIn(BaseModel):
    # Für Admins optional – alle anderen müssen ihr aktuelles Passwort bestätigen
    current_password: Password | None = None
    new_password: Password


class SessionOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    last_seen_at: datetime
    ip: str | None
    user_agent: str | None
    auth_method: str
    current: bool
