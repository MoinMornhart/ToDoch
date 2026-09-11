"""Datenexport ohne Geheimnisse und endgültiges Löschen des Kontos."""

import time
from urllib.parse import urlsplit

import pyotp
from httpx import AsyncClient
from sqlalchemy import select

from app.models import AuditEvent
from app.resources import Resources
from tests.conftest import PASSWORD, ClientFactory, create_user, login


async def test_export_contains_my_data_but_no_secrets(alice: AsyncClient) -> None:
    await alice.post("/api/tasks", json={"title": "Steuererklärung"})
    await alice.post(
        "/api/mail/accounts",
        json={
            "email": "alice@example.org",
            "password": "imap-geheim",
            "imap_host": "imap.example.org",
        },
    )
    await alice.post("/api/feeds", json={"name": "iPhone"})
    exported = await alice.get("/api/account/export")
    assert exported.status_code == 200
    assert "attachment" in exported.headers["content-disposition"]
    data = exported.json()
    assert data["format"] == "todoch-export/1"
    assert data["user"]["email"] == "alice@example.org"
    assert [t["title"] for t in data["tasks"]] == ["Steuererklärung"]
    assert data["mail_accounts"][0]["imap_host"] == "imap.example.org"
    assert len(data["mails"]) == 1 and len(data["calendar_feeds"]) == 1
    assert any(e["event"] == "login.success" for e in data["audit_log"])
    text = exported.text
    for secret in ("imap-geheim", "password_hash", "password_encrypted", "token_hash", "$argon2"):
        assert secret not in text, secret


async def test_delete_account(
    alice: AsyncClient, resources: Resources, client_factory: ClientFactory
) -> None:
    await create_user(resources, "bob@example.org")
    bob = await client_factory()
    await login(bob, "bob@example.org")
    # Bob arbeitet in Alice' geteiltem Bereich mit
    work = next(a for a in (await alice.get("/api/areas")).json() if a["name"] == "Arbeit")
    invite = await alice.post(f"/api/areas/{work['id']}/invites", json={"role": "member"})
    token = urlsplit(invite.json()["url"]).fragment
    await bob.post("/api/invites/accept", json={"token": token})
    task = (await bob.post("/api/tasks", json={"title": "Von Bob", "area_id": work["id"]})).json()
    await bob.post(f"/api/tasks/{task['id']}/comments", json={"body": "Erledige ich"})
    await bob.post("/api/tasks", json={"title": "Bobs Privates"})

    wrong = await bob.post("/api/account/delete", json={"password": "falsches-passwort-123"})
    assert wrong.status_code == 400
    deleted = await bob.post("/api/account/delete", json={"password": PASSWORD})
    assert deleted.status_code == 204
    assert (await bob.get("/api/auth/me")).status_code == 401
    relogin = await bob.post(
        "/api/auth/login", json={"email": "bob@example.org", "password": PASSWORD}
    )
    assert relogin.status_code != 200

    # In Alice' Bereich bleibt Bobs Arbeit – ohne seinen Namen
    kept = (await alice.get(f"/api/tasks/{task['id']}")).json()
    assert kept["title"] == "Von Bob"
    comments = (await alice.get(f"/api/tasks/{task['id']}/comments")).json()
    assert [c["author_name"] for c in comments] == ["?"]
    members = (await alice.get(f"/api/areas/{work['id']}/members")).json()
    assert [m["role"] for m in members] == ["owner"]
    async with resources.sessionmaker() as db:
        events = list(await db.scalars(select(AuditEvent.event)))
    assert "account.deleted" in events


async def test_last_admin_and_two_factor(alice: AsyncClient) -> None:
    last = await alice.post(
        "/api/account/delete", json={"password": PASSWORD}, headers={"Accept-Language": "en"}
    )
    assert last.status_code == 409
    assert last.json()["detail"] == "The last admin account cannot be deleted."

    setup = (await alice.post("/api/auth/totp/setup", json={"password": PASSWORD})).json()
    secret = setup["secret"]
    confirmed = await alice.post(
        "/api/auth/totp/confirm", json={"code": pyotp.TOTP(secret).at(time.time())}
    )
    assert confirmed.status_code == 200
    missing = await alice.post("/api/account/delete", json={"password": PASSWORD})
    assert missing.status_code == 400
    assert missing.json()["detail"] == "Der Code ist falsch."
