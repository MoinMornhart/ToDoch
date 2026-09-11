"""Regeln für Mails: anlegen, ändern, löschen und auf vorhandene Mails anwenden."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import DB, CurrentUser
from app.api.tasks import area_for_new_item
from app.models import MailAccount, MailMessage, MailRule, User
from app.schemas.mail_rules import (
    NEEDS_ACTION,
    NEEDS_CONDITION,
    MailRuleIn,
    MailRuleOut,
    MailRulePatch,
    RuleApplyOut,
)
from app.services.mail_rules import run_rules

router = APIRouter(prefix="/api/mail/rules", tags=["mail"])

MAX_RULES = 50
APPLY_LIMIT = 2000
FIELDS = (
    "name",
    "from_contains",
    "subject_contains",
    "body_contains",
    "create_task",
    "mark_read",
    "priority",
    "tags",
    "enabled",
)


def rule_out(rule: MailRule) -> MailRuleOut:
    return MailRuleOut(
        id=rule.id,
        name=rule.name,
        account_id=rule.account_id,
        account_name=rule.account.name if rule.account else None,
        from_contains=rule.from_contains,
        subject_contains=rule.subject_contains,
        body_contains=rule.body_contains,
        create_task=rule.create_task,
        mark_read=rule.mark_read,
        area_id=rule.area_id,
        area_name=rule.area.name if rule.area else None,
        priority=rule.priority,
        tags=list(rule.tags or []),
        enabled=rule.enabled,
        match_count=rule.match_count,
        last_matched_at=rule.last_matched_at,
        created_at=rule.created_at,
    )


async def _own_rule(db: DB, user: User, rule_id: uuid.UUID) -> MailRule:
    rule = await db.get(MailRule, rule_id)
    if rule is None or rule.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nicht gefunden.")
    return rule


async def _check_account(db: DB, user: User, account_id: uuid.UUID | None) -> None:
    if account_id is None:
        return
    account = await db.get(MailAccount, account_id)
    if account is None or account.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nicht gefunden.")


async def _reloaded(db: DB, rule: MailRule) -> MailRuleOut:
    await db.commit()
    await db.refresh(rule)
    return rule_out(rule)


@router.get("", response_model=list[MailRuleOut])
async def list_rules(db: DB, user: CurrentUser) -> list[MailRuleOut]:
    rules = await db.scalars(
        select(MailRule).where(MailRule.owner_id == user.id).order_by(MailRule.created_at)
    )
    return [rule_out(rule) for rule in rules.unique()]


@router.post("", response_model=MailRuleOut, status_code=status.HTTP_201_CREATED)
async def add_rule(body: MailRuleIn, db: DB, user: CurrentUser) -> MailRuleOut:
    count = await db.scalar(
        select(func.count()).select_from(MailRule).where(MailRule.owner_id == user.id)
    )
    if (count or 0) >= MAX_RULES:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Höchstens {MAX_RULES} Regeln möglich.")
    await _check_account(db, user, body.account_id)
    if body.area_id is not None:
        await area_for_new_item(db, user, body.area_id)
    rule = MailRule(
        owner_id=user.id,
        account_id=body.account_id,
        area_id=body.area_id,
        match_count=0,
        **{name: getattr(body, name) for name in FIELDS},
    )
    db.add(rule)
    return await _reloaded(db, rule)


@router.patch("/{rule_id}", response_model=MailRuleOut)
async def update_rule(
    rule_id: uuid.UUID, body: MailRulePatch, db: DB, user: CurrentUser
) -> MailRuleOut:
    rule = await _own_rule(db, user, rule_id)
    fields = body.model_fields_set
    for name in FIELDS:
        value = getattr(body, name)
        if name in fields and value is not None:
            setattr(rule, name, value)
    # Postfach und Bereich dürfen auch wieder geleert werden (null = alle / erster Bereich)
    if "account_id" in fields:
        await _check_account(db, user, body.account_id)
        rule.account_id = body.account_id
    if "area_id" in fields:
        if body.area_id is not None:
            await area_for_new_item(db, user, body.area_id)
        rule.area_id = body.area_id
    if not (rule.from_contains or rule.subject_contains or rule.body_contains):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, NEEDS_CONDITION)
    if not (rule.create_task or rule.mark_read):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, NEEDS_ACTION)
    return await _reloaded(db, rule)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(rule_id: uuid.UUID, db: DB, user: CurrentUser) -> None:
    rule = await _own_rule(db, user, rule_id)
    await db.delete(rule)
    await db.commit()


@router.post("/{rule_id}/apply", response_model=RuleApplyOut)
async def apply_rule(rule_id: uuid.UUID, db: DB, user: CurrentUser) -> RuleApplyOut:
    """Wendet die Regel auf abgeholte Mails an – vorhandene Aufgaben werden nicht verdoppelt."""
    rule = await _own_rule(db, user, rule_id)
    messages = list(
        (
            await db.scalars(
                select(MailMessage)
                .join(MailAccount, MailMessage.account_id == MailAccount.id)
                .where(MailAccount.owner_id == user.id)
                .order_by(MailMessage.received_at.desc())
                .limit(APPLY_LIMIT)
            )
        ).unique()
    )
    matched = await run_rules(db, user, [rule], messages)
    await db.commit()
    return RuleApplyOut(matched=matched)
