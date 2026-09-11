from httpx import AsyncClient

from app.resources import Resources
from app.security.middleware import CSRF_COOKIE, SESSION_COOKIE
from tests.conftest import (
    ORIGIN,
    PASSWORD,
    SETUP_TOKEN,
    ClientFactory,
    create_user,
    login,
)

SETUP = {
    "setup_token": SETUP_TOKEN,
    "email": "Admin@Example.org ",
    "display_name": "Admin",
    "password": PASSWORD,
    "timezone": "Europe/Berlin",
}


async def test_meta_reports_setup_and_sets_csrf_cookie(client: AsyncClient) -> None:
    response = await client.get("/api/meta")
    assert response.status_code == 200
    assert response.json()["setup_required"] is True
    assert client.cookies.get(CSRF_COOKIE)


async def test_security_headers(client: AsyncClient) -> None:
    response = await client.get("/api/meta")
    headers = response.headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "no-referrer"
    assert headers["cross-origin-opener-policy"] == "same-origin"
    assert "default-src 'none'" in headers["content-security-policy"]
    assert headers["strict-transport-security"].startswith("max-age=")
    assert headers["cache-control"] == "no-store"
    assert "publickey-credentials-get=(self)" in headers["permissions-policy"]


async def test_setup_flow(client: AsyncClient) -> None:
    wrong = await client.post("/api/setup", json={**SETUP, "setup_token": "falsch-falsch-falsch"})
    assert wrong.status_code == 403

    weak = await client.post("/api/setup", json={**SETUP, "password": "kurz"})
    assert weak.status_code == 400

    response = await client.post("/api/setup", json=SETUP)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == "admin@example.org"
    assert body["is_admin"] is True

    session_cookie = next(
        c for c in response.headers.get_list("set-cookie") if c.startswith(SESSION_COOKIE)
    )
    lowered = session_cookie.lower()
    assert "httponly" in lowered and "secure" in lowered
    assert "samesite=lax" in lowered and "path=/" in lowered

    areas = (await client.get("/api/areas")).json()
    assert [a["name"] for a in areas] == ["Arbeit", "Privat"]

    again = await client.post("/api/setup", json=SETUP)
    assert again.status_code == 409
    assert (await client.get("/api/meta")).json()["setup_required"] is False


async def test_csrf_and_origin_are_enforced(client: AsyncClient) -> None:
    no_token = await client.post(
        "/api/auth/login",
        json={"email": "a@b.de", "password": "x"},
        headers={"X-CSRF-Token": ""},
    )
    assert no_token.status_code == 403

    wrong_token = await client.post(
        "/api/auth/login",
        json={"email": "a@b.de", "password": "x"},
        headers={"X-CSRF-Token": "nicht-das-cookie"},
    )
    assert wrong_token.status_code == 403

    foreign = await client.post(
        "/api/auth/login",
        json={"email": "a@b.de", "password": "x"},
        headers={"Origin": "https://evil.example"},
    )
    assert foreign.status_code == 403

    fine = await client.post("/api/auth/login", json={"email": "a@b.de", "password": "x"})
    assert fine.status_code == 401


async def test_referer_fallback_when_origin_missing(client: AsyncClient) -> None:
    del client.headers["Origin"]
    missing = await client.post("/api/auth/login", json={"email": "a@b.de", "password": "x"})
    assert missing.status_code == 403
    with_referer = await client.post(
        "/api/auth/login",
        json={"email": "a@b.de", "password": "x"},
        headers={"Referer": f"{ORIGIN}/login"},
    )
    assert with_referer.status_code == 401


async def test_login_errors_are_generic(resources: Resources, client: AsyncClient) -> None:
    await create_user(resources, "alice@example.org")
    unknown = await client.post(
        "/api/auth/login", json={"email": "niemand@example.org", "password": PASSWORD}
    )
    wrong = await client.post(
        "/api/auth/login", json={"email": "alice@example.org", "password": "falsch"}
    )
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()


async def test_login_lockout_with_backoff(resources: Resources, client: AsyncClient) -> None:
    await create_user(resources, "alice@example.org")
    for _ in range(4):
        r = await client.post(
            "/api/auth/login", json={"email": "alice@example.org", "password": "falsch"}
        )
        assert r.status_code == 401
    fifth = await client.post(
        "/api/auth/login", json={"email": "alice@example.org", "password": "falsch"}
    )
    assert fifth.status_code == 401
    locked = await client.post(
        "/api/auth/login", json={"email": "alice@example.org", "password": PASSWORD}
    )
    assert locked.status_code == 429
    assert int(locked.headers["retry-after"]) > 0


async def test_unknown_accounts_are_locked_too(client: AsyncClient) -> None:
    for _ in range(5):
        await client.post("/api/auth/login", json={"email": "x@example.org", "password": "y"})
    r = await client.post("/api/auth/login", json={"email": "x@example.org", "password": "y"})
    assert r.status_code == 429


async def test_validation_errors_do_not_echo_input(client: AsyncClient) -> None:
    secret = "S3cret-" + "x" * 300
    r = await client.post("/api/auth/login", json={"email": "a@b.de", "password": secret})
    assert r.status_code == 422
    assert "S3cret" not in r.text


async def test_body_size_limit(client: AsyncClient) -> None:
    r = await client.post(
        "/api/auth/login",
        content=b'{"email": "' + b"a" * 2_000_000 + b'"}',
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 413


async def test_me_requires_login(client: AsyncClient) -> None:
    assert (await client.get("/api/auth/me")).status_code == 401
    assert (await client.get("/api/tasks")).status_code == 401


async def test_update_profile(alice: AsyncClient) -> None:
    r = await alice.patch("/api/auth/me", json={"display_name": "Alice A.", "timezone": "UTC"})
    assert r.status_code == 200
    assert r.json()["timezone"] == "UTC"
    bad = await alice.patch("/api/auth/me", json={"timezone": "../../etc/passwd"})
    assert bad.status_code == 422


async def test_sessions_list_and_revoke(
    resources: Resources, alice: AsyncClient, client_factory: ClientFactory
) -> None:
    second = await client_factory()
    await login(second, "alice@example.org")

    sessions = (await alice.get("/api/auth/sessions")).json()
    assert len(sessions) == 2
    current = [s for s in sessions if s["current"]]
    other = [s for s in sessions if not s["current"]]
    assert len(current) == 1 and len(other) == 1

    r = await alice.delete(f"/api/auth/sessions/{other[0]['id']}")
    assert r.status_code == 204
    assert (await second.get("/api/auth/me")).status_code == 401
    assert (await alice.get("/api/auth/me")).status_code == 200


async def test_logout_all(alice: AsyncClient, client_factory: ClientFactory) -> None:
    second = await client_factory()
    await login(second, "alice@example.org")
    assert (await alice.post("/api/auth/logout-all")).status_code == 204
    assert (await alice.get("/api/auth/me")).status_code == 401
    assert (await second.get("/api/auth/me")).status_code == 401


async def test_logout(alice: AsyncClient) -> None:
    assert (await alice.post("/api/auth/logout")).status_code == 204
    assert (await alice.get("/api/auth/me")).status_code == 401


async def test_session_rotation_on_login(alice: AsyncClient) -> None:
    old_token = alice.cookies.get(SESSION_COOKIE)
    await login(alice, "alice@example.org")
    assert alice.cookies.get(SESSION_COOKIE) != old_token
    sessions = (await alice.get("/api/auth/sessions")).json()
    assert len(sessions) == 1


async def test_password_change(alice: AsyncClient, client_factory: ClientFactory) -> None:
    second = await client_factory()
    await login(second, "alice@example.org")

    wrong = await alice.post(
        "/api/auth/password",
        json={"current_password": "falsch", "new_password": "Neues-Sehr-Langes-Passwort-7"},
    )
    assert wrong.status_code == 400
    weak = await alice.post(
        "/api/auth/password", json={"current_password": PASSWORD, "new_password": "kurz"}
    )
    assert weak.status_code == 400

    ok = await alice.post(
        "/api/auth/password",
        json={"current_password": PASSWORD, "new_password": "Neues-Sehr-Langes-Passwort-7"},
    )
    assert ok.status_code == 204
    assert (await alice.get("/api/auth/me")).status_code == 200
    assert (await second.get("/api/auth/me")).status_code == 401

    third = await client_factory()
    await login(third, "alice@example.org", "Neues-Sehr-Langes-Passwort-7")


async def test_health(client: AsyncClient) -> None:
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
