from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.area import Area
from app.models.base import Base, Timestamps, UUIDPk


class ExternalCalendar(UUIDPk, Timestamps, Base):
    """Abonnierter Kalender (ICS-Adresse), z. B. aus Streamo. Seine Termine werden regelmäßig
    abgeglichen, landen im gewählten Bereich und sind in ToDoch nur lesbar.

    Die Adresse enthält meist ein Geheimnis (Token) und wird deshalb verschlüsselt gespeichert;
    ``url_host`` dient nur der Anzeige.
    """

    __tablename__ = "external_calendars"
    __table_args__ = (
        CheckConstraint("refresh_minutes between 15 and 1440", name="refresh_minutes"),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    area_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("areas.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    url_encrypted: Mapped[str] = mapped_column(Text)
    url_host: Mapped[str] = mapped_column(String(255))
    refresh_minutes: Mapped[int] = mapped_column(default=60)
    enabled: Mapped[bool] = mapped_column(default=True)
    etag: Mapped[str | None] = mapped_column(String(200))
    last_synced_at: Mapped[datetime | None]
    last_success_at: Mapped[datetime | None]
    last_error: Mapped[str | None] = mapped_column(String(300))
    event_count: Mapped[int] = mapped_column(default=0)

    area: Mapped[Area] = relationship(lazy="joined", innerjoin=True)
