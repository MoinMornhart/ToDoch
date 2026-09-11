"""Passwort-Hashing (Argon2id) und Passwort-Richtlinie."""

from __future__ import annotations

from functools import lru_cache

import anyio
import anyio.to_thread
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.security.leaked import is_leaked

MIN_LENGTH = 12
MAX_LENGTH = 256

# Argon2id mit den Parametern aus RFC 9106 (zweite Empfehlung: 64 MiB, t=3, p=4).
_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)


class PasswordPolicyError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> tuple[bool, bool]:
    """Gibt ``(korrekt, muss_neu_gehasht_werden)`` zurück."""
    try:
        _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False, False
    return True, _hasher.check_needs_rehash(password_hash)


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    return _hasher.hash("todoch-timing-ausgleich-kein-echtes-passwort")


def dummy_verify(password: str) -> None:
    """Gleiche Rechenzeit wie eine echte Prüfung – gegen Nutzer-Enumeration per Timing."""
    verify_password(_dummy_hash(), password)


_limiter: anyio.CapacityLimiter | None = None


def _thread_limiter() -> anyio.CapacityLimiter:
    # Begrenzt parallele Argon2-Berechnungen (je 64 MiB) gegen Speicher-DoS.
    global _limiter
    if _limiter is None:
        _limiter = anyio.CapacityLimiter(4)
    return _limiter


async def hash_password_async(password: str) -> str:
    return await anyio.to_thread.run_sync(hash_password, password, limiter=_thread_limiter())


async def verify_password_async(password_hash: str, password: str) -> tuple[bool, bool]:
    return await anyio.to_thread.run_sync(
        verify_password, password_hash, password, limiter=_thread_limiter()
    )


async def dummy_verify_async(password: str) -> None:
    await anyio.to_thread.run_sync(dummy_verify, password, limiter=_thread_limiter())


def check_password_policy(password: str, *, email: str = "", display_name: str = "") -> None:
    if len(password) < MIN_LENGTH:
        raise PasswordPolicyError(
            "too_short", f"Das Passwort muss mindestens {MIN_LENGTH} Zeichen lang sein."
        )
    if len(password) > MAX_LENGTH:
        raise PasswordPolicyError(
            "too_long", f"Das Passwort darf höchstens {MAX_LENGTH} Zeichen lang sein."
        )
    if len(set(password)) < 4:
        raise PasswordPolicyError("too_simple", "Das Passwort ist zu einfach.")
    lowered = password.lower()
    for word in (email.split("@")[0].lower(), display_name.lower()):
        if len(word) >= 4 and word in lowered:
            raise PasswordPolicyError(
                "personal", "Das Passwort darf weder Namen noch E-Mail-Adresse enthalten."
            )
    if is_leaked(password):
        raise PasswordPolicyError(
            "leaked",
            "Dieses Passwort taucht in Listen gestohlener Passwörter auf. "
            "Bitte ein anderes wählen.",
        )
