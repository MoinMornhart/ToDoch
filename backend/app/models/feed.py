from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.area import Area
from app.models.base import Base, UUIDPk, utcnow

FEED_DETAILS = ("full", "title", "busy")


class FeedToken(UUIDPk, Base):
    """Geheimer, widerrufbarer Link auf einen ICS-Kalender (nur lesend).

    Gespeichert wird nur der SHA-256 des Tokens – wer die Datenbank liest, kann damit keinen
    Feed abrufen. ``area_id`` leer = alle Bereiche, die der Nutzer sehen darf.
    """

    __tablename__ = "feed_tokens"
    __table_args__ = (CheckConstraint("detail in ('full', 'title', 'busy')", name="detail"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    area_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("areas.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True)
    detail: Mapped[str] = mapped_column(String(10), default="full")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    last_used_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]

    area: Mapped[Area | None] = relationship(lazy="joined")
