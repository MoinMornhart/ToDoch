"""Zwei-Faktor mit Authenticator-App (TOTP, RFC 6238) und Wiederherstellungscodes.

- 6-stellige Codes, 30-Sekunden-Schritte, ein Schritt Toleranz in beide Richtungen
- Jeder Schritt gilt nur einmal (``totp_last_step``) – ein abgefangener Code nützt nichts
- Wiederherstellungscodes: 10 Stück, zufällig, nur als SHA-256 gespeichert, je einmal gültig
"""

from __future__ import annotations

import hashlib
import io
import secrets
import time

import pyotp
import segno

ISSUER = "ToDoch"
STEP = 30
RECOVERY_COUNT = 10
# Ohne leicht verwechselbare Zeichen (0/o, 1/l/i)
ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


def new_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, account: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=account, issuer_name=ISSUER)


def qr_svg(uri: str) -> str:
    """QR-Code als SVG ohne Inline-Styles – passt zur Content-Security-Policy."""
    buffer = io.BytesIO()
    segno.make(uri, error="m").save(
        buffer, kind="svg", scale=5, border=2, xmldecl=False, nl=False, dark="#000", light="#fff"
    )
    return buffer.getvalue().decode("utf-8")


def current_step(now: float | None = None) -> int:
    return int((now if now is not None else time.time()) // STEP)


def verify(secret: str, code: str, last_step: int | None, now: float | None = None) -> int | None:
    """Liefert den Zeitschritt des gültigen Codes – oder None. Bereits benutzte Schritte
    (und ältere) werden abgelehnt."""
    code = code.strip().replace(" ", "")
    if len(code) != 6 or not code.isdigit():
        return None
    totp = pyotp.TOTP(secret)
    step = current_step(now)
    for candidate in (step - 1, step, step + 1):
        if last_step is not None and candidate <= last_step:
            continue
        if secrets.compare_digest(totp.at(candidate * STEP), code):
            return candidate
    return None


def normalize_recovery(code: str) -> str:
    return "".join(ch for ch in code.lower() if ch.isalnum())


def hash_recovery(code: str) -> bytes:
    return hashlib.sha256(normalize_recovery(code).encode("ascii", "ignore")).digest()


def new_recovery_codes() -> list[str]:
    codes = []
    for _ in range(RECOVERY_COUNT):
        raw = "".join(secrets.choice(ALPHABET) for _ in range(10))
        codes.append(f"{raw[:5]}-{raw[5:]}")
    return codes


def looks_like_totp(code: str) -> bool:
    cleaned = code.strip().replace(" ", "")
    return len(cleaned) == 6 and cleaned.isdigit()
