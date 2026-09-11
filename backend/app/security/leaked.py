"""Offline-Abgleich gegen bekannte Leak-Passwörter.

``app/data/leaked-passwords.bin`` enthält sortiert die ersten 8 Byte des SHA-1-Hashes
jedes Passworts (erstellt mit ``scripts/build_leaked_list.py``). Es werden keine
Klartext-Passwörter mitgeliefert und keine Anfragen ins Internet gestellt.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

RECORD = 8
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "leaked-passwords.bin"


@lru_cache(maxsize=1)
def _table() -> bytes:
    try:
        data = DATA_FILE.read_bytes()
    except FileNotFoundError:
        return b""
    return data[: len(data) - len(data) % RECORD]


def prefix(password: str) -> bytes:
    return hashlib.sha1(password.encode("utf-8"), usedforsecurity=False).digest()[:RECORD]


def _contains(table: bytes, needle: bytes) -> bool:
    lo, hi = 0, len(table) // RECORD
    while lo < hi:
        mid = (lo + hi) // 2
        candidate = table[mid * RECORD : (mid + 1) * RECORD]
        if candidate < needle:
            lo = mid + 1
        elif candidate > needle:
            hi = mid
        else:
            return True
    return False


def is_leaked(password: str) -> bool:
    table = _table()
    if not table:
        return False
    return any(_contains(table, prefix(p)) for p in {password, password.lower()})
