from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPk


class Contact(UUIDPk, Timestamps, Base):
    """Leichtgewichtiger Kontakt für Telefontermine – kein CRM, nur was zum Vorschlagen und
    Zurückrufen nötig ist. Gehört genau einem Nutzer; andere sehen ihn nur über einen
    verknüpften Termin in einem Bereich, den sie sehen dürfen."""

    __tablename__ = "contacts"
    __table_args__ = (Index("ix_contacts_owner_name", "owner_id", "name"),)

    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    company: Mapped[str] = mapped_column(String(200), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    email: Mapped[str] = mapped_column(String(254), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    use_count: Mapped[int] = mapped_column(default=0)
    last_used_at: Mapped[datetime | None]
