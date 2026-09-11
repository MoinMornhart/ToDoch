"""Passkeys: hinzufügen, anmelden ohne Passwort, Schutz gegen Replay, Klone und fremde Seiten."""

from httpx import AsyncClient
from sqlalchemy import select, update

from app.models import AuditEvent, Passkey, User
from app.resources import Resources
from tests.conftest import ClientFactory, create_user, login
from tests.webauthn_soft import SoftAuthenticator, passkey_login, register_passkey


async def test_register_and_sign_in_without_password(
    alice: AsyncClient, client_factory: ClientFactory, resources: Resources
) -> None:
    authenticator = SoftAuthenticator()
    passkey = await register_passkey(alice, authenticator, name="MacBook")
    assert passkey["name"] == "MacBook"
    assert passkey["last_used_at"] is None
    listed = (await alice.get("/api/auth/passkeys")).json()
    assert [p["name"] for p in listed] == ["MacBook"]

    fresh = await client_factory()
    assert (await fresh.get("/api/auth/me")).status_code == 401
    r = await passkey_login(fresh, authenticator)
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "alice@example.org"
    assert (await fresh.get("/api/auth/me")).status_code == 200
    sessions = (await fresh.get("/api/auth/sessions")).json()
    assert {s["auth_method"] for s in sessions if s["current"]} == {"passkey"}

    async with resources.sessionmaker() as db:
        stored = await db.scalar(select(Passkey))
        assert stored is not None
        assert stored.sign_count == 1
        assert stored.last_used_at is not None
        assert stored.transports == ["internal", "hybrid"]  # Unbekanntes wird verworfen
        actions = list(await db.scalars(select(AuditEvent.event)))
        assert "passkey.added" in actions
        assert "login.success" in actions


async def test_registration_requires_password_and_session(
    alice: AsyncClient, client_factory: ClientFactory
) -> None:
    wrong = await alice.post("/api/auth/passkeys/register/options", json={"password": "falsch"})
    assert wrong.status_code == 400
    anonymous = await client_factory()
    r = await anonymous.post("/api/auth/passkeys/register/options", json={"password": "x"})
    assert r.status_code == 401
    # Ohne vorherige Challenge wird nichts eingetragen
    r = await alice.post(
        "/api/auth/passkeys/register/verify",
        json={"name": "x", "credential": SoftAuthenticator().create(
            {"challenge": "AAAA", "user": {"id": "AAAA"}}
        )},
    )  # fmt: skip
    assert r.status_code == 400


async def test_registration_from_foreign_origin_is_rejected(alice: AsyncClient) -> None:
    options = (
        await alice.post("/api/auth/passkeys/register/options", json={"password": "Korrekt-Pferd-Batterie-Heftklammer"})
    ).json()  # fmt: skip
    evil = SoftAuthenticator(origin="https://evil.example")
    r = await alice.post(
        "/api/auth/passkeys/register/verify", json={"name": "x", "credential": evil.create(options)}
    )
    assert r.status_code == 400
    assert (await alice.get("/api/auth/passkeys")).json() == []


async def test_challenge_cannot_be_replayed(
    alice: AsyncClient, client_factory: ClientFactory
) -> None:
    authenticator = SoftAuthenticator()
    await register_passkey(alice, authenticator)
    fresh = await client_factory()
    options = (await fresh.post("/api/auth/passkeys/login/options")).json()
    body = {
        "challenge_id": options["challenge_id"],
        "credential": authenticator.get(options["options"]),
    }
    assert (await fresh.post("/api/auth/passkeys/login/verify", json=body)).status_code == 200
    other = await client_factory()
    assert (await other.post("/api/auth/passkeys/login/verify", json=body)).status_code == 401


async def test_foreign_origin_and_wrong_rp_are_rejected(
    alice: AsyncClient, client_factory: ClientFactory
) -> None:
    authenticator = SoftAuthenticator()
    await register_passkey(alice, authenticator)
    fresh = await client_factory()
    authenticator.origin = "https://evil.example"
    assert (await passkey_login(fresh, authenticator)).status_code == 401
    authenticator.origin, authenticator.rp_id = "https://testserver", "evil.example"
    assert (await passkey_login(fresh, authenticator)).status_code == 401
    assert (await fresh.get("/api/auth/me")).status_code == 401


async def test_cloned_authenticator_is_detected(
    alice: AsyncClient, client_factory: ClientFactory
) -> None:
    authenticator = SoftAuthenticator()
    await register_passkey(alice, authenticator)
    fresh = await client_factory()
    assert (await passkey_login(fresh, authenticator)).status_code == 200
    assert (await passkey_login(fresh, authenticator)).status_code == 200
    authenticator.sign_count = 0  # Klon mit altem Zählerstand
    assert (await passkey_login(fresh, authenticator)).status_code == 401


async def test_unknown_credential_and_wrong_user_handle(
    alice: AsyncClient, client_factory: ClientFactory, resources: Resources
) -> None:
    authenticator = SoftAuthenticator()
    await register_passkey(alice, authenticator)
    fresh = await client_factory()
    assert (await passkey_login(fresh, SoftAuthenticator())).status_code == 401
    bob = await create_user(resources, "bob@example.org")
    r = await passkey_login(fresh, authenticator, user_handle=bob.id.bytes)
    assert r.status_code == 401


async def test_inactive_user_cannot_sign_in(
    alice: AsyncClient, client_factory: ClientFactory, resources: Resources
) -> None:
    authenticator = SoftAuthenticator()
    await register_passkey(alice, authenticator)
    async with resources.sessionmaker() as db:
        await db.execute(update(User).values(is_active=False))
        await db.commit()
    fresh = await client_factory()
    assert (await passkey_login(fresh, authenticator)).status_code == 401


async def test_rename_and_delete(alice: AsyncClient, client_factory: ClientFactory) -> None:
    authenticator = SoftAuthenticator()
    passkey = await register_passkey(alice, authenticator)
    renamed = await alice.patch(f"/api/auth/passkeys/{passkey['id']}", json={"name": " iPhone "})
    assert renamed.json()["name"] == "iPhone"
    empty = await alice.patch(f"/api/auth/passkeys/{passkey['id']}", json={"name": ""})
    assert empty.status_code == 422

    assert (await alice.delete(f"/api/auth/passkeys/{passkey['id']}")).status_code == 204
    fresh = await client_factory()
    assert (await passkey_login(fresh, authenticator)).status_code == 401


async def test_same_authenticator_cannot_register_twice(alice: AsyncClient) -> None:
    authenticator = SoftAuthenticator()
    await register_passkey(alice, authenticator)
    options = (
        await alice.post("/api/auth/passkeys/register/options", json={"password": "Korrekt-Pferd-Batterie-Heftklammer"})
    ).json()  # fmt: skip
    assert len(options["excludeCredentials"]) == 1
    r = await alice.post(
        "/api/auth/passkeys/register/verify",
        json={"name": "doppelt", "credential": authenticator.create(options)},
    )
    assert r.status_code == 409


async def test_passkeys_of_others_are_invisible(alice: AsyncClient, bob: AsyncClient) -> None:
    passkey = await register_passkey(alice, SoftAuthenticator())
    assert (await bob.get("/api/auth/passkeys")).json() == []
    assert (await bob.delete(f"/api/auth/passkeys/{passkey['id']}")).status_code == 404
    assert len((await alice.get("/api/auth/passkeys")).json()) == 1


async def test_bad_login_payloads(client: AsyncClient) -> None:
    bad_id = await client.post(
        "/api/auth/passkeys/login/verify", json={"challenge_id": "x", "credential": {}}
    )
    assert bad_id.status_code == 422
    garbage = await client.post(
        "/api/auth/passkeys/login/verify",
        json={"challenge_id": "a" * 32, "credential": {"id": "!!", "response": 5}},
    )
    assert garbage.status_code == 401


async def test_login_with_password_still_works(
    alice: AsyncClient, client_factory: ClientFactory
) -> None:
    await register_passkey(alice, SoftAuthenticator())
    fresh = await client_factory()
    await login(fresh, "alice@example.org")
