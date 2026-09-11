from sqlalchemy import select

from app.cli import run
from app.models import AuditEvent, User
from app.resources import Resources
from app.security.passwords import verify_password
from tests.conftest import create_user


async def test_users_and_reset_password(resources: Resources, client) -> None:  # type: ignore[no-untyped-def]
    code, output = await run("users", None, resources.settings)
    assert code == 0 and "Noch keine Benutzer" in output

    await create_user(resources, "alice@example.org")
    await client.post(
        "/api/auth/login",
        json={"email": "alice@example.org", "password": "Korrekt-Pferd-Batterie-Heftklammer"},
    )
    assert (await client.get("/api/auth/me")).status_code == 200

    code, output = await run("users", None, resources.settings)
    assert "alice@example.org" in output

    code, output = await run("reset-password", "ALICE@example.org", resources.settings)
    assert code == 0
    new_password = output.split("\n\n")[1].strip()
    async with resources.sessionmaker() as db:
        user = await db.scalar(select(User).where(User.email == "alice@example.org"))
        assert user is not None
        assert verify_password(user.password_hash, new_password)[0]
        events = [e.event for e in await db.scalars(select(AuditEvent))]
    assert "password.reset_cli" in events
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_make_admin_and_unknown_user(resources: Resources) -> None:
    await create_user(resources, "bob@example.org")
    code, _ = await run("make-admin", "bob@example.org", resources.settings)
    assert code == 0
    async with resources.sessionmaker() as db:
        user = await db.scalar(select(User).where(User.email == "bob@example.org"))
        assert user is not None and user.is_admin
    code, output = await run("make-admin", "niemand@example.org", resources.settings)
    assert code == 1 and "nicht gefunden" in output
