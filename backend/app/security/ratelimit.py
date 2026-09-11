"""Rate-Limits und exponentielles Backoff auf Basis von Redis."""

from __future__ import annotations

import hashlib

from fastapi import HTTPException, status
from redis.asyncio import Redis


def hashed(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()[:32]


def too_many(retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Zu viele Versuche. Bitte später erneut versuchen.",
        headers={"Retry-After": str(max(1, retry_after))},
    )


class RateLimiter:
    def __init__(self, redis: Redis, prefix: str = "todoch:rl:") -> None:
        self.redis = redis
        self.prefix = prefix

    async def hit(self, bucket: str, key: str, *, limit: int, window: int) -> int | None:
        """Zählt einen Zugriff. Bei erreichtem Limit: Sekunden bis zur Freigabe."""
        name = f"{self.prefix}{bucket}:{key}"
        count = await self.redis.incr(name)
        if count == 1:
            await self.redis.expire(name, window)
        if count > limit:
            ttl = await self.redis.ttl(name)
            if ttl < 0:
                await self.redis.expire(name, window)
                ttl = window
            return int(ttl)
        return None

    async def enforce(self, bucket: str, key: str, *, limit: int, window: int) -> None:
        retry = await self.hit(bucket, key, limit=limit, window=window)
        if retry is not None:
            raise too_many(retry)

    async def locked_for(self, bucket: str, key: str) -> int | None:
        ttl = await self.redis.ttl(f"{self.prefix}{bucket}:lock:{key}")
        return int(ttl) if ttl and ttl > 0 else None

    async def register_failure(
        self,
        bucket: str,
        key: str,
        *,
        threshold: int = 5,
        base_seconds: int = 30,
        max_seconds: int = 3600,
    ) -> int | None:
        """Zählt einen Fehlversuch. Ab ``threshold`` wird exponentiell länger gesperrt."""
        name = f"{self.prefix}{bucket}:fail:{key}"
        failures = await self.redis.incr(name)
        await self.redis.expire(name, 24 * 3600)
        if failures < threshold:
            return None
        lock = min(max_seconds, base_seconds * 2 ** (failures - threshold))
        await self.redis.set(f"{self.prefix}{bucket}:lock:{key}", "1", ex=lock)
        return int(lock)

    async def reset(self, bucket: str, key: str) -> None:
        await self.redis.delete(
            f"{self.prefix}{bucket}:fail:{key}", f"{self.prefix}{bucket}:lock:{key}"
        )
