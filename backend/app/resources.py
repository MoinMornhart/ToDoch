"""Gemeinsame Laufzeit-Ressourcen (Datenbank, Redis, Krypto, Rate-Limiter)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import Settings
from app.db import create_engine, create_sessionmaker
from app.security.crypto import Crypto
from app.security.ratelimit import RateLimiter


@dataclass
class Resources:
    settings: Settings
    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]
    redis: Redis
    crypto: Crypto
    limiter: RateLimiter

    async def close(self) -> None:
        await self.redis.aclose()
        await self.engine.dispose()


def _connect_redis(settings: Settings) -> Redis:
    url = settings.redis_url.get_secret_value()
    if url.startswith("memory://"):
        # Nur für die lokale Entwicklung ohne Redis-Server (im Betrieb per Config verboten).
        from fakeredis import FakeAsyncRedis

        return cast(Redis, FakeAsyncRedis())
    return cast(Redis, Redis.from_url(url, decode_responses=False))


def build_resources(settings: Settings) -> Resources:
    engine = create_engine(settings.database_url.get_secret_value())
    redis = _connect_redis(settings)
    return Resources(
        settings=settings,
        engine=engine,
        sessionmaker=create_sessionmaker(engine),
        redis=redis,
        crypto=Crypto(settings.key_ring, settings.active_key_id),
        limiter=RateLimiter(redis),
    )
