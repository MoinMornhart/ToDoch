"""E-Mail: Postfächer per IMAP einbinden, Mails lesen und Aufgaben daraus machen."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select

from app.api.deps import DB, CurrentUser, Res, client_ip
from app.api.events import conflicts_out, create_event_row, event_out
from app.api.tasks import area_for_new_item, task_out
from app.i18n import language_from, translate
from app.models import MailAccount, MailMessage, Task, User
from app.policy import Action, authorize
from app.schemas.events import EventIn, EventWriteOut
from app.schemas.mail import (
    MailAccountIn,
    MailAccountOut,
    MailAccountPatch,
    MailMessageDetail,
    MailMessageOut,
    MailMessagePatch,
    MailTaskIn,
    SuggestionOut,
)
from app.schemas.tasks import TaskOut
from app.services import audit, mail

router = APIRouter(prefix="/api/mail", tags=["mail"])

MAX_ACCOUNTS = 10
QUOTE_CHARS = 3000


def _language(request: Request) -> str:
    return language_from(request.headers.get("accept-language"))


def account_out(account: MailAccount, unread: int, language: str = "de") -> MailAccountOut:
    return MailAccountOut(
        id=account.id,
        name=account.name,
        email=account.email,
        host=account.imap_host,
        port=account.imap_port,
        security=account.security,
        username=account.username,
        folder=account.folder,
        refresh_minutes=account.refresh_minutes,
        enabled=account.enabled,
        message_count=account.message_count,
        unread_count=unread,
        last_synced_at=account.last_synced_at,
        last_success_at=account.last_success_at,
        last_error=translate(account.last_error, language) if account.last_error else None,
        created_at=account.created_at,
        auth=account.auth,
        provider=account.oauth_provider,
    )


def suggestion_out(message: MailMessage, tzid: str) -> SuggestionOut | None:
    data = message.suggestion
    if not data or message.suggestion_status is None:
        return None
    start = datetime.fromisoformat(str(data["start"]))
    end = datetime.fromisoformat(str(data["end"]))
    all_day = bool(data.get("all_day"))
    if all_day:
        start_date, start_time = start.date(), None
        end_date, end_time = max(start.date(), (end - timedelta(days=1)).date()), None
    else:
        zone = ZoneInfo(tzid)
        local_start, local_end = start.astimezone(zone), end.astimezone(zone)
        start_date, start_time = local_start.date(), local_start.time()
        end_date, end_time = local_end.date(), local_end.time()
    return SuggestionOut(
        source=str(data.get("source", "text")),
        title=str(data.get("title", "")),
        location=str(data.get("location", "")),
        all_day=all_day,
        start_date=start_date,
        start_time=start_time,
        end_date=end_date,
        end_time=end_time,
        status=message.suggestion_status,
    )


def _message_fields(message: MailMessage, tzid: str) -> dict[str, object]:
    return {
        "suggestion": suggestion_out(message, tzid),
        "event_id": message.event_id,
        "id": message.id,
        "account_id": message.account_id,
        "account_name": message.account.name,
        "from_name": message.from_name,
        "from_address": message.from_address,
        "subject": message.subject,
        "sent_at": message.sent_at,
        "received_at": message.received_at,
        "snippet": message.snippet,
        "is_read": message.is_read,
        "attachment_count": message.attachment_count,
        "task_id": message.task_id,
    }


def message_detail(message: MailMessage, tzid: str) -> MailMessageDetail:
    return MailMessageDetail(
        **_message_fields(message, tzid),
        message_id=message.message_id,
        recipients=message.recipients,
        body_text=message.body_text,
        has_html=message.has_html,
        truncated=message.truncated,
    )


async def _unread(db: DB, account_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not account_ids:
        return {}
    rows = await db.execute(
        select(MailMessage.account_id, func.count())
        .where(MailMessage.account_id.in_(account_ids), MailMessage.is_read.is_(False))
        .group_by(MailMessage.account_id)
    )
    return {account_id: int(count) for account_id, count in rows.tuples()}


async def _account_out(db: DB, account: MailAccount, request: Request) -> MailAccountOut:
    unread = await _unread(db, [account.id])
    return account_out(account, unread.get(account.id, 0), _language(request))


async def _own_account(db: DB, user: User, account_id: uuid.UUID) -> MailAccount:
    account = await db.get(MailAccount, account_id)
    if account is None or account.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nicht gefunden.")
    return account


async def _own_message(db: DB, user: User, mail_id: uuid.UUID) -> MailMessage:
    message = await db.get(MailMessage, mail_id)
    if message is None or message.account.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nicht gefunden.")
    return message


# --- Postfächer -----------------------------------------------------------------------------


@router.get("/accounts", response_model=list[MailAccountOut])
async def list_accounts(request: Request, db: DB, user: CurrentUser) -> list[MailAccountOut]:
    accounts = list(
        await db.scalars(
            select(MailAccount)
            .where(MailAccount.owner_id == user.id)
            .order_by(MailAccount.created_at)
        )
    )
    unread = await _unread(db, [a.id for a in accounts])
    language = _language(request)
    return [account_out(a, unread.get(a.id, 0), language) for a in accounts]


@router.post("/accounts", response_model=MailAccountOut, status_code=status.HTTP_201_CREATED)
async def add_account(
    body: MailAccountIn, request: Request, db: DB, res: Res, user: CurrentUser
) -> MailAccountOut:
    await res.limiter.enforce("mail-add", str(user.id), limit=10, window=600)
    count = await db.scalar(
        select(func.count()).select_from(MailAccount).where(MailAccount.owner_id == user.id)
    )
    if (count or 0) >= MAX_ACCOUNTS:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Höchstens {MAX_ACCOUNTS} Postfächer möglich."
        )
    target = mail.ImapTarget(
        host=body.imap_host.lower(),
        port=body.imap_port,
        security=body.security,
        username=body.username or body.email,
        password=body.password,
        folder=body.folder,
    )
    # Erst anmelden und abholen – falsche Zugangsdaten werden gar nicht gespeichert
    try:
        result = await mail.fetch_mailbox(
            target,
            allow_private=user.is_admin,
            uidvalidity=None,
            last_uid=0,
            limit=mail.FIRST_BATCH,
        )
    except mail.MailError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, exc.message) from exc

    now = datetime.now(UTC)
    account_id = uuid.uuid4()
    account = MailAccount(
        id=account_id,
        owner_id=user.id,
        name=body.name or body.email,
        email=body.email,
        imap_host=target.host,
        imap_port=target.port,
        security=target.security,
        username=target.username,
        password_encrypted=res.crypto.encrypt(
            body.password, context=mail.password_context(account_id)
        ),
        folder=target.folder,
        refresh_minutes=body.refresh_minutes,
        enabled=True,
        last_uid=0,
        message_count=0,
        last_synced_at=now,
        last_success_at=now,
    )
    db.add(account)
    await db.flush()
    await mail.apply_result(db, account, result, tzid=user.timezone)
    audit.record(
        db,
        "mail.account_added",
        user_id=user.id,
        ip=client_ip(request),
        account=str(account_id),
        host=target.host,
    )
    await db.commit()
    await db.refresh(account)
    return await _account_out(db, account, request)


@router.patch("/accounts/{account_id}", response_model=MailAccountOut)
async def update_account(
    account_id: uuid.UUID,
    body: MailAccountPatch,
    request: Request,
    db: DB,
    res: Res,
    user: CurrentUser,
) -> MailAccountOut:
    account = await _own_account(db, user, account_id)
    fields = body.model_fields_set
    if "name" in fields and body.name is not None:
        account.name = body.name
    if "refresh_minutes" in fields and body.refresh_minutes is not None:
        account.refresh_minutes = body.refresh_minutes
    if "enabled" in fields and body.enabled is not None:
        account.enabled = body.enabled
    if "password" in fields and body.password is not None:
        account.password_encrypted = res.crypto.encrypt(
            body.password, context=mail.password_context(account.id)
        )
        audit.record(
            db,
            "mail.password_changed",
            user_id=user.id,
            ip=client_ip(request),
            account=str(account.id),
        )
        await db.flush()
        await mail.sync_account(db, res.crypto, account, user, settings=res.settings)
    else:
        await db.commit()
    await db.refresh(account)
    return await _account_out(db, account, request)


@router.post("/accounts/{account_id}/sync", response_model=MailAccountOut)
async def sync_now(
    account_id: uuid.UUID, request: Request, db: DB, res: Res, user: CurrentUser
) -> MailAccountOut:
    account = await _own_account(db, user, account_id)
    await res.limiter.enforce("mail-sync", str(account.id), limit=10, window=600)
    await mail.sync_account(db, res.crypto, account, user, settings=res.settings)
    await db.refresh(account)
    return await _account_out(db, account, request)


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: uuid.UUID, request: Request, db: DB, user: CurrentUser
) -> None:
    """Entfernt das Postfach samt abgeholter Mails aus ToDoch – auf dem Server bleibt alles."""
    account = await _own_account(db, user, account_id)
    await db.delete(account)
    audit.record(
        db, "mail.account_removed", user_id=user.id, ip=client_ip(request), account=str(account_id)
    )
    await db.commit()


# --- Mails ----------------------------------------------------------------------------------


@router.get("/messages", response_model=list[MailMessageOut])
async def list_messages(
    db: DB,
    user: CurrentUser,
    account_id: uuid.UUID | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    unread: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> list[MailMessageOut]:
    query = (
        select(MailMessage)
        .join(MailAccount, MailMessage.account_id == MailAccount.id)
        .where(MailAccount.owner_id == user.id)
    )
    if account_id is not None:
        query = query.where(MailMessage.account_id == account_id)
    if unread:
        query = query.where(MailMessage.is_read.is_(False))
    if q and q.strip():
        term = q.strip()
        query = query.where(
            or_(
                MailMessage.subject.icontains(term, autoescape=True),
                MailMessage.from_name.icontains(term, autoescape=True),
                MailMessage.from_address.icontains(term, autoescape=True),
                MailMessage.snippet.icontains(term, autoescape=True),
            )
        )
    query = (
        query.order_by(
            func.coalesce(MailMessage.sent_at, MailMessage.received_at).desc(),
            MailMessage.uid.desc(),
        )
        .offset(offset)
        .limit(limit)
    )
    messages = (await db.scalars(query)).unique()
    return [MailMessageOut(**_message_fields(m, user.timezone)) for m in messages]


@router.get("/suggestions", response_model=list[MailMessageOut])
async def list_suggestions(db: DB, user: CurrentUser) -> list[MailMessageOut]:
    """Bestätigungs-Inbox: Mails mit erkanntem, noch offenem Terminvorschlag."""
    rows = await db.scalars(
        select(MailMessage)
        .join(MailAccount, MailMessage.account_id == MailAccount.id)
        .where(MailAccount.owner_id == user.id, MailMessage.suggestion_status == "pending")
        .order_by(MailMessage.received_at.desc(), MailMessage.uid.desc())
        .limit(50)
    )
    return [MailMessageOut(**_message_fields(m, user.timezone)) for m in rows.unique()]


@router.get("/messages/{mail_id}", response_model=MailMessageDetail)
async def get_message(mail_id: uuid.UUID, db: DB, user: CurrentUser) -> MailMessageDetail:
    """Öffnen markiert die Mail in ToDoch als gelesen (auf dem Server bleibt sie unverändert)."""
    message = await _own_message(db, user, mail_id)
    if not message.is_read:
        message.is_read = True
        await db.commit()
        await db.refresh(message)
    return message_detail(message, user.timezone)


@router.patch("/messages/{mail_id}", response_model=MailMessageDetail)
async def update_message(
    mail_id: uuid.UUID, body: MailMessagePatch, db: DB, user: CurrentUser
) -> MailMessageDetail:
    message = await _own_message(db, user, mail_id)
    if body.is_read is not None:
        message.is_read = body.is_read
    await db.commit()
    await db.refresh(message)
    return message_detail(message, user.timezone)


@router.post(
    "/messages/{mail_id}/suggestion/accept",
    response_model=EventWriteOut,
    status_code=status.HTTP_201_CREATED,
)
async def accept_suggestion(
    mail_id: uuid.UUID,
    request: Request,
    db: DB,
    user: CurrentUser,
    body: MailTaskIn | None = None,
) -> EventWriteOut:
    """Übernimmt den erkannten Termin in den Kalender – mit der Mail als Beschreibung."""
    message = await _own_message(db, user, mail_id)
    suggestion = suggestion_out(message, user.timezone)
    if suggestion is None or message.suggestion_status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "Kein offener Terminvorschlag.")
    event_in = EventIn(
        title=(suggestion.title or message.subject or "–")[:300],
        description=_task_notes(message, _language(request)),
        location=suggestion.location[:500],
        area_id=body.area_id if body else None,
        all_day=suggestion.all_day,
        start_date=suggestion.start_date,
        start_time=suggestion.start_time,
        end_date=suggestion.end_date,
        end_time=suggestion.end_time,
        tzid=user.timezone,
    )
    event, conflicts = await create_event_row(db, user, event_in, source="mail")
    message.suggestion_status = "accepted"
    message.event_id = event.id
    await db.commit()
    return EventWriteOut(
        event=event_out(event, user.timezone),
        conflicts=conflicts_out(conflicts, user.timezone),
    )


@router.post("/messages/{mail_id}/suggestion/dismiss", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_suggestion(mail_id: uuid.UUID, db: DB, user: CurrentUser) -> None:
    message = await _own_message(db, user, mail_id)
    if message.suggestion_status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "Kein offener Terminvorschlag.")
    message.suggestion_status = "dismissed"
    await db.commit()


def _task_notes(message: MailMessage, language: str) -> str:
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


@router.post(
    "/messages/{mail_id}/task", response_model=TaskOut, status_code=status.HTTP_201_CREATED
)
async def task_from_message(
    mail_id: uuid.UUID,
    request: Request,
    db: DB,
    user: CurrentUser,
    body: MailTaskIn | None = None,
) -> TaskOut:
    """Legt eine Aufgabe mit Betreff und zitierter Mail an – ein zweiter Klick liefert dieselbe."""
    message = await _own_message(db, user, mail_id)
    if message.task_id is not None:
        existing = await db.get(Task, message.task_id)
        if existing is not None:
            authorize(user, Action.VIEW, existing)
            return task_out(existing)
    language = _language(request)
    area = await area_for_new_item(db, user, body.area_id if body else None)
    fallback = "Email without subject" if language == "en" else "E-Mail ohne Betreff"
    task = Task(
        area_id=area.id,
        area=area,
        created_by=user.id,
        title=(message.subject or fallback)[:300],
        notes=_task_notes(message, language),
        tags=[],
        source="mail",
        checklist=[],
    )
    db.add(task)
    await db.flush()
    message.task_id = task.id
    await db.commit()
    return task_out(task)
