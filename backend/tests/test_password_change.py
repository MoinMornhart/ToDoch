"""Passwort ändern: Admins ohne altes Passwort, alle anderen nur mit."""

from httpx import AsyncClient
from sqlalchemy import select

from app.models import AuditEvent
from app.resources import Resources
from tests.conftest import PASSWORD, ClientFactory, login

NEW_PASSWORD = "Neues-Passwort-fuer-den-Admin-2026"


async def test_admin_changes_password_without_current(
    alice: AsyncClient, client_factory: ClientFactory, resources: Resources
) -> None:
    r = await alice.post("/api/auth/password", json={"new_password": NEW_PASSWORD})
    assert r.status_code == 204, r.text
    assert (await alice.get("/api/auth/me")).status_code == 200  # Sitzung rotiert, bleibt gültig

    fresh = await client_factory()
    await login(fresh, "alice@example.org", NEW_PASSWORD)
    async with resources.sessionmaker() as db:
        entry = await db.scalar(select(AuditEvent).where(AuditEvent.event == "password.changed"))
        assert entry is not None
        assert entry.details["without_current"] is True


async def test_admin_with_wrong_current_password_is_rejected(alice: AsyncClient) -> None:
    r = await alice.post(
        "/api/auth/password", json={"current_password": "falsch", "new_password": NEW_PASSWORD}
    )
    assert r.status_code == 400


async def test_user_still_needs_current_password(
    bob: AsyncClient, client_factory: ClientFactory
) -> None:
    r = await bob.post("/api/auth/password", json={"new_password": NEW_PASSWORD})
    assert r.status_code == 400
    assert r.json()["detail"] == "Bitte das aktuelle Passwort eingeben."
    fresh = await client_factory()
    await login(fresh, "bob@example.org", PASSWORD)  # altes Passwort gilt weiter

    ok = await bob.post(
        "/api/auth/password", json={"current_password": PASSWORD, "new_password": NEW_PASSWORD}
    )
    assert ok.status_code == 204
