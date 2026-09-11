from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPk


class Area(UUIDPk, Timestamps, Base):
    """Bereich wie „Arbeit“ oder „Privat“. Jede Aufgabe gehört zu genau einem Bereich."""

    __tablename__ = "areas"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_areas_owner_name"),
        CheckConstraint("color ~ '^#[0-9a-f]{6}$'", name="color_hex"),
        CheckConstraint("week_days between 1 and 127", name="week_days"),
        CheckConstraint(
            "day_start >= 0 and day_end <= 24 and day_start < day_end", name="day_hours"
        ),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(60))
    color: Mapped[str] = mapped_column(String(7), default="#6b7280")
    icon: Mapped[str] = mapped_column(String(32), default="circle")
    sort_order: Mapped[int] = mapped_column(default=0)
    # Kalenderansicht dieses Bereichs: Wochentage als Bitmaske (Bit 0 = Montag … Bit 6 = Sonntag)
    # und sichtbare Stunden [day_start, day_end).
    week_days: Mapped[int] = mapped_column(SmallInteger, default=127)
    day_start: Mapped[int] = mapped_column(SmallInteger, default=0)
    day_end: Mapped[int] = mapped_column(SmallInteger, default=24)
