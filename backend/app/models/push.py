from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Identity, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPk, utcnow


class ServerKey(Base):
    """Vom Server selbst erzeugte Schlüssel (z. B. VAPID für Web-Push), privat verschlüsselt."""

    __tablename__ = "server_keys"

    name: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class PushSubscription(UUIDPk, Base):
    """Web-Push-Abo eines Browsers. Das Auth-Geheimnis liegt verschlüsselt in der Datenbank."""

    __tablename__ = "push_subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    endpoint: Mapped[str] = mapped_column(String(1000), unique=True)
    p256dh: Mapped[str] = mapped_column(String(200))
    auth_enc: Mapped[str] = mapped_column(String(300))
    user_agent: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_success_at: Mapped[datetime | None]
    failures: Mapped[int] = mapped_column(default=0)


class ReminderLog(Base):
    """Verschickte Erinnerungen – damit jede nur einmal kommt."""

    __tablename__ = "reminder_log"
    __table_args__ = (
        UniqueConstraint("event_id", "occurrence_start", "minutes", name="uq_reminder_log_once"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    occurrence_start: Mapped[datetime]
    minutes: Mapped[int]
    sent_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
