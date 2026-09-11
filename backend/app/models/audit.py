from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Identity, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


class AuditEvent(Base):
    """Audit-Log für sicherheitsrelevante Ereignisse.

    Die Tabelle ist per Datenbank-Trigger nur anhängbar (kein UPDATE/DELETE/TRUNCATE).
    ``user_id`` hat bewusst keinen Fremdschlüssel: Nach einer Kontolöschung bleibt der
    Eintrag mit der pseudonymen ID erhalten.
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    event: Mapped[str] = mapped_column(String(64))
    ip: Mapped[str | None] = mapped_column(String(45))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
