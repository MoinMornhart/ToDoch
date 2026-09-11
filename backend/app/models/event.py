from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.area import Area
from app.models.base import Base, Timestamps, UUIDPk
from app.models.contact import Contact

CHANNELS = ("phone", "in_person", "mail", "other")
EVENT_STATUSES = ("tentative", "confirmed", "cancelled")


class Event(UUIDPk, Timestamps, Base):
    """Termin. Serien haben eine RRULE; geänderte Einzeltermine einer Serie sind eigene Zeilen
    mit ``series_id`` (Serie) und ``recurrence_id`` (ursprünglicher Beginn, UTC) – wie
    RECURRENCE-ID in iCalendar.

    Zeitgebundene Termine speichern Beginn/Ende in UTC plus die Zeitzone ``tzid`` (für
    Wiederholungen über Sommerzeitwechsel). Ganztägige Termine speichern Mitternacht UTC des
    Tages; ``end_at`` ist exklusiv (Folgetag).
    """

    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("end_at >= start_at", name="end_after_start"),
        CheckConstraint("status in ('tentative', 'confirmed', 'cancelled')", name="status"),
        CheckConstraint("transparency in ('opaque', 'transparent')", name="transparency"),
        CheckConstraint("(series_id is null) = (recurrence_id is null)", name="override_pair"),
        CheckConstraint(
            "channel is null or channel in ('phone', 'in_person', 'mail', 'other')",
            name="channel",
        ),
        CheckConstraint("priority between 0 and 3", name="priority"),
        UniqueConstraint(
            "uid",
            "recurrence_id",
            name="uq_events_uid_recurrence",
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_events_area_start", "area_id", "start_at"),
        Index("ix_events_series", "series_id"),
        Index("ix_events_search", "search_vector", postgresql_using="gin"),
    )

    area_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("areas.id", ondelete="CASCADE"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    uid: Mapped[str] = mapped_column(String(255))
    series_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    recurrence_id: Mapped[datetime | None]
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    location: Mapped[str] = mapped_column(String(500), default="")
    url: Mapped[str] = mapped_column(String(1000), default="")
    start_at: Mapped[datetime]
    end_at: Mapped[datetime]
    all_day: Mapped[bool] = mapped_column(default=False)
    tzid: Mapped[str] = mapped_column(String(64), default="Europe/Berlin")
    rrule: Mapped[str | None] = mapped_column(String(300))
    exdates: Mapped[list[datetime]] = mapped_column(ARRAY(DateTime(timezone=True)), default=list)
    status: Mapped[str] = mapped_column(String(12), default="confirmed")
    transparency: Mapped[str] = mapped_column(String(12), default="opaque")
    is_fixed: Mapped[bool] = mapped_column(default=False)
    source: Mapped[str] = mapped_column(String(20), default="manual")
    # Telefontermin: Kontakt, wie und wann vereinbart, mit wem gesprochen
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL"), index=True
    )
    channel: Mapped[str | None] = mapped_column(String(12))
    agreed_on: Mapped[date | None]
    agreed_with: Mapped[str] = mapped_column(String(200), default="")
    priority: Mapped[int] = mapped_column(SmallInteger, default=0)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list)
    attendees: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    reminders: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    sequence: Mapped[int] = mapped_column(default=0)
    search_vector: Mapped[Any] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(description, '') "
            "|| ' ' || coalesce(location, ''))",
            persisted=True,
        ),
        deferred=True,
    )

    area: Mapped[Area] = relationship(lazy="joined", innerjoin=True)
    contact: Mapped[Contact | None] = relationship(lazy="joined")
