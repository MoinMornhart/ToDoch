"""Zwei-Faktor (TOTP): einrichten, anmelden mit Code, Replay-Schutz, Wiederherstellungscodes."""

import time
from typing import Any

import pyotp
from httpx import AsyncClient
from sqlalchemy import select

from app.cli import run
from app.models import RecoveryCode, User
from app.resources import Resources
from app.security import totp
from tests.conftest import PASSWORD, ClientFactory, make_settings

EMAIL = "alice@example.org"


def code_at(secret: str, offset_steps: int = 0) -> str:
    return pyotp.TOTP(secret).at(time.time() + offset_steps * totp.STEP)


async def enable(client: AsyncClient) -> tuple[str, list[str]]:
    setup = await client.post("/api/auth/totp/setup", json={"password": PASSWORD})
    assert setup.status_code == 200, setup.text
    data = setup.json()
    assert data["uri"].startswith("otpauth://totp/ToDoch:")
    assert data["qr_svg"].startswith("<svg") and "style=" not in data["qr_svg"]
    confirm = await client.post("/api/auth/totp/confirm", json={"code": code_at(data["secret"])})
    assert confirm.status_code == 200, confirm.text
    codes: list[str] = confirm.json()["recovery_codes"]
    return data["secret"], codes


async def password_step(client: AsyncClient) -> dict[str, Any]:
    r = await client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200, r.text
    result: dict[str, Any] = r.json()
    return result


async def test_setup_and_login_with_code(alice: AsyncClient, client_factory: ClientFactory) -> None:
    secret, codes = await enable(alice)
    assert len(codes) == 10 and len(set(codes)) == 10
    status = (await alice.get("/api/auth/totp")).json()
    assert status == {**status, "enabled": True, "recovery_codes_left": 10}
    assert (await alice.get("/api/auth/me")).json()["totp_enabled"] is True

    fresh = await client_factory()
    step1 = await password_step(fresh)
    assert step1["mfa_required"] is True
    assert (await fresh.get("/api/auth/me")).status_code == 401  # noch keine Sitzung

    wrong = await fresh.post(
        "/api/auth/login/totp", json={"mfa_token": step1["mfa_token"], "code": "000000"}
    )
    assert wrong.status_code == 401
    ok = await fresh.post(
        "/api/auth/login/totp",
        json={"mfa_token": step1["mfa_token"], "code": code_at(secret, 1)},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["email"] == EMAIL
    sessions = (await fresh.get("/api/auth/sessions")).json()
    assert {s["auth_method"] for s in sessions if s["current"]} == {"password+totp"}

    # Das Token ist verbraucht
    again = await fresh.post(
        "/api/auth/login/totp",
        json={"mfa_token": step1["mfa_token"], "code": code_at(secret, 1)},
    )
    assert again.status_code == 401


async def test_same_code_cannot_be_used_twice(
    alice: AsyncClient, client_factory: ClientFactory
) -> None:
    secret, _ = await enable(alice)
    code = code_at(secret, 1)
    first = await client_factory()
    token = (await password_step(first))["mfa_token"]
    ok = await first.post("/api/auth/login/totp", json={"mfa_token": token, "code": code})
    assert ok.status_code == 200
    second = await client_factory()
    token = (await password_step(second))["mfa_token"]
    replay = await second.post("/api/auth/login/totp", json={"mfa_token": token, "code": code})
    assert replay.status_code == 401


async def test_recovery_code_works_once(alice: AsyncClient, client_factory: ClientFactory) -> None:
    _, codes = await enable(alice)
    first = await client_factory()
    token = (await password_step(first))["mfa_token"]
    ok = await first.post(
        "/api/auth/login/totp", json={"mfa_token": token, "code": codes[0].upper()}
    )
    assert ok.status_code == 200
    assert (await first.get("/api/auth/totp")).json()["recovery_codes_left"] == 9
    second = await client_factory()
    token = (await password_step(second))["mfa_token"]
    reused = await second.post("/api/auth/login/totp", json={"mfa_token": token, "code": codes[0]})
    assert reused.status_code == 401


async def test_attempts_are_limited(alice: AsyncClient, client_factory: ClientFactory) -> None:
    await enable(alice)
    fresh = await client_factory()
    token = (await password_step(fresh))["mfa_token"]
    statuses = [
        (
            await fresh.post("/api/auth/login/totp", json={"mfa_token": token, "code": "123456"})
        ).status_code
        for _ in range(7)
    ]
    assert statuses[:5] == [401] * 5
    assert 429 in statuses


async def test_setup_requires_password_and_valid_code(alice: AsyncClient) -> None:
    denied = await alice.post("/api/auth/totp/setup", json={"password": "falsch"})
    assert denied.status_code == 400
    setup = (await alice.post("/api/auth/totp/setup", json={"password": PASSWORD})).json()
    wrong = await alice.post("/api/auth/totp/confirm", json={"code": "000000"})
    assert wrong.status_code == 400
    assert (await alice.get("/api/auth/me")).json()["totp_enabled"] is False
    assert setup["secret"]


async def test_disable_needs_password_and_code(alice: AsyncClient) -> None:
    _, codes = await enable(alice)
    no_code = await alice.post(
        "/api/auth/totp/disable", json={"password": PASSWORD, "code": "000000"}
    )
    assert no_code.status_code == 400
    ok = await alice.post("/api/auth/totp/disable", json={"password": PASSWORD, "code": codes[3]})
    assert ok.status_code == 204
    assert (await alice.get("/api/auth/me")).json()["totp_enabled"] is False
    assert (await alice.get("/api/auth/totp")).json()["recovery_codes_left"] == 0


async def test_new_recovery_codes_replace_old(alice: AsyncClient) -> None:
    _, old = await enable(alice)
    r = await alice.post("/api/auth/totp/recovery-codes", json={"password": PASSWORD})
    new = r.json()["recovery_codes"]
    assert not set(old) & set(new)


async def test_passkey_login_skips_second_factor(
    alice: AsyncClient, client_factory: ClientFactory
) -> None:
    from tests.webauthn_soft import SoftAuthenticator, passkey_login, register_passkey

    authenticator = SoftAuthenticator()
    await register_passkey(alice, authenticator)
    await enable(alice)
    fresh = await client_factory()
    assert (await passkey_login(fresh, authenticator)).status_code == 200


async def test_cli_disables_two_factor(alice: AsyncClient, resources: Resources) -> None:
    await enable(alice)
    code, output = await run("disable-2fa", EMAIL, make_settings())
    assert code == 0, output
    async with resources.sessionmaker() as db:
        user = await db.scalar(select(User).where(User.email == EMAIL))
        assert user is not None and user.totp_secret is None
        assert list(await db.scalars(select(RecoveryCode))) == []


def test_verify_rejects_old_steps() -> None:
    secret = totp.new_secret()
    now = time.time()
    step = totp.current_step(now)
    code = pyotp.TOTP(secret).at(now)
    assert totp.verify(secret, code, None, now) == step
    assert totp.verify(secret, code, step, now) is None
    assert totp.verify(secret, "abc", None, now) is None
    assert totp.hash_recovery("ABCDE-FGHJK") == totp.hash_recovery("abcde fghjk")
