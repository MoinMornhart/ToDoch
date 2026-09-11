from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Identity,
    String,
    Text,
    event,
    insert,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.area import Area
from app.models.base import Base, Timestamps, UUIDPk, utcnow
from app.models.event import Event


class CalendarConnection(UUIDPk, Timestamps, Base):
    """Zwei-Wege-Abgleich eines Bereichs mit einem Online-Kalender (zuerst Google Kalender).

    Termine des Bereichs gehen zum Anbieter, Termine vom Anbieter landen im Bereich. Gespeichert
    wird nur das Refresh-Token (verschlüsselt); ``sync_token`` merkt sich den Stand beim Anbieter.
    """

    __tablename__ = "calendar_connections"
    __table_args__ = (
        CheckConstraint("provider in ('google', 'microsoft', 'caldav')", name="provider"),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    area_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("areas.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(20))
    account_email: Mapped[str] = mapped_column(String(320), default="")
    remote_calendar_id: Mapped[str] = mapped_column(String(255), default="primary")
    token_encrypted: Mapped[str] = mapped_column(Text)
    sync_token: Mapped[str | None] = mapped_column(String(1000))
    enabled: Mapped[bool] = mapped_column(default=True)
    last_synced_at: Mapped[datetime | None]
    last_success_at: Mapped[datetime | None]
    last_error: Mapped[str | None] = mapped_column(String(300))
    event_count: Mapped[int] = mapped_column(default=0)

    area: Mapped[Area] = relationship(lazy="joined", innerjoin=True)


class CalendarTombstone(Base):
    """In ToDoch gelöschter, schon abgeglichener Termin – wird beim nächsten Abgleich auch beim
    Anbieter gelöscht."""

    __tablename__ = "calendar_tombstones"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("calendar_connections.id", ondelete="CASCADE"), index=True
    )
    remote_id: Mapped[str] = mapped_column(String(1024))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


@event.listens_for(Event, "after_delete")
def _remember_deletion(mapper: Any, connection: Any, target: Event) -> None:
    """Jede Löschung (Einzeltermin, ganze Serie …) hinterlässt einen Grabstein für den Abgleich."""
    if target.connection_id is not None and target.remote_id:
        connection.execute(
            insert(CalendarTombstone).values(
                connection_id=target.connection_id,
                remote_id=target.remote_id,
                created_at=utcnow(),
            )
        )
