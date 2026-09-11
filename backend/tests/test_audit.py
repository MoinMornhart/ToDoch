import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.models import AuditEvent
from app.resources import Resources
from tests.conftest import PASSWORD, create_user, login


async def test_security_events_are_logged(resources: Resources, client) -> None:  # type: ignore[no-untyped-def]
    await create_user(resources, "alice@example.org")
    await client.post("/api/auth/login", json={"email": "alice@example.org", "password": "x"})
    await login(client, "alice@example.org")
    await client.post("/api/auth/logout")
    async with resources.sessionmaker() as db:
        events = [e.event for e in await db.scalars(select(AuditEvent).order_by(AuditEvent.id))]
        details = [e.details for e in await db.scalars(select(AuditEvent))]
    assert events == ["login.failure", "login.success", "logout"]
    assert all(PASSWORD not in str(d) for d in details)


@pytest.mark.parametrize(
    "statement",
    ["UPDATE audit_log SET event = 'x'", "DELETE FROM audit_log", "TRUNCATE audit_log"],
)
async def test_audit_log_is_append_only(
    resources: Resources, engine: AsyncEngine, statement: str
) -> None:
    async with resources.sessionmaker() as db:
        db.add(AuditEvent(event="test"))
        await db.commit()
    async with engine.connect() as conn:
        with pytest.raises(DBAPIError, match="nur anhängbar"):
            await conn.execute(text(statement))
