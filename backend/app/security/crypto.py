"""Verschlüsselung von Zugangsdaten (AES-256-GCM) mit Schlüsselbund für Key-Rotation.

Format eines Chiffrats: ``v1.<key-id>.<base64url(nonce || ciphertext+tag)>``.
Der Kontext (z. B. ``mail_account:<id>:password``) geht als AAD ein, damit ein
Chiffrat nicht in ein anderes Feld kopiert werden kann.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class DecryptionError(ValueError):
    pass


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class Crypto:
    def __init__(self, keys: dict[int, bytes], active: int) -> None:
        if active not in keys:
            raise ValueError("aktiver Schlüssel fehlt im Schlüsselbund")
        self._keys = dict(keys)
        self.active = active

    def encrypt(self, plaintext: str | bytes, *, context: str) -> str:
        data = plaintext.encode("utf-8") if isinstance(plaintext, str) else plaintext
        nonce = os.urandom(12)
        sealed = AESGCM(self._keys[self.active]).encrypt(nonce, data, context.encode("utf-8"))
        return f"v1.{self.active}.{_b64e(nonce + sealed)}"

    def decrypt(self, token: str, *, context: str) -> bytes:
        try:
            version, kid_text, payload = token.split(".", 2)
            key = self._keys[int(kid_text)]
            raw = _b64d(payload)
        except (ValueError, KeyError) as exc:
            raise DecryptionError("unbekanntes Format oder Schlüssel") from exc
        if version != "v1" or len(raw) < 12 + 16:
            raise DecryptionError("unbekanntes Format")
        try:
            return AESGCM(key).decrypt(raw[:12], raw[12:], context.encode("utf-8"))
        except InvalidTag as exc:
            raise DecryptionError("Entschlüsselung fehlgeschlagen") from exc

    def decrypt_str(self, token: str, *, context: str) -> str:
        return self.decrypt(token, context=context).decode("utf-8")

    def needs_rotation(self, token: str) -> bool:
        parts = token.split(".", 2)
        return len(parts) != 3 or parts[1] != str(self.active)

    def rotate(self, token: str, *, context: str) -> str:
        return self.encrypt(self.decrypt(token, context=context), context=context)


def sign(secret: str, message: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
    return _b64e(digest)


def verify_signature(secret: str, message: str, signature: str) -> bool:
    return hmac.compare_digest(sign(secret, message), signature)
