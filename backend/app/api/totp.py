"""Zwei-Faktor mit Authenticator-App: einrichten, abschalten, Wiederherstellungscodes."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DB, CurrentSession, CurrentUser, Res, client_ip
from app.models import RecoveryCode, User
from app.resources import Resources
from app.schemas.auth import (
    RecoveryCodesOut,
    TotpConfirmIn,
    TotpDisableIn,
    TotpSetupIn,
    TotpSetupOut,
    TotpStatusOut,
)
from app.security import totp
from app.security.passwords import verify_password_async
from app.services import audit

router = APIRouter(prefix="/api/auth/totp", tags=["totp"])

PENDING_TTL = 600
WRONG_CODE = "Der Code ist falsch."


def secret_context(user: User) -> str:
    return f"user:{user.id}:totp"


def _pending_key(session_id: object) -> str:
    return f"totp:pending:{session_id}"


async def check_second_factor(
    db: AsyncSession, res: Resources, user: User, code: str
) -> str | None:
    """Prüft einen TOTP- oder Wiederherstellungscode. Liefert die Art („totp“/„recovery“)
    oder None. Ein gültiger Code wird dabei verbraucht."""
    if user.totp_secret is None:
        return None
    if totp.looks_like_totp(code):
        secret = res.crypto.decrypt_str(user.totp_secret, context=secret_context(user))
        step = totp.verify(secret, code, user.totp_last_step)
        if step is None:
            return None
        user.totp_last_step = step
        return "totp"
    found = await db.scalar(
        select(RecoveryCode).where(
            RecoveryCode.user_id == user.id,
            RecoveryCode.code_hash == totp.hash_recovery(code),
            RecoveryCode.used_at.is_(None),
        )
    )
    if found is None:
        return None
    found.used_at = datetime.now(UTC)
    return "recovery"


async def _replace_recovery_codes(db: AsyncSession, user: User) -> list[str]:
    await db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))
    codes = totp.new_recovery_codes()
    for code in codes:
        db.add(RecoveryCode(user_id=user.id, code_hash=totp.hash_recovery(code)))
    return codes


async def _require_password(
    db: AsyncSession, request: Request, user: User, password: str, event: str
) -> None:
    valid, _ = await verify_password_async(user.password_hash, password)
    if not valid:
        audit.record(db, event, user_id=user.id, ip=client_ip(request))
        await db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Das Passwort ist falsch.")


@router.get("", response_model=TotpStatusOut)
async def totp_status(db: DB, user: CurrentUser) -> TotpStatusOut:
    left = await db.scalar(
        select(func.count())
        .select_from(RecoveryCode)
        .where(RecoveryCode.user_id == user.id, RecoveryCode.used_at.is_(None))
    )
    return TotpStatusOut(
        enabled=user.totp_enabled, enabled_at=user.totp_enabled_at, recovery_codes_left=left or 0
    )


@router.post("/setup", response_model=TotpSetupOut)
async def totp_setup(
    body: TotpSetupIn, request: Request, db: DB, res: Res, session: CurrentSession
) -> TotpSetupOut:
    user = session.user
    await res.limiter.enforce("totp-setup", str(user.id), limit=10, window=600)
    if user.totp_enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, "Zwei-Faktor ist bereits eingerichtet.")
    await _require_password(db, request, user, body.password, "totp.setup_denied")
    secret = totp.new_secret()
    await res.redis.set(
        _pending_key(session.id),
        res.crypto.encrypt(secret, context=f"totp_pending:{session.id}"),
        ex=PENDING_TTL,
    )
    uri = totp.provisioning_uri(secret, user.email)
    return TotpSetupOut(secret=secret, uri=uri, qr_svg=totp.qr_svg(uri))


@router.post("/confirm", response_model=RecoveryCodesOut)
async def totp_confirm(
    body: TotpConfirmIn, request: Request, db: DB, res: Res, session: CurrentSession
) -> RecoveryCodesOut:
    user = session.user
    await res.limiter.enforce("totp-confirm", str(user.id), limit=10, window=600)
    stored = await res.redis.get(_pending_key(session.id))
    if stored is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Die Einrichtung ist abgelaufen. Bitte neu beginnen."
        )
    token = stored.decode() if isinstance(stored, bytes) else str(stored)
    secret = res.crypto.decrypt_str(token, context=f"totp_pending:{session.id}")
    step = totp.verify(secret, body.code, None)
    if step is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, WRONG_CODE)
    await res.redis.delete(_pending_key(session.id))
    user.totp_secret = res.crypto.encrypt(secret, context=secret_context(user))
    user.totp_enabled_at = datetime.now(UTC)
    user.totp_last_step = step
    codes = await _replace_recovery_codes(db, user)
    audit.record(db, "totp.enabled", user_id=user.id, ip=client_ip(request))
    await db.commit()
    return RecoveryCodesOut(recovery_codes=codes)


@router.post("/disable", status_code=status.HTTP_204_NO_CONTENT)
async def totp_disable(
    body: TotpDisableIn, request: Request, db: DB, res: Res, user: CurrentUser
) -> None:
    await res.limiter.enforce("totp-disable", str(user.id), limit=10, window=600)
    if not user.totp_enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, "Zwei-Faktor ist nicht eingerichtet.")
    await _require_password(db, request, user, body.password, "totp.disable_denied")
    if await check_second_factor(db, res, user, body.code) is None:
        audit.record(db, "totp.disable_denied", user_id=user.id, ip=client_ip(request))
        await db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, WRONG_CODE)
    await disable_totp(db, user)
    audit.record(db, "totp.disabled", user_id=user.id, ip=client_ip(request))
    await db.commit()


async def disable_totp(db: AsyncSession, user: User) -> None:
    user.totp_secret = None
    user.totp_enabled_at = None
    user.totp_last_step = None
    await db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))


@router.post("/recovery-codes", response_model=RecoveryCodesOut)
async def new_recovery_codes(
    body: TotpSetupIn, request: Request, db: DB, res: Res, user: CurrentUser
) -> RecoveryCodesOut:
    await res.limiter.enforce("totp-recovery", str(user.id), limit=10, window=600)
    if not user.totp_enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, "Zwei-Faktor ist nicht eingerichtet.")
    await _require_password(db, request, user, body.password, "totp.recovery_denied")
    codes = await _replace_recovery_codes(db, user)
    audit.record(db, "totp.recovery_codes", user_id=user.id, ip=client_ip(request))
    await db.commit()
    return RecoveryCodesOut(recovery_codes=codes)
