"""Scheitert die Anmeldung beim Anbieter, sieht man den genauen Grund – nie das Secret."""

from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from httpx import AsyncClient

from app.resources import Resources
from app.services import mail_oauth as oauth
from tests.conftest import make_settings


async def test_token_endpoint_reason_is_reported(caplog: pytest.LogCaptureFixture) -> None:
    provider = oauth.provider(
        make_settings(microsoft_client_id="ms-id", microsoft_client_secret="falsches-secret"),
        "microsoft",
    )
    assert provider is not None

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={
                "error": "invalid_client",
                "error_description": "AADSTS7000215: Invalid client secret provided.",
            },
        )

    with pytest.raises(oauth.OAuthError) as failure:
        await oauth.exchange_code(provider, "c", "v", "https://t/cb", httpx.MockTransport(handler))
    assert failure.value.reason == "invalid_client"
    assert "AADSTS7000215" in caplog.text
    assert "falsches-secret" not in caplog.text

    def html(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="<html>Bad Gateway</html>")

    with pytest.raises(oauth.OAuthError) as broken:
        await oauth.exchange_code(provider, "c", "v", "https://t/cb", httpx.MockTransport(html))
    assert broken.value.reason == "http_502"


async def test_callback_passes_the_reason_on(
    alice: AsyncClient, resources: Resources, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = make_settings(google_client_id="id-123", google_client_secret="secret-123")
    object.__setattr__(resources, "settings", settings)

    async def rejected(*_: object) -> oauth.Tokens:
        raise oauth.OAuthError(oauth.EXCHANGE_FAILED, reason="invalid_grant")

    monkeypatch.setattr(oauth, "exchange_code", rejected)
    started = await alice.post("/api/mail/oauth/google/start")
    state = parse_qs(urlsplit(started.json()["url"]).query)["state"][0]
    back = await alice.get("/api/mail/oauth/google/callback", params={"code": "c", "state": state})
    location = urlsplit(back.headers["location"])
    assert location.path == "/mail"
    assert parse_qs(location.query) == {
        "oauth_error": ["failed"],
        "reason": ["invalid_grant"],
        "provider": ["google"],
    }
