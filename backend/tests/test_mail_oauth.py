"""„Mit Google/Microsoft verbinden“: OAuth mit PKCE, einmaliger State, XOAUTH2, Token-Erneuerung."""

import base64
import hashlib
import json
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from httpx import AsyncClient

from app.resources import Resources
from app.services import mail_oauth as oauth
from tests.conftest import make_settings
from tests.fake_imap import FakeMailbox


def _id_token(claims: dict[str, Any]) -> str:
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"eyJhbGciOiJSUzI1NiJ9.{payload}.signatur"


@pytest.fixture
def configured(resources: Resources) -> None:
    settings = make_settings(
        google_client_id="123-abc.apps.googleusercontent.com",
        google_client_secret="GOCSPX-geheim",
        microsoft_client_id="00000000-1111-2222-3333-444444444444",
        microsoft_client_secret="ms~geheim",
    )
    object.__setattr__(resources, "settings", settings)


@pytest.fixture
def provider_calls(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Token-Endpunkt der Anbieter nachgebaut."""
    calls: dict[str, Any] = {"refresh": "access-2", "fail_refresh": False}

    async def exchange(p: oauth.Provider, code: str, verifier: str, redirect: str) -> oauth.Tokens:
        calls["exchange"] = {
            "provider": p.name,
            "code": code,
            "verifier": verifier,
            "redirect": redirect,
        }
        return oauth.Tokens("access-1", "refresh-1", "Alice@Gmail.com".lower())

    async def refresh(p: oauth.Provider, token: str) -> oauth.Tokens:
        calls["refreshed_with"] = token
        if calls["fail_refresh"]:
            raise oauth.OAuthError(oauth.EXPIRED)
        return oauth.Tokens(calls["refresh"], "refresh-2", None)

    monkeypatch.setattr(oauth, "exchange_code", exchange)
    monkeypatch.setattr(oauth, "refresh_access", refresh)
    return calls


async def _start(client: AsyncClient, provider: str = "google") -> dict[str, str]:
    response = await client.post(f"/api/mail/oauth/{provider}/start")
    assert response.status_code == 200, response.text
    url = urlsplit(response.json()["url"])
    return {k: v[0] for k, v in parse_qs(url.query).items()} | {"host": url.netloc}


async def _callback(client: AsyncClient, provider: str = "google", **params: str) -> str:
    response = await client.get(f"/api/mail/oauth/{provider}/callback", params=params)
    assert response.status_code == 303, response.text
    return response.headers["location"]


async def test_providers_are_off_until_configured(alice: AsyncClient) -> None:
    assert (await alice.get("/api/mail/oauth/providers")).json() == {
        "google": False,
        "microsoft": False,
    }
    assert (await alice.post("/api/mail/oauth/google/start")).status_code == 409


async def test_connect_google_and_sync_with_fresh_tokens(
    alice: AsyncClient, configured: None, provider_calls: dict[str, Any], mailbox: FakeMailbox
) -> None:
    assert (await alice.get("/api/mail/oauth/providers")).json() == {
        "google": True,
        "microsoft": True,
    }
    params = await _start(alice)
    assert params["host"] == "accounts.google.com"
    assert params["client_id"] == "123-abc.apps.googleusercontent.com"
    assert params["redirect_uri"] == "https://testserver/api/mail/oauth/google/callback"
    assert params["code_challenge_method"] == "S256"
    assert "https://mail.google.com/" in params["scope"]
    assert (params["access_type"], params["prompt"]) == ("offline", "consent")

    location = await _callback(alice, code="code-123", state=params["state"])
    assert location == "/mail?connected=google"
    exchange = provider_calls["exchange"]
    verifier_hash = hashlib.sha256(exchange["verifier"].encode()).digest()
    assert base64.urlsafe_b64encode(verifier_hash).rstrip(b"=").decode() == params["code_challenge"]
    assert exchange["code"] == "code-123"
    assert mailbox.oauth_logins == ["alice@gmail.com:access-1"]
    assert mailbox.connections[-1][0] == "imap.gmail.com"

    accounts = (await alice.get("/api/mail/accounts")).json()
    assert len(accounts) == 1
    account = accounts[0]
    assert (account["auth"], account["provider"], account["email"]) == (
        "oauth2",
        "google",
        "alice@gmail.com",
    )
    assert account["message_count"] == 1
    assert "refresh-1" not in str(accounts)

    # Der State gilt genau einmal
    assert await _callback(alice, code="code-123", state=params["state"]) == (
        "/mail?oauth_error=expired"
    )

    # Abgleich holt ein frisches Zugriffstoken; das erneuerte Refresh-Token wird gespeichert
    synced = (await alice.post(f"/api/mail/accounts/{account['id']}/sync")).json()
    assert synced["last_error"] is None
    assert provider_calls["refreshed_with"] == "refresh-1"
    assert mailbox.oauth_logins[-1] == "alice@gmail.com:access-2"
    await alice.post(f"/api/mail/accounts/{account['id']}/sync")
    assert provider_calls["refreshed_with"] == "refresh-2"

    provider_calls["fail_refresh"] = True
    failed = (await alice.post(f"/api/mail/accounts/{account['id']}/sync")).json()
    assert "neu verbinden" in failed["last_error"]

    # Neu verbinden legt kein zweites Postfach an und behebt den Fehler
    params = await _start(alice)
    assert await _callback(alice, code="c", state=params["state"]) == "/mail?connected=google"
    accounts = (await alice.get("/api/mail/accounts")).json()
    assert len(accounts) == 1
    assert accounts[0]["last_error"] is None


async def test_state_is_bound_to_user_and_provider(
    alice: AsyncClient, bob: AsyncClient, configured: None, provider_calls: dict[str, Any]
) -> None:
    params = await _start(alice)
    assert await _callback(bob, code="x", state=params["state"]) == "/mail?oauth_error=failed"
    assert (await bob.get("/api/mail/accounts")).json() == []
    # … und ist danach verbraucht
    assert await _callback(alice, code="x", state=params["state"]) == "/mail?oauth_error=expired"

    params = await _start(alice, "microsoft")
    assert params["host"] == "login.microsoftonline.com"
    assert "IMAP.AccessAsUser.All" in params["scope"]
    location = await _callback(alice, "google", code="x", state=params["state"])
    assert location == "/mail?oauth_error=failed"

    params = await _start(alice)
    denied = await _callback(alice, error="access_denied", state=params["state"])
    assert denied == "/mail?oauth_error=denied"
    assert await _callback(alice, code="x") == "/mail?oauth_error=failed"
    assert "exchange" not in provider_calls


def test_email_comes_from_the_id_token() -> None:
    assert oauth.email_from_id_token(_id_token({"email": "Max@Example.org"})) == "max@example.org"
    assert oauth.email_from_id_token(_id_token({"preferred_username": "a@live.de"})) == "a@live.de"
    assert oauth.email_from_id_token(_id_token({"sub": "123"})) is None
    assert oauth.email_from_id_token("kaputt") is None
    assert oauth.email_from_id_token(None) is None


async def test_token_endpoint_requests() -> None:
    settings = make_settings(
        microsoft_client_id="ms-client-id", microsoft_client_secret="ms-client-secret"
    )
    provider = oauth.provider(settings, "microsoft")
    assert provider is not None
    seen: list[dict[str, list[str]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        form = parse_qs(request.content.decode())
        seen.append(form)
        if form["grant_type"] == ["refresh_token"] and form["refresh_token"] == ["alt"]:
            return httpx.Response(400, json={"error": "invalid_grant"})
        return httpx.Response(
            200,
            json={
                "access_token": "a",
                "refresh_token": "r",
                "id_token": _id_token({"email": "x@outlook.de"}),
            },
        )

    transport = httpx.MockTransport(handler)
    tokens = await oauth.exchange_code(provider, "code", "verifier", "https://t/cb", transport)
    assert (tokens.access_token, tokens.refresh_token, tokens.email) == ("a", "r", "x@outlook.de")
    assert seen[0]["code_verifier"] == ["verifier"]
    assert seen[0]["client_secret"] == ["ms-client-secret"]
    refreshed = await oauth.refresh_access(provider, "neu", transport)
    assert refreshed.access_token == "a"
    assert "IMAP.AccessAsUser.All" in seen[1]["scope"][0]
    with pytest.raises(oauth.OAuthError, match="neu verbinden"):
        await oauth.refresh_access(provider, "alt", transport)
