"""ASGI-Middleware: Security-Header, Größenlimit, Origin- und CSRF-Prüfung.

CSRF-Schutz nach dem Double-Submit-Verfahren: Jede Antwort der API setzt – falls noch
nicht vorhanden – das Cookie ``__Host-todoch_csrf``. Zustandsändernde Anfragen müssen
denselben Wert im Header ``X-CSRF-Token`` mitschicken *und* von der eigenen Origin kommen.
"""

from __future__ import annotations

import json
import secrets
from collections.abc import Iterable
from hmac import compare_digest
from http.cookies import SimpleCookie

from fastapi import HTTPException
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import Settings
from app.i18n import language_from, translate

SESSION_COOKIE = "__Host-todoch_session"
CSRF_COOKIE = "__Host-todoch_csrf"
CSRF_HEADER = "x-csrf-token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

PERMISSIONS_POLICY = (
    "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), "
    "microphone=(), payment=(), usb=(), interest-cohort=(), "
    "publickey-credentials-get=(self), publickey-credentials-create=(self)"
)


def parse_cookies(header: str | None) -> dict[str, str]:
    if not header:
        return {}
    jar: SimpleCookie = SimpleCookie()
    try:
        jar.load(header)
    except Exception:  # kaputte Cookies ignorieren
        return {}
    return {key: morsel.value for key, morsel in jar.items()}


def csrf_cookie_header(value: str, *, max_age: int = 60 * 60 * 24 * 30) -> str:
    return f"{CSRF_COOKIE}={value}; Path=/; Secure; SameSite=Lax; Max-Age={max_age}"


def security_headers(settings: Settings) -> list[tuple[str, str]]:
    headers = [
        ("x-content-type-options", "nosniff"),
        ("referrer-policy", "no-referrer"),
        ("x-frame-options", "DENY"),
        ("cross-origin-opener-policy", "same-origin"),
        ("cross-origin-resource-policy", "same-origin"),
        ("permissions-policy", PERMISSIONS_POLICY),
        (
            "content-security-policy",
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
        ),
    ]
    if settings.is_https:
        headers.append(("strict-transport-security", "max-age=63072000; includeSubDomains"))
    return headers


class SecurityMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        settings: Settings,
        csrf_exempt_prefixes: Iterable[str] = ("/api/health",),
    ) -> None:
        self.app = app
        self.settings = settings
        self.exempt = tuple(csrf_exempt_prefixes)
        self.headers = security_headers(settings)
        self.origin = settings.origin

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_headers = Headers(scope=scope)
        path: str = scope["path"]
        method: str = scope["method"]
        is_api = path.startswith("/api/")
        limit = self.settings.max_body_bytes
        language = language_from(request_headers.get("accept-language"))

        length = request_headers.get("content-length")
        if length is not None and (not length.isdigit() or int(length) > limit):
            await self._reject(send, 413, translate("Die Anfrage ist zu groß.", language))
            return

        cookies = parse_cookies(request_headers.get("cookie"))
        csrf_cookie = cookies.get(CSRF_COOKIE)

        if is_api and method not in SAFE_METHODS and not path.startswith(self.exempt):
            if not self._origin_allowed(request_headers):
                message = "Die Herkunft der Anfrage ist nicht erlaubt."
                await self._reject(send, 403, translate(message, language))
                return
            token = request_headers.get(CSRF_HEADER, "")
            if not csrf_cookie or not token or not compare_digest(csrf_cookie, token):
                message = "CSRF-Prüfung fehlgeschlagen. Bitte die Seite neu laden."
                await self._reject(send, 403, translate(message, language))
                return

        new_csrf = secrets.token_urlsafe(32) if is_api and not csrf_cookie else None
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise HTTPException(status_code=413, detail="Die Anfrage ist zu groß.")
            return message

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in self.headers:
                    if name not in headers:
                        headers[name] = value
                if is_api and "cache-control" not in headers:
                    headers["cache-control"] = "no-store"
                if new_csrf:
                    headers.append("set-cookie", csrf_cookie_header(new_csrf))
            await send(message)

        await self.app(scope, limited_receive, send_with_headers)

    def _origin_allowed(self, headers: Headers) -> bool:
        origin = headers.get("origin")
        if origin is not None:
            return compare_digest(origin.rstrip("/"), self.origin)
        referer = headers.get("referer")
        if referer is not None:
            return referer == self.origin or referer.startswith(self.origin + "/")
        return False

    async def _reject(self, send: Send, status: int, detail: str) -> None:
        body = json.dumps({"detail": detail}, ensure_ascii=False).encode("utf-8")
        headers = [
            (b"content-type", b"application/json; charset=utf-8"),
            (b"content-length", str(len(body)).encode()),
            (b"cache-control", b"no-store"),
        ]
        headers += [(k.encode(), v.encode()) for k, v in self.headers]
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})
