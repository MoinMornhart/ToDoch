# ADR 0001 – Technik-Stack

**Status:** angenommen (v0.0.1)

## Kontext

ToDoch wurde von Grund auf neu aufgebaut. Vorgabe: Python/FastAPI, PostgreSQL, Redis + ARQ,
SvelteKit/TypeScript/Tailwind als PWA, Caddy, Docker Compose, Tests mit pytest/Vitest/Playwright.

## Entscheidung

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2 (async, asyncpg), Alembic, Pydantic v2,
  argon2-cffi, cryptography, markdown-it-py + nh3. Paketverwaltung mit uv (Lockfile im Repo).
- **Jobs:** ARQ auf Redis-kompatiblem Server (siehe ADR 0003).
- **Frontend:** SvelteKit 2 mit Svelte 5 (Runes), Tailwind 4, `@lucide/svelte`-Icons – alles
  gebündelt, keine Laufzeit-CDNs. Keine UI-Bibliothek, um Umfang und Abhängigkeiten klein zu halten.
- **Qualität:** ruff, mypy (strict), svelte-check, Prettier; CI mit pip-audit und npm audit.

## Folgen

- Zwei Laufzeiten (Python, Node nur zum Bauen). Das Web-Image enthält nur Caddy + statische Dateien.
- Async-SQLAlchemy erfordert explizites Laden von Beziehungen (lazy="joined"/"selectin").
