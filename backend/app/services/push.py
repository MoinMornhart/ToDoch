"""Web-Push (VAPID): Serverschlüssel, erlaubte Push-Dienste, Versand."""

from __future__ import annotations

import base64
import json
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

import anyio.to_thread
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PushSubscription, ServerKey
from app.security.crypto import Crypto

log = logging.getLogger(__name__)

# Nur an bekannte Push-Dienste senden – sonst könnte ein Abo den Server beliebige Adressen
# aufrufen lassen (SSRF).
ALLOWED_HOSTS = (
    "fcm.googleapis.com",
    "updates.push.services.mozilla.com",
    "push.services.mozilla.com",
    "web.push.apple.com",
    "notify.windows.com",
)
VAPID_KEY = "vapid"
MAX_FAILURES = 10

# (Abo-Daten, Nutzlast als JSON, privater Schlüssel als PEM, VAPID-Subject) → HTTP-Status
Sender = Callable[[dict[str, Any], str, bytes, str], int]


def endpoint_allowed(url: str) -> bool:
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return False
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not host or port not in (None, 443):
        return False
    return any(host == allowed or host.endswith("." + allowed) for allowed in ALLOWED_HOSTS)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _auth_context(subscription_id: uuid.UUID) -> str:
    return f"push_subscription:{subscription_id}:auth"


def encrypt_auth(crypto: Crypto, subscription_id: uuid.UUID, auth: str) -> str:
    return crypto.encrypt(auth, context=_auth_context(subscription_id))


async def vapid_keys(db: AsyncSession, crypto: Crypto) -> tuple[str, bytes]:
    """Öffentlicher Schlüssel (für den Browser) und privater Schlüssel (PEM).

    Wird beim ersten Bedarf erzeugt und als ein Datensatz gespeichert, damit parallele
    Aufrufe nie zu einem gemischten Schlüsselpaar führen.
    """
    stored = await db.get(ServerKey, VAPID_KEY)
    if stored is None:
        key = ec.generate_private_key(ec.SECP256R1())
        pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        public = _b64url(
            key.public_key().public_bytes(
                serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
            )
        )
        value = json.dumps(
            {"public": public, "private": crypto.encrypt(pem, context="server_key:vapid")}
        )
        await db.execute(
            insert(ServerKey).values(name=VAPID_KEY, value=value).on_conflict_do_nothing()
        )
        await db.commit()
        stored = await db.get(ServerKey, VAPID_KEY)
        assert stored is not None
    data = json.loads(stored.value)
    return str(data["public"]), crypto.decrypt(data["private"], context="server_key:vapid")


def send_notification_sync(
    subscription: dict[str, Any], payload: str, private_pem: bytes, subject: str
) -> int:
    """Eine Benachrichtigung zustellen (blockierend – läuft in einem Thread)."""
    from py_vapid import Vapid
    from pywebpush import WebPushException, webpush

    try:
        response = webpush(
            subscription_info=subscription,
            data=payload,
            vapid_private_key=Vapid.from_pem(private_pem),
            vapid_claims={"sub": subject},
            ttl=3600,
            timeout=10,
        )
    except WebPushException as exc:
        return int(exc.response.status_code) if exc.response is not None else 0
    except Exception:
        log.warning("Push-Zustellung fehlgeschlagen", exc_info=True)
        return 0
    return int(getattr(response, "status_code", 201))


async def push_to_user(
    db: AsyncSession,
    crypto: Crypto,
    user_id: uuid.UUID,
    payload: dict[str, Any],
    *,
    subject: str,
    sender: Sender | None = None,
) -> int:
    """An alle Geräte eines Nutzers senden. Gibt die Zahl erfolgreicher Zustellungen zurück."""
    send = sender or send_notification_sync
    subscriptions = list(
        await db.scalars(select(PushSubscription).where(PushSubscription.user_id == user_id))
    )
    if not subscriptions:
        return 0
    _, private_pem = await vapid_keys(db, crypto)
    body = json.dumps(payload, ensure_ascii=False)
    delivered = 0
    for subscription in subscriptions:
        info = {
            "endpoint": subscription.endpoint,
            "keys": {
                "p256dh": subscription.p256dh,
                "auth": crypto.decrypt_str(
                    subscription.auth_enc, context=_auth_context(subscription.id)
                ),
            },
        }
        status = await anyio.to_thread.run_sync(send, info, body, private_pem, subject)
        if status in (404, 410):  # Abo existiert beim Push-Dienst nicht mehr
            await db.delete(subscription)
        elif 200 <= status < 300:
            subscription.last_success_at = datetime.now(UTC)
            subscription.failures = 0
            delivered += 1
        else:
            subscription.failures += 1
            if subscription.failures >= MAX_FAILURES:
                await db.delete(subscription)
    await db.commit()
    return delivered
