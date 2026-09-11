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
from app.security.crypto import Crypto
from app.services.calendar_sync import sync_due_connections
from app.services.external_calendars import sync_due_calendars
from app.services.mail import sync_due_accounts
from app.services.reminders import cleanup_reminder_log, send_due_reminders


async def cleanup_sessions(ctx: dict[str, Any]) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=30)
    async with ctx["sessionmaker"]() as db:
        result = await db.execute(
            delete(UserSession).where(
                or_(UserSession.expires_at < cutoff, UserSession.revoked_at < cutoff)
            )
        )
        await db.commit()
        await cleanup_reminder_log(db)
        return int(result.rowcount or 0)


async def send_reminders(ctx: dict[str, Any]) -> int:
    async with ctx["sessionmaker"]() as db:
        return await send_due_reminders(db, ctx["crypto"], subject=ctx["settings"].origin)


async def sync_calendars(ctx: dict[str, Any]) -> int:
    async with ctx["sessionmaker"]() as db:
        return await sync_due_calendars(db, ctx["crypto"])


async def sync_mail(ctx: dict[str, Any]) -> int:
    async with ctx["sessionmaker"]() as db:
        return await sync_due_accounts(db, ctx["crypto"], ctx["settings"])


async def sync_online_calendars(ctx: dict[str, Any]) -> int:
    async with ctx["sessionmaker"]() as db:
        return await sync_due_connections(db, ctx["crypto"], ctx["settings"])


async def startup(ctx: dict[str, Any]) -> None:
    settings = load_settings()
    engine = create_engine(settings.database_url.get_secret_value())
    ctx["settings"] = settings
    ctx["engine"] = engine
    ctx["sessionmaker"] = create_sessionmaker(engine)
    ctx["crypto"] = Crypto(settings.key_ring, settings.active_key_id)


async def shutdown(ctx: dict[str, Any]) -> None:
    await ctx["engine"].dispose()


class WorkerSettings:
    functions: ClassVar[list[Any]] = [
        cleanup_sessions,
        send_reminders,
        sync_calendars,
        sync_mail,
        sync_online_calendars,
    ]
    cron_jobs: ClassVar[list[Any]] = [
        cron(cleanup_sessions, minute={17}, run_at_startup=True),
        # Jede Minute: fällige Terminerinnerungen verschicken
        cron(send_reminders, second={0}, timeout=50),
        # Alle 5 Minuten: abonnierte Kalender abgleichen, deren Intervall abgelaufen ist
        cron(sync_calendars, minute=set(range(0, 60, 5)), second={30}, timeout=240),
        # Alle 5 Minuten (versetzt): fällige E-Mail-Postfächer abholen
        cron(sync_mail, minute=set(range(2, 60, 5)), second={15}, timeout=240),
        # Alle 5 Minuten (versetzt): Zwei-Wege-Abgleich mit Google Kalender
        cron(sync_online_calendars, minute=set(range(4, 60, 5)), second={0}, timeout=240),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(
        os.environ.get("TODOCH_REDIS_URL", "redis://localhost:6379/0")
    )
    job_timeout = 300
    max_jobs = 10
    health_check_interval = 60
