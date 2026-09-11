"""Test-Infrastruktur: echte PostgreSQL-Datenbank, Redis per fakeredis."""

from __future__ import annotations

import base64
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

import pytest
from fakeredis import FakeAsyncRedis
from httpx import ASGITransport, AsyncClient, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import Settings
from app.db import create_engine, create_sessionmaker
from app.main import create_app
from app.models import Area, User
from app.resources import Resources
from app.security.crypto import Crypto
from app.security.middleware import CSRF_COOKIE
from app.security.passwords import hash_password
from app.security.ratelimit import RateLimiter
from app.services import external_calendars

EMPTY_ICS = b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Test//DE\r\nEND:VCALENDAR\r\n"


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests rufen nie echte Kalender-Adressen ab: öffentliche IP, leerer Kalender."""

    async def fake_resolve(host: str, port: int) -> list[str]:
        return ["93.184.216.34"]

    async def fake_fetch(
        url: str, *, allow_private: bool, etag: str | None = None, **_: object
    ) -> tuple[bytes | None, str | None]:
        return EMPTY_ICS, None

    monkeypatch.setattr(external_calendars, "resolve", fake_resolve)
    monkeypatch.setattr(external_calendars, "fetch_ics", fake_fetch)


BACKEND = Path(__file__).resolve().parent.parent
TEST_DATABASE_URL = os.environ.get(
    "TODOCH_TEST_DATABASE_URL", "postgresql+asyncpg://todoch:todoch@localhost:55432/todoch_test"
)
ORIGIN = "https://testserver"
TEST_KEY = base64.b64encode(bytes(range(32))).decode()
SETUP_TOKEN = "setup-token-0123456789"
PASSWORD = "Korrekt-Pferd-Batterie-Heftklammer"

TABLES = ["task_checklist_items", "tasks", "areas", "user_sessions", "users"]


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "origin": ORIGIN,
        "secret_key": "t" * 48,
        "encryption_keys": f"1:{TEST_KEY}",
        "database_url": TEST_DATABASE_URL,
        "redis_url": "redis://fakeredis",
        "setup_token": SETUP_TOKEN,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    env = {**os.environ, "TODOCH_DATABASE_URL": TEST_DATABASE_URL}
    for step in (["downgrade", "base"], ["upgrade", "head"]):
        subprocess.run(
            [sys.executable, "-m", "alembic", *step],
            cwd=BACKEND,
            env=env,
            check=True,
            capture_output=True,
        )


@pytest.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_engine(TEST_DATABASE_URL)
    yield eng
    await eng.dispose()


@pytest.fixture(autouse=True)
async def clean_database(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("ALTER TABLE audit_log DISABLE TRIGGER USER"))
        await conn.execute(text(f"TRUNCATE {', '.join([*TABLES, 'audit_log'])} CASCADE"))
        await conn.execute(text("ALTER TABLE audit_log ENABLE TRIGGER USER"))


@pytest.fixture
async def resources(engine: AsyncEngine) -> AsyncIterator[Resources]:
    settings = make_settings()
    redis = FakeAsyncRedis()
    yield Resources(
        settings=settings,
        engine=engine,
        sessionmaker=create_sessionmaker(engine),
        redis=redis,
        crypto=Crypto(settings.key_ring, settings.active_key_id),
        limiter=RateLimiter(redis),
    )
    await redis.aclose()


ClientFactory = Callable[[], Awaitable[AsyncClient]]


@pytest.fixture
async def client_factory(resources: Resources) -> AsyncIterator[ClientFactory]:
    app = create_app(resources.settings, resources)
    clients: list[AsyncClient] = []

    async def factory() -> AsyncClient:
        client = AsyncClient(
            transport=ASGITransport(app=app, client=("203.0.113.7", 50000)),
            base_url=ORIGIN,
            headers={"Origin": ORIGIN},
        )

        async def add_csrf(request: Request) -> None:
            token = client.cookies.get(CSRF_COOKIE)
            if token and "x-csrf-token" not in request.headers:
                request.headers["X-CSRF-Token"] = token

        client.event_hooks["request"].append(add_csrf)
        await client.get("/api/meta")  # holt das CSRF-Cookie
        clients.append(client)
        return client

    yield factory
    for client in clients:
        await client.aclose()


@pytest.fixture
async def client(client_factory: ClientFactory) -> AsyncClient:
    return await client_factory()


async def create_user(
    resources: Resources, email: str, *, password: str = PASSWORD, admin: bool = False
) -> User:
    async with resources.sessionmaker() as db:
        user = User(
            email=email,
            display_name=email.split("@")[0],
            password_hash=hash_password(password),
            is_admin=admin,
        )
        db.add(user)
        await db.flush()
        db.add(Area(owner_id=user.id, name="Arbeit", color="#2563eb", icon="briefcase"))
        db.add(Area(owner_id=user.id, name="Privat", color="#16a34a", icon="home", sort_order=1))
        await db.commit()
        return user


async def login(client: AsyncClient, email: str, password: str = PASSWORD) -> None:
    response = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text


@pytest.fixture
async def alice(resources: Resources, client: AsyncClient) -> AsyncClient:
    await create_user(resources, "alice@example.org", admin=True)
    await login(client, "alice@example.org")
    return client


@pytest.fixture
async def bob(resources: Resources, client_factory: ClientFactory) -> AsyncClient:
    await create_user(resources, "bob@example.org")
    bob_client = await client_factory()
    await login(bob_client, "bob@example.org")
    return bob_client
