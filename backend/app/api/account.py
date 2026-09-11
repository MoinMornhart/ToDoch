"""Dein Konto: alle Daten exportieren (DSGVO Art. 15/20) und das Konto endgültig löschen (Art. 17).

Export: eine JSON-Datei mit allem, was dir gehört – ohne Passwort-Hashes, Tokens, Geheimnisse und
verschlüsselte Zugangsdaten. Löschen: mit Passwort (und Code, falls Zwei-Faktor eingerichtet ist);
alles Eigene verschwindet per Datenbank-Kaskade, in geteilten Bereichen bleiben Aufgaben und
Kommentare für die anderen erhalten – nur ohne Namen. Das Audit-Log behält die pseudonyme ID.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from app.api.deps import DB, CurrentUser, Res, client_ip
from app.api.totp import check_second_factor
from app.models import (
    Area,
    AreaMember,
    AuditEvent,
    CalendarConnection,
    Contact,
    Event,
    ExternalCalendar,
    FeedToken,
    MailAccount,
    MailMessage,
    MailRule,
    Passkey,
    Task,
    TaskComment,
    User,
    UserSession,
)
from app.models.base import Base
from app.schemas.account import AccountDeleteIn
from app.security.passwords import verify_password_async
from app.security.sessions import clear_session_cookies
from app.services import audit

router = APIRouter(prefix="/api/account", tags=["account"])

# Nie im Export: Geheimnisse, Hashes, verschlüsselte Zugangsdaten, interne Suchspalten
SECRET_MARKERS = ("password", "secret", "token", "hash", "encrypted", "search_vector")


def _row(obj: Base) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for column in obj.__table__.columns:
        name = column.key
        if any(marker in name for marker in SECRET_MARKERS):
            continue
        value = getattr(obj, name)
        if isinstance(value, bytes):
            continue
        values[name] = value
    return values


async def _rows(db: DB, query: Any) -> list[dict[str, Any]]:
    return [_row(obj) for obj in (await db.scalars(query)).unique()]


@router.get("/export")
async def export_data(db: DB, res: Res, user: CurrentUser) -> JSONResponse:
    await res.limiter.enforce("account-export", str(user.id), limit=10, window=3600)
    owned = select(Area.id).where(Area.owner_id == user.id)
    accounts = select(MailAccount.id).where(MailAccount.owner_id == user.id)
    data = {
        "format": "todoch-export/1",
        "exported_at": datetime.now(UTC),
        "user": _row(user),
        "areas": await _rows(db, select(Area).where(Area.owner_id == user.id)),
        "memberships": await _rows(db, select(AreaMember).where(AreaMember.user_id == user.id)),
        "tasks": await _rows(db, select(Task).where(Task.area_id.in_(owned))),
        "events": await _rows(db, select(Event).where(Event.area_id.in_(owned))),
        "comments": await _rows(db, select(TaskComment).where(TaskComment.author_id == user.id)),
        "contacts": await _rows(db, select(Contact).where(Contact.owner_id == user.id)),
        "calendar_feeds": await _rows(db, select(FeedToken).where(FeedToken.user_id == user.id)),
        "subscribed_calendars": await _rows(
            db, select(ExternalCalendar).where(ExternalCalendar.owner_id == user.id)
        ),
        "calendar_connections": await _rows(
            db, select(CalendarConnection).where(CalendarConnection.owner_id == user.id)
        ),
        "mail_accounts": await _rows(
            db, select(MailAccount).where(MailAccount.owner_id == user.id)
        ),
        "mail_rules": await _rows(db, select(MailRule).where(MailRule.owner_id == user.id)),
        "mails": await _rows(db, select(MailMessage).where(MailMessage.account_id.in_(accounts))),
        "passkeys": await _rows(db, select(Passkey).where(Passkey.user_id == user.id)),
        "sessions": await _rows(db, select(UserSession).where(UserSession.user_id == user.id)),
        "audit_log": await _rows(db, select(AuditEvent).where(AuditEvent.user_id == user.id)),
    }
    name = f"todoch-export-{datetime.now(UTC):%Y-%m-%d}.json"
    return JSONResponse(
        jsonable_encoder(data),
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.post("/delete", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    body: AccountDeleteIn,
    request: Request,
    response: Response,
    db: DB,
    res: Res,
    user: CurrentUser,
) -> None:
    """Endgültig – vorher Passwort (und Code, falls Zwei-Faktor eingerichtet ist)."""
    ip = client_ip(request)
    await res.limiter.enforce("account-delete", str(user.id), limit=5, window=600)
    valid, _ = await verify_password_async(user.password_hash, body.password)
    if not valid:
        audit.record(db, "account.delete_failed", user_id=user.id, ip=ip)
        await db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Das Passwort ist falsch.")
    if user.totp_enabled and (
        not body.code or await check_second_factor(db, res, user, body.code) is None
    ):
        audit.record(db, "account.delete_failed", user_id=user.id, ip=ip, reason="code")
        await db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Der Code ist falsch.")
    if user.is_admin:
        other_admins = await db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.is_admin.is_(True), User.is_active.is_(True), User.id != user.id)
        )
        if not other_admins:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Das letzte Admin-Konto kann nicht gelöscht werden."
            )
    audit.record(db, "account.deleted", user_id=user.id, ip=ip)
    await db.delete(user)
    await db.commit()
    clear_session_cookies(response)
