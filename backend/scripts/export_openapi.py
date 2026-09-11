"""Schreibt die OpenAPI-Beschreibung nach docs/openapi.json.

Aufruf:  uv run python scripts/export_openapi.py
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

from app.config import Settings
from app.main import create_app

TARGET = Path(__file__).resolve().parents[2] / "docs" / "openapi.json"


def main() -> None:
    settings = Settings(
        environment="development",
        origin="http://localhost:5173",
        secret_key="openapi-export-" + "x" * 32,
        encryption_keys="1:" + base64.b64encode(bytes(32)).decode(),
        database_url="postgresql+asyncpg://unused",
        redis_url="memory://",
    )
    schema = create_app(settings).openapi()
    TARGET.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OpenAPI → {TARGET}")


if __name__ == "__main__":
    main()
