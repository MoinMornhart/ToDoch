"""Erzeugt ``app/data/leaked-passwords.bin`` aus einer Textliste (ein Passwort pro Zeile).

Gespeichert werden nur sortierte 8-Byte-Präfixe der SHA-1-Hashes, keine Klartexte.
Quelle der mitgelieferten Datei: SecLists ``Passwords/Common-Credentials/Pwdb_top-100000.txt``
(MIT-Lizenz, https://github.com/danielmiessler/SecLists).

Aufruf:  python scripts/build_leaked_list.py passwoerter.txt
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

MIN_LENGTH = 8
TARGET = Path(__file__).resolve().parent.parent / "app" / "data" / "leaked-passwords.bin"


def main(source: str) -> None:
    prefixes: set[bytes] = set()
    with open(source, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            password = line.rstrip("\r\n")
            if len(password) < MIN_LENGTH:
                continue
            digest = hashlib.sha1(password.encode("utf-8"), usedforsecurity=False).digest()
            prefixes.add(digest[:8])
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_bytes(b"".join(sorted(prefixes)))
    print(f"{len(prefixes)} Einträge → {TARGET}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
