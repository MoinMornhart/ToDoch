"""Regeln für Mails: einfache Bedingungen („enthält …“) → Aufgabe anlegen, als gelesen markieren.

Bedingungen sind reine Teilstring-Vergleiche ohne Groß-/Kleinschreibung – keine regulären
Ausdrücke, also auch kein ReDoS durch präparierte Mails oder Regeln. Alle ausgefüllten
Bedingungen einer Regel müssen zutreffen; es gelten alle passenden Regeln, eine Mail wird aber
höchstens einmal zur Aufgabe.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Area, MailMessage, MailRule, Task, User
from app.policy import visible_areas

QUOTE_CHARS = 3000


def task_notes(message: MailMessage, language: str = "de") -> str:
    """Notiz einer Aufgabe aus einer Mail: Absender, Datum und die Mail als Zitat."""
    sender = message.from_name or message.from_address or "?"
    if message.from_name and message.from_address:
        sender = f"{message.from_name} <{message.from_address}>"
    when = message.sent_at.strftime("%Y-%m-%d %H:%M") if message.sent_at else ""
    label = "From email by" if language == "en" else "Aus E-Mail von"
    body = message.body_text[:QUOTE_CHARS]
    if len(message.body_text) > QUOTE_CHARS:
        body += " …"
    quoted = "\n".join(f"> {line}" if line else ">" for line in body.split("\n"))
    return f"{label} {sender} · {when}\n\n{quoted}".strip()


def untitled(language: str) -> str:
    return "Email without subject" if language == "en" else "E-Mail ohne Betreff"


def matches(rule: MailRule, message: MailMessage) -> bool:
    if rule.account_id is not None and rule.account_id != message.account_id:
        return False
    checks = (
        (rule.from_contains, f"{message.from_name} {message.from_address}"),
        (rule.subject_contains, message.subject or ""),
        (rule.body_contains, message.body_text or ""),
    )
    wanted = [(needle.casefold(), haystack.casefold()) for needle, haystack in checks if needle]
    return bool(wanted) and all(needle in haystack for needle, haystack in wanted)


async def enabled_rules(db: AsyncSession, owner_id: object) -> list[MailRule]:
    return list(
        (
            await db.scalars(
                select(MailRule)
                .where(MailRule.owner_id == owner_id, MailRule.enabled.is_(True))
                .order_by(MailRule.created_at)
            )
        ).unique()
    )


async def _area_for(db: AsyncSession, owner: User, rule: MailRule) -> Area | None:
    query = select(Area).where(visible_areas(owner))
    area: Area | None = None
    if rule.area_id is not None:
        area = await db.scalar(query.where(Area.id == rule.area_id))
    if area is None:
        area = await db.scalar(query.order_by(Area.sort_order, Area.name).limit(1))
    return area


async def run_rules(
    db: AsyncSession,
    owner: User,
    rules: list[MailRule],
    messages: list[MailMessage],
    now: datetime | None = None,
) -> int:
    """Wendet die Regeln an (ohne Commit) und liefert, wie oft eine Regel gepasst hat."""
    now = now or datetime.now(UTC)
    language = "en" if owner.locale == "en" else "de"
    matched = 0
    for message in messages:
        for rule in rules:
            if not matches(rule, message):
                continue
            matched += 1
            rule.match_count = (rule.match_count or 0) + 1
            rule.last_matched_at = now
            if rule.mark_read:
                message.is_read = True
            if rule.create_task and message.task_id is None:
                area = await _area_for(db, owner, rule)
                if area is None:
                    continue
                task = Task(
                    area_id=area.id,
                    area=area,
                    created_by=owner.id,
                    title=(message.subject or untitled(language))[:300],
                    notes=task_notes(message, language),
                    priority=rule.priority,
                    tags=list(rule.tags or []),
                    source="mail_rule",
                    checklist=[],
                )
                db.add(task)
                await db.flush()
                message.task_id = task.id
    return matched
