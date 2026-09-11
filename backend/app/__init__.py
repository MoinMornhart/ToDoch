"""Todoch – selbst gehostete, minimalistische To-do- und Termin-App."""

from pathlib import Path


def _read_version() -> str:
    here = Path(__file__).resolve()
    for parent in (here.parent, *here.parents):
        candidate = parent / "VERSION"
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8").strip()
    return "0.0.0-dev"


__version__ = _read_version()
