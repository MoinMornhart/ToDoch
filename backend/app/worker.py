"""Hintergrund-Jobs (ARQ). Start: ``arq app.worker.WorkerSettings``."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import delete, or_

from app.config import load_settings
from app.db import create_engine, create_sessionmaker
from app.models import UserSession


async def cleanup_sessions(ctx: dict[str, Any]) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=30)
    async with ctx["sessionmaker"]() as db:
        result = await db.execute(
            delete(UserSession).where(
                or_(UserSession.expires_at < cutoff, UserSession.revoked_at < cutoff)
            )
        )
        await db.commit()
        return int(result.rowcount or 0)


async def startup(ctx: dict[str, Any]) -> None:
    settings = load_settings()
    engine = create_engine(settings.database_url.get_secret_value())
    ctx["settings"] = settings
    ctx["engine"] = engine
    ctx["sessionmaker"] = create_sessionmaker(engine)


async def shutdown(ctx: dict[str, Any]) -> None:
    await ctx["engine"].dispose()


class WorkerSettings:
    functions: ClassVar[list[Any]] = [cleanup_sessions]
    cron_jobs: ClassVar[list[Any]] = [cron(cleanup_sessions, minute={17}, run_at_startup=True)]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(
        os.environ.get("TODOCH_REDIS_URL", "redis://localhost:6379/0")
    )
    job_timeout = 300
    max_jobs = 10
    health_check_interval = 60
