from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, Field, StringConstraints

from app.schemas.auth import Password

PasskeyName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
ChallengeId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{16,64}$")]
# Rohdaten aus navigator.credentials.* (JSON-kodiert) – geprüft von py_webauthn
Credential = Annotated[dict[str, Any], Field(max_length=10)]


class RegisterOptionsIn(BaseModel):
    """Neuer Passkey nur mit Passwort-Bestätigung – eine gestohlene Sitzung reicht nicht."""

    password: Password


class RegisterVerifyIn(BaseModel):
    name: PasskeyName
    credential: Credential


class LoginOptionsOut(BaseModel):
    challenge_id: str
    options: dict[str, Any]


class LoginVerifyIn(BaseModel):
    challenge_id: ChallengeId
    credential: Credential


class PasskeyPatch(BaseModel):
    name: PasskeyName | None = None


class PasskeyOut(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    last_used_at: datetime | None
    backed_up: bool
    device_type: str
