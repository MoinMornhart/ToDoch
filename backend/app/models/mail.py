from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamps, UUIDPk, utcnow


class MailAccount(UUIDPk, Timestamps, Base):
    """E-Mail-Postfach (IMAP). Das Passwort wird verschlüsselt gespeichert und nie ausgegeben.

    ``uidvalidity``/``last_uid`` merken sich, bis wohin abgeglichen wurde – beim nächsten Mal
    werden nur neuere Mails geholt.
    """

    __tablename__ = "mail_accounts"
    __table_args__ = (
        CheckConstraint("refresh_minutes between 5 and 1440", name="refresh_minutes"),
        CheckConstraint("security in ('ssl', 'starttls')", name="security"),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(320))
    imap_host: Mapped[str] = mapped_column(String(255))
    imap_port: Mapped[int]
    security: Mapped[str] = mapped_column(String(10), default="ssl")
    username: Mapped[str] = mapped_column(String(320))
    password_encrypted: Mapped[str] = mapped_column(Text)
    folder: Mapped[str] = mapped_column(String(200), default="INBOX")
    refresh_minutes: Mapped[int] = mapped_column(default=15)
    enabled: Mapped[bool] = mapped_column(default=True)
    uidvalidity: Mapped[int | None] = mapped_column(BigInteger)
    last_uid: Mapped[int] = mapped_column(BigInteger, default=0)
    last_synced_at: Mapped[datetime | None]
    last_success_at: Mapped[datetime | None]
    last_error: Mapped[str | None] = mapped_column(String(300))
    message_count: Mapped[int] = mapped_column(default=0)


class MailMessage(UUIDPk, Base):
    """Eine abgeholte Mail – nur als Text, HTML wird nie gespeichert oder angezeigt."""

    __tablename__ = "mail_messages"
    __table_args__ = (
        UniqueConstraint("account_id", "uid", name="uq_mail_messages_account_uid"),
        Index("ix_mail_messages_account_sent", "account_id", "sent_at"),
        CheckConstraint(
            "suggestion_status is null or "
            "suggestion_status in ('pending', 'accepted', 'dismissed')",
            name="suggestion_status",
        ),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mail_accounts.id", ondelete="CASCADE")
    )
    uid: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[str] = mapped_column(String(500), default="")
    from_name: Mapped[str] = mapped_column(String(200), default="")
    from_address: Mapped[str] = mapped_column(String(320), default="")
    recipients: Mapped[str] = mapped_column(String(1000), default="")
    subject: Mapped[str] = mapped_column(String(500), default="")
    sent_at: Mapped[datetime | None]
    received_at: Mapped[datetime] = mapped_column(server_default=func.now(), default=utcnow)
    snippet: Mapped[str] = mapped_column(String(300), default="")
    body_text: Mapped[str] = mapped_column(Text, default="")
    has_html: Mapped[bool] = mapped_column(default=False)
    attachment_count: Mapped[int] = mapped_column(default=0)
    truncated: Mapped[bool] = mapped_column(default=False)
    is_read: Mapped[bool] = mapped_column(default=False)
    # Aufgabe, die aus dieser Mail entstanden ist
    task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"))
    # Erkannter Termin (Einladung oder Datum im Text) – wartet auf Bestätigung
    suggestion: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    suggestion_status: Mapped[str | None] = mapped_column(String(12))
    event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"))

    account: Mapped[MailAccount] = relationship(lazy="joined", innerjoin=True)
