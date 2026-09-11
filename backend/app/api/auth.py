"""Anmeldung mit Passwort, Sitzungen, Profil."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select

from app.api.deps import DB, CurrentSession, CurrentUser, Res, client_ip
from app.models import User, UserSession
from app.schemas.auth import (
    LoginIn,
    MePatch,
    PasswordChangeIn,
    SessionOut,
    UserOut,
)
from app.security.middleware import SESSION_COOKIE
from app.security.passwords import (
    PasswordPolicyError,
    check_password_policy,
    dummy_verify_async,
    hash_password_async,
    verify_password_async,
)
from app.security.ratelimit import hashed, too_many
from app.security.sessions import (
    clear_session_cookies,
    create_session,
    is_session_valid,
    resolve_session,
    revoke_all_sessions,
    revoke_session,
    set_session_cookies,
)
from app.services import audit

router = APIRouter(prefix="/api/auth", tags=["auth"])

LOGIN_FAILED = "E-Mail-Adresse oder Passwort ist falsch."


@router.post("/login", response_model=UserOut)
async def login(body: LoginIn, request: Request, response: Response, db: DB, res: Res) -> User:
    ip = client_ip(request)
    await res.limiter.enforce("login-ip", ip or "unknown", limit=30, window=600)
    account = hashed(body.email)
    locked = await res.limiter.locked_for("login", account)
    if locked:
        raise too_many(locked)

    user = await db.scalar(select(User).where(User.email == body.email))
    needs_rehash = False
    if user is None or not user.is_active:
        await dummy_verify_async(body.password)
        valid = False
    else:
        valid, needs_rehash = await verify_password_async(user.password_hash, body.password)

    if not valid:
        await res.limiter.register_failure("login", account)
        audit.record(db, "login.failure", user_id=user.id if user else None, ip=ip)
        await db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, LOGIN_FAILED)

    assert user is not None
    await res.limiter.reset("login", account)
    if needs_rehash:
        user.password_hash = await hash_password_async(body.password)

    previous = await resolve_session(db, request.cookies.get(SESSION_COOKIE), res.settings)
    if previous is not None:
        await revoke_session(db, previous)
    _, token = await create_session(
        db, user, res.settings, method="password", ip=ip,
        user_agent=request.headers.get("user-agent"),
    )  # fmt: skip
    audit.record(db, "login.success", user_id=user.id, ip=ip, method="password")
    await db.commit()
    set_session_cookies(response, token, res.settings)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, db: DB, session: CurrentSession) -> None:
    await revoke_session(db, session)
    audit.record(db, "logout", user_id=session.user_id, ip=client_ip(request))
    await db.commit()
    clear_session_cookies(response)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(request: Request, response: Response, db: DB, user: CurrentUser) -> None:
    count = await revoke_all_sessions(db, user.id)
    audit.record(db, "logout.all", user_id=user.id, ip=client_ip(request), sessions=count)
    await db.commit()
    clear_session_cookies(response)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> User:
    return user


@router.patch("/me", response_model=UserOut)
async def update_me(body: MePatch, db: DB, user: CurrentUser) -> User:
    for field in body.model_fields_set:
        value = getattr(body, field)
        if value is not None:
            setattr(user, field, value)
    await db.commit()
    return user


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(db: DB, res: Res, current: CurrentSession) -> list[SessionOut]:
    rows = await db.scalars(
        select(UserSession)
        .where(
            UserSession.user_id == current.user_id,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > datetime.now(UTC),
        )
        .order_by(UserSession.last_seen_at.desc())
    )
    return [
        SessionOut(
            id=s.id,
            created_at=s.created_at,
            last_seen_at=s.last_seen_at,
            ip=s.ip,
            user_agent=s.user_agent,
            auth_method=s.auth_method,
            current=s.id == current.id,
        )
        for s in rows
        if is_session_valid(s, res.settings)
    ]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def end_session(
    session_id: uuid.UUID, request: Request, db: DB, current: CurrentSession
) -> None:
    target = await db.scalar(
        select(UserSession).where(
            UserSession.id == session_id, UserSession.user_id == current.user_id
        )
    )
    if target is None or target.revoked_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nicht gefunden.")
    await revoke_session(db, target)
    audit.record(db, "session.revoked", user_id=current.user_id, ip=client_ip(request))
    await db.commit()


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: PasswordChangeIn,
    request: Request,
    response: Response,
    db: DB,
    res: Res,
    session: CurrentSession,
) -> None:
    user = session.user
    ip = client_ip(request)
    await res.limiter.enforce("password-change", str(user.id), limit=10, window=600)
    valid, _ = await verify_password_async(user.password_hash, body.current_password)
    if not valid:
        audit.record(db, "password.change_failed", user_id=user.id, ip=ip)
        await db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Das aktuelle Passwort ist falsch.")
    try:
        check_password_policy(body.new_password, email=user.email, display_name=user.display_name)
    except PasswordPolicyError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, exc.message) from exc

    user.password_hash = await hash_password_async(body.new_password)
    user.password_changed_at = datetime.now(UTC)
    # Alle anderen Sitzungen beenden und die aktuelle Sitzung rotieren.
    await revoke_all_sessions(db, user.id)
    _, token = await create_session(
        db, user, res.settings, method=session.auth_method, ip=ip,
        user_agent=request.headers.get("user-agent"),
    )  # fmt: skip
    audit.record(db, "password.changed", user_id=user.id, ip=ip)
    await db.commit()
    set_session_cookies(response, token, res.settings)
