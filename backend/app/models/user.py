from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamps, UUIDPk, utcnow


class User(UUIDPk, Timestamps, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(254), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    password_changed_at: Mapped[datetime] = mapped_column(default=utcnow)
    is_admin: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Berlin")
    locale: Mapped[str] = mapped_column(String(8), default="de")
    # Zwei-Faktor (TOTP): Geheimnis verschlüsselt, letzter benutzter Zeitschritt gegen Replay
    totp_secret: Mapped[str | None] = mapped_column(Text)
    totp_enabled_at: Mapped[datetime | None]
    totp_last_step: Mapped[int | None] = mapped_column(BigInteger)

    sessions: Mapped[list[UserSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )

    @property
    def totp_enabled(self) -> bool:
        return self.totp_secret is not None


class RecoveryCode(UUIDPk, Base):
    """Einmal-Code für den Fall, dass die Authenticator-App fehlt. Nur als SHA-256."""

    __tablename__ = "recovery_codes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    code_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    used_at: Mapped[datetime | None]


class UserSession(UUIDPk, Base):
    """Serverseitige Sitzung. Im Cookie steht nur ein zufälliges Token, hier sein SHA-256."""

    __tablename__ = "user_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True)
    auth_method: Mapped[str] = mapped_column(String(20))
    ip: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(default=utcnow)
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]

    user: Mapped[User] = relationship(back_populates="sessions", lazy="joined")
