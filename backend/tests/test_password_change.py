"""Passwort ändern: mit altem Passwort – ohne nur direkt nach einer Anmeldung per Passkey."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select, update

from app.models import AuditEvent, UserSession
from app.resources import Resources
from tests.conftest import PASSWORD, ClientFactory, login

NEW_PASSWORD = "Neues-Passwort-fuer-den-Admin-2026"


async def _as_passkey_login(resources: Resources, *, age: timedelta) -> None:
    """Macht alle Sitzungen zu Passkey-Anmeldungen, die ``age`` alt sind."""
    async with resources.sessionmaker() as db:
        await db.execute(
            update(UserSession).values(auth_method="passkey", created_at=datetime.now(UTC) - age)
        )
        await db.commit()


async def test_fresh_passkey_login_changes_password_without_current(
    alice: AsyncClient, client_factory: ClientFactory, resources: Resources
) -> None:
    await _as_passkey_login(resources, age=timedelta(minutes=1))
    r = await alice.post("/api/auth/password", json={"new_password": NEW_PASSWORD})
    assert r.status_code == 204, r.text
    assert (await alice.get("/api/auth/me")).status_code == 200  # Sitzung rotiert, bleibt gültig

    fresh = await client_factory()
    await login(fresh, "alice@example.org", NEW_PASSWORD)
    async with resources.sessionmaker() as db:
        entry = await db.scalar(select(AuditEvent).where(AuditEvent.event == "password.changed"))
        assert entry is not None
        assert entry.details["without_current"] is True


async def test_old_or_password_session_needs_current_password(
    alice: AsyncClient, resources: Resources
) -> None:
    # Auch ein Admin: Wer nur eine (vielleicht übernommene) Sitzung hat, braucht das Passwort
    r = await alice.post("/api/auth/password", json={"new_password": NEW_PASSWORD})
    assert r.status_code == 400
    assert r.json()["detail"] == "Bitte das aktuelle Passwort eingeben."

    await _as_passkey_login(resources, age=timedelta(hours=1))
    stale = await alice.post("/api/auth/password", json={"new_password": NEW_PASSWORD})
    assert stale.status_code == 400


async def test_wrong_current_password_is_rejected(alice: AsyncClient) -> None:
    r = await alice.post(
        "/api/auth/password", json={"current_password": "falsch", "new_password": NEW_PASSWORD}
    )
    assert r.status_code == 400


async def test_user_changes_password_with_current(
    bob: AsyncClient, client_factory: ClientFactory
) -> None:
    r = await bob.post("/api/auth/password", json={"new_password": NEW_PASSWORD})
    assert r.status_code == 400
    fresh = await client_factory()
    await login(fresh, "bob@example.org", PASSWORD)  # altes Passwort gilt weiter

    ok = await bob.post(
        "/api/auth/password", json={"current_password": PASSWORD, "new_password": NEW_PASSWORD}
    )
    assert ok.status_code == 204
