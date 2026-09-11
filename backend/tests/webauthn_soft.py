"""Software-Authenticator für Tests: erzeugt echte WebAuthn-Antworten (ES256, Attestation „none“)."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from httpx import AsyncClient, Response
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url, encode_cbor

from tests.conftest import ORIGIN, PASSWORD

FLAG_UP, FLAG_UV, FLAG_AT = 0x01, 0x04, 0x40


class SoftAuthenticator:
    def __init__(self, *, rp_id: str = "testserver", origin: str = ORIGIN) -> None:
        self.rp_id = rp_id
        self.origin = origin
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = os.urandom(32)
        self.sign_count = 0
        self.user_handle: bytes | None = None

    def _client_data(self, kind: str, challenge: str) -> bytes:
        data = {"type": kind, "challenge": challenge, "origin": self.origin, "crossOrigin": False}
        return json.dumps(data).encode()

    def _rp_hash(self) -> bytes:
        return hashlib.sha256(self.rp_id.encode()).digest()

    def create(self, options: dict[str, Any]) -> dict[str, Any]:
        self.user_handle = base64url_to_bytes(options["user"]["id"])
        numbers = self.key.public_key().public_numbers()
        cose_key = encode_cbor(
            {
                1: 2,
                3: -7,
                -1: 1,
                -2: numbers.x.to_bytes(32, "big"),
                -3: numbers.y.to_bytes(32, "big"),
            }
        )
        auth_data = (
            self._rp_hash()
            + bytes([FLAG_UP | FLAG_UV | FLAG_AT])
            + self.sign_count.to_bytes(4, "big")
            + bytes(16)  # AAGUID
            + len(self.credential_id).to_bytes(2, "big")
            + self.credential_id
            + cose_key
        )
        attestation = encode_cbor({"fmt": "none", "attStmt": {}, "authData": auth_data})
        client_data = self._client_data("webauthn.create", options["challenge"])
        encoded_id = bytes_to_base64url(self.credential_id)
        return {
            "id": encoded_id,
            "rawId": encoded_id,
            "type": "public-key",
            "response": {
                "clientDataJSON": bytes_to_base64url(client_data),
                "attestationObject": bytes_to_base64url(attestation),
                "transports": ["internal", "hybrid", "unbekannt"],
            },
            "clientExtensionResults": {},
            "authenticatorAttachment": "platform",
        }

    def get(self, options: dict[str, Any], *, user_handle: bytes | None = None) -> dict[str, Any]:
        self.sign_count += 1
        auth_data = (
            self._rp_hash() + bytes([FLAG_UP | FLAG_UV]) + self.sign_count.to_bytes(4, "big")
        )
        client_data = self._client_data("webauthn.get", options["challenge"])
        signature = self.key.sign(
            auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256())
        )
        handle = user_handle if user_handle is not None else self.user_handle
        encoded_id = bytes_to_base64url(self.credential_id)
        return {
            "id": encoded_id,
            "rawId": encoded_id,
            "type": "public-key",
            "response": {
                "clientDataJSON": bytes_to_base64url(client_data),
                "authenticatorData": bytes_to_base64url(auth_data),
                "signature": bytes_to_base64url(signature),
                "userHandle": bytes_to_base64url(handle) if handle else None,
            },
            "clientExtensionResults": {},
        }


async def register_passkey(
    client: AsyncClient, authenticator: SoftAuthenticator, name: str = "Laptop"
) -> dict[str, Any]:
    options = await client.post("/api/auth/passkeys/register/options", json={"password": PASSWORD})
    assert options.status_code == 200, options.text
    response = await client.post(
        "/api/auth/passkeys/register/verify",
        json={"name": name, "credential": authenticator.create(options.json())},
    )
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


async def passkey_login(
    client: AsyncClient, authenticator: SoftAuthenticator, **kwargs: Any
) -> Response:
    options = (await client.post("/api/auth/passkeys/login/options")).json()
    return await client.post(
        "/api/auth/passkeys/login/verify",
        json={
            "challenge_id": options["challenge_id"],
            "credential": authenticator.get(options["options"], **kwargs),
        },
    )
