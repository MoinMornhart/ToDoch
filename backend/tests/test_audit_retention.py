"""Audit-Log: IP-Adressen verschwinden nach 90 Tagen – sonst bleibt jeder Eintrag unveränderlich."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.exc import DBAPIError

from app.models import AuditEvent
from app.resources import Resources
from app.worker import forget_audit_ips


async def _entry(resources: Resources, *, age: timedelta, ip: str) -> int:
    async with resources.sessionmaker() as db:
        entry = AuditEvent(
            event="login.success",
            user_id=uuid.uuid4(),
            ip=ip,
            details={"method": "password"},
            created_at=datetime.now(UTC) - age,
        )
        db.add(entry)
        await db.commit()
        return entry.id


async def test_old_ips_are_removed_recent_ones_kept(resources: Resources) -> None:
    old = await _entry(resources, age=timedelta(days=120), ip="203.0.113.7")
    recent = await _entry(resources, age=timedelta(days=10), ip="198.51.100.9")

    assert await forget_audit_ips({"sessionmaker": resources.sessionmaker}) == 1

    async with resources.sessionmaker() as db:
        rows = {e.id: e for e in await db.scalars(select(AuditEvent))}
    assert rows[old].ip is None
    assert rows[old].event == "login.success"  # Ereignis und pseudonyme ID bleiben
    assert rows[old].details == {"method": "password"}
    assert rows[recent].ip == "198.51.100.9"


@pytest.mark.parametrize(
    "change",
    [
        # frische IP entfernen – die Frist steht in der Datenbank, nicht in der App
        lambda recent, old: update(AuditEvent).where(AuditEvent.id == recent).values(ip=None),
        # bei alten Einträgen darf sich nur die IP ändern
        lambda recent, old: (
            update(AuditEvent).where(AuditEvent.id == old).values(ip=None, event="nichts passiert")
        ),
        lambda recent, old: update(AuditEvent).where(AuditEvent.id == old).values(ip="10.0.0.1"),
        lambda recent, old: delete(AuditEvent).where(AuditEvent.id == old),
    ],
)
async def test_everything_else_stays_immutable(resources: Resources, change: object) -> None:
    old = await _entry(resources, age=timedelta(days=120), ip="203.0.113.7")
    recent = await _entry(resources, age=timedelta(days=10), ip="198.51.100.9")
    async with resources.sessionmaker() as db:
        with pytest.raises(DBAPIError, match="nur anhängbar"):
            await db.execute(change(recent, old))  # type: ignore[operator]
