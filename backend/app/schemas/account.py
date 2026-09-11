from __future__ import annotations

from pydantic import BaseModel

from app.schemas.auth import MfaCode, Password


class AccountDeleteIn(BaseModel):
    password: Password
    # Nur nötig, wenn Zwei-Faktor eingerichtet ist (auch ein Wiederherstellungscode)
    code: MfaCode | None = None
