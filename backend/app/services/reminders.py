"""Fällige Terminerinnerungen finden und per Web-Push verschicken (Worker, jede Minute)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PushSubscription, ReminderLog, User
from app.security.crypto import Crypto
from app.services.events import Occurrence, occurrences
from app.services.push import Sender, push_to_user

# Verpasste Erinnerungen (z. B. nach einem Neustart) höchstens so lange nachholen.
LOOKBACK = timedelta(minutes=10)
# Längste Vorlaufzeit einer Erinnerung (4 Wochen) plus Puffer.
HORIZON_DAYS = 29
KEEP_LOG = timedelta(days=60)

TEXTS = {
    "de": {
        "all_day": "Ganztägig",
        "test_title": "ToDoch",
        "test": "Benachrichtigungen funktionieren.",
    },
    "en": {"all_day": "All day", "test_title": "ToDoch", "test": "Notifications are working."},
}


def texts(user: User) -> dict[str, str]:
    return TEXTS.get(user.locale, TEXTS["de"])


async def due_reminders(db: AsyncSession, now: datetime) -> list[tuple[User, Occurrence, int]]:
    with_devices = select(PushSubscription.user_id).distinct()
    users = await db.scalars(select(User).where(User.id.in_(with_devices), User.is_active))
    due: list[tuple[User, Occurrence, int]] = []
    for user in users:
        today = now.astimezone(ZoneInfo(user.timezone)).date()
        found = await occurrences(
            db, user, today - timedelta(days=1), today + timedelta(days=HORIZON_DAYS), user.timezone
        )
        for occ in found:
            if occ.event.status == "cancelled":
                continue
            for minutes in occ.event.reminders or []:
                fire_at = occ.start - timedelta(minutes=minutes)
                if now - LOOKBACK < fire_at <= now:
                    due.append((user, occ, minutes))
    return due


def reminder_payload(user: User, occ: Occurrence) -> dict[str, Any]:
    tz = ZoneInfo(user.timezone)
    if occ.event.all_day:
        when = texts(user)["all_day"]
        day = occ.start.date()
    else:
        start, end = occ.start.astimezone(tz), occ.end.astimezone(tz)
        when = f"{start:%H:%M}–{end:%H:%M}"
        day = start.date()
    body = f"{when} · {occ.event.location}" if occ.event.location else when
    return {
        "title": occ.event.title,
        "body": body,
        "url": f"/calendar?view=day&date={day.isoformat()}",
        "tag": occ.key,
    }


async def send_due_reminders(
    db: AsyncSession,
    crypto: Crypto,
    *,
    subject: str,
    now: datetime | None = None,
    sender: Sender | None = None,
) -> int:
    now = now or datetime.now(UTC)
    delivered = 0
    for user, occ, minutes in await due_reminders(db, now):
        inserted = await db.execute(
            insert(ReminderLog)
            .values(event_id=occ.event.id, occurrence_start=occ.start, minutes=minutes, sent_at=now)
            .on_conflict_do_nothing()
            .returning(ReminderLog.id)
        )
        if inserted.scalar_one_or_none() is None:
            continue  # schon verschickt
        await db.commit()
        delivered += await push_to_user(
            db, crypto, user.id, reminder_payload(user, occ), subject=subject, sender=sender
        )
    return delivered


async def cleanup_reminder_log(db: AsyncSession, now: datetime | None = None) -> None:
    cutoff = (now or datetime.now(UTC)) - KEEP_LOG
    await db.execute(delete(ReminderLog).where(ReminderLog.sent_at < cutoff))
    await db.commit()
