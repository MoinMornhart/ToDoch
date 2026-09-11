"""Audit-Log schreiben. Nie Passwörter, Tokens oder Inhalte protokollieren."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent


def record(
    db: AsyncSession,
    event: str,
    *,
    user_id: uuid.UUID | None = None,
    ip: str | None = None,
    **details: Any,
) -> None:
    db.add(AuditEvent(event=event, user_id=user_id, ip=ip, details=details))
