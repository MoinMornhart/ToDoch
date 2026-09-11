from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, LargeBinary, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPk, utcnow


class Passkey(UUIDPk, Base):
    """WebAuthn-Zugangsdaten (Passkey). Gespeichert wird nur der öffentliche Schlüssel –
    der private bleibt im Gerät, Passwort-Manager oder Sicherheitsschlüssel."""

    __tablename__ = "passkeys"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    credential_id: Mapped[bytes] = mapped_column(LargeBinary(1023), unique=True)
    public_key: Mapped[bytes] = mapped_column(LargeBinary)
    sign_count: Mapped[int] = mapped_column(BigInteger, default=0)
    transports: Mapped[list[str]] = mapped_column(ARRAY(String(20)), default=list)
    aaguid: Mapped[str] = mapped_column(String(36), default="")
    name: Mapped[str] = mapped_column(String(100))
    backed_up: Mapped[bool] = mapped_column(default=False)
    device_type: Mapped[str] = mapped_column(String(20), default="single_device")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_used_at: Mapped[datetime | None]
