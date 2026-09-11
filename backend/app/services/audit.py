"""Audit-Log schreiben. Nie Passwörter, Tokens oder Inhalte protokollieren."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent

# Die Datenbank erlaubt das Entfernen der IP ab 90 Tagen (Migration 0019); ein Tag Puffer,
# damit leicht abweichende Uhren von App und Datenbank den Lauf nicht abbrechen.
IP_RETENTION = timedelta(days=91)


def record(
    db: AsyncSession,
    event: str,
    *,
    user_id: uuid.UUID | None = None,
    ip: str | None = None,
    **details: Any,
) -> None:
    db.add(AuditEvent(event=event, user_id=user_id, ip=ip, details=details))


async def forget_old_ips(db: AsyncSession, now: datetime | None = None) -> int:
    """Entfernt IP-Adressen aus alten Einträgen – Ereignis und pseudonyme ID bleiben."""
    cutoff = (now or datetime.now(UTC)) - IP_RETENTION
    result = await db.execute(
        update(AuditEvent)
        .where(AuditEvent.ip.is_not(None), AuditEvent.created_at < cutoff)
        .values(ip=None)
        .execution_options(synchronize_session=False)
    )
    await db.commit()
    return int(getattr(result, "rowcount", 0) or 0)
