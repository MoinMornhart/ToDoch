from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.area import Area
from app.models.base import Base, Timestamps, UUIDPk
from app.models.mail import MailAccount


class MailRule(UUIDPk, Timestamps, Base):
    """Regel für neue Mails: Bedingungen („enthält …“, alle müssen passen) → Aktionen.

    Verglichen wird reiner Text ohne Groß-/Kleinschreibung – bewusst keine regulären Ausdrücke.
    """

    __tablename__ = "mail_rules"
    __table_args__ = (CheckConstraint("priority between 0 and 3", name="priority"),)

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    # Leer = alle Postfächer
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mail_accounts.id", ondelete="CASCADE")
    )
    from_contains: Mapped[str] = mapped_column(String(200), default="")
    subject_contains: Mapped[str] = mapped_column(String(200), default="")
    body_contains: Mapped[str] = mapped_column(String(200), default="")
    create_task: Mapped[bool] = mapped_column(default=True)
    mark_read: Mapped[bool] = mapped_column(default=False)
    # Leer (oder gelöscht) = erster Bereich des Nutzers
    area_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("areas.id", ondelete="SET NULL"))
    priority: Mapped[int] = mapped_column(SmallInteger, default=0)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list)
    enabled: Mapped[bool] = mapped_column(default=True)
    match_count: Mapped[int] = mapped_column(default=0)
    last_matched_at: Mapped[datetime | None]

    account: Mapped[MailAccount | None] = relationship(lazy="joined")
    area: Mapped[Area | None] = relationship(lazy="joined")
