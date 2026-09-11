"""Postfächer von Google und Microsoft per Knopfdruck verbinden (OAuth 2.0 mit PKCE).

Ablauf: ToDoch leitet zur Anmeldeseite des Anbieters (mit einmaligem ``state`` und PKCE), bekommt
nach der Zustimmung einen Code, tauscht ihn direkt beim Anbieter gegen Tokens und meldet sich
damit per IMAP an (XOAUTH2). Gespeichert wird nur das Refresh-Token – verschlüsselt wie ein
Passwort; ein frisches Zugriffstoken holt ToDoch sich bei jedem Abgleich.

Die Adressen der Anbieter sind fest eingebaut (kein SSRF), Client-ID und Secret stehen nur in
der Server-Konfiguration (``todoch oauth google`` bzw. ``todoch oauth microsoft``).
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.config import Settings

TIMEOUT = httpx.Timeout(15.0, connect=10.0)
STATE_TTL = 600
PROVIDER_NAMES = ("google", "microsoft")

EXCHANGE_FAILED = "Die Anmeldung beim Anbieter ist fehlgeschlagen."
EXPIRED = "Die Verbindung zum Anbieter ist abgelaufen. Bitte das Postfach neu verbinden."
NOT_CONFIGURED = "Die Anmeldung bei diesem Anbieter ist auf dem Server nicht eingerichtet."


class OAuthError(Exception):
    """Verständliche Fehlermeldung (Deutsch; übersetzt in app/i18n.py)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class Provider:
    name: str
    label: str
    client_id: str
    client_secret: str
    auth_url: str
    token_url: str
    scope: str
    imap_host: str
    extra: tuple[tuple[str, str], ...] = ()


def provider(settings: Settings, name: str) -> Provider | None:
    """Der Anbieter mit Zugangsdaten aus der Konfiguration – oder None, wenn nicht eingerichtet."""
    if name == "google" and settings.google_client_id and settings.google_client_secret:
        return Provider(
            name="google",
            label="Google",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret.get_secret_value(),
            auth_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",  # noqa: S106
            scope="openid email https://mail.google.com/",
            imap_host="imap.gmail.com",
            # „consent“: Google liefert das Refresh-Token sonst nur beim allerersten Mal
            extra=(("access_type", "offline"), ("prompt", "consent")),
        )
    if name == "microsoft" and settings.microsoft_client_id and settings.microsoft_client_secret:
        base = f"https://login.microsoftonline.com/{settings.microsoft_tenant}/oauth2/v2.0"
        return Provider(
            name="microsoft",
            label="Microsoft",
            client_id=settings.microsoft_client_id,
            client_secret=settings.microsoft_client_secret.get_secret_value(),
            auth_url=f"{base}/authorize",
            token_url=f"{base}/token",
            scope="openid email offline_access https://outlook.office.com/IMAP.AccessAsUser.All",
            imap_host="outlook.office365.com",
            extra=(("prompt", "select_account"),),
        )
    return None


def configured(settings: Settings) -> dict[str, bool]:
    return {name: provider(settings, name) is not None for name in PROVIDER_NAMES}


def redirect_uri(settings: Settings, name: str) -> str:
    return f"{settings.origin}/api/mail/oauth/{name}/callback"


def new_state() -> str:
    return secrets.token_urlsafe(32)


def new_pkce() -> tuple[str, str]:
    """(verifier, challenge) nach RFC 7636 mit S256."""
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def authorization_url(p: Provider, redirect: str, state: str, challenge: str) -> str:
    params = {
        "client_id": p.client_id,
        "response_type": "code",
        "redirect_uri": redirect,
        "scope": p.scope,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        **dict(p.extra),
    }
    return f"{p.auth_url}?{urlencode(params)}"


@dataclass
class Tokens:
    access_token: str
    refresh_token: str | None
    email: str | None


def email_from_id_token(id_token: object) -> str | None:
    """Die Adresse steht im ID-Token. Es kommt per TLS direkt vom Token-Endpunkt des Anbieters –
    dann muss die Signatur nach OpenID Connect Core 3.1.3.7 nicht zusätzlich geprüft werden."""
    if not isinstance(id_token, str) or id_token.count(".") != 2:
        return None
    payload = id_token.split(".")[1]
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (ValueError, TypeError):
        return None
    if not isinstance(claims, dict):
        return None
    for key in ("email", "preferred_username"):
        value = claims.get(key)
        if isinstance(value, str) and "@" in value and len(value) <= 320:
            return value.strip().lower()
    return None


async def _token_request(
    p: Provider,
    data: dict[str, str],
    failure: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> Tokens:
    body = {"client_id": p.client_id, "client_secret": p.client_secret, **data}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, transport=transport) as client:
            response = await client.post(
                p.token_url, data=body, headers={"Accept": "application/json"}
            )
        payload = response.json() if response.status_code == 200 else None
    except (httpx.HTTPError, ValueError) as exc:
        raise OAuthError(failure) from exc
    if not isinstance(payload, dict):
        raise OAuthError(failure)
    access = payload.get("access_token")
    if not isinstance(access, str) or not access:
        raise OAuthError(failure)
    refresh = payload.get("refresh_token")
    return Tokens(
        access_token=access,
        refresh_token=refresh if isinstance(refresh, str) and refresh else None,
        email=email_from_id_token(payload.get("id_token")),
    )


async def exchange_code(
    p: Provider,
    code: str,
    verifier: str,
    redirect: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> Tokens:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": verifier,
        "redirect_uri": redirect,
    }
    return await _token_request(p, data, EXCHANGE_FAILED, transport)


async def refresh_access(
    p: Provider, refresh_token: str, transport: httpx.AsyncBaseTransport | None = None
) -> Tokens:
    data = {"grant_type": "refresh_token", "refresh_token": refresh_token}
    if p.name == "microsoft":
        data["scope"] = p.scope
    return await _token_request(p, data, EXPIRED, transport)


def xoauth2(user: str, access_token: str) -> bytes:
    """Anmeldestring für IMAP AUTHENTICATE XOAUTH2."""
    return f"user={user}\x01auth=Bearer {access_token}\x01\x01".encode()
