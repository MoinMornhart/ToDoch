"""Passkeys (WebAuthn): hinzufügen, verwalten und damit ohne Passwort anmelden.

Challenges liegen fünf Minuten in Redis und werden beim Prüfen gelöscht (kein Replay).
Anmeldung ohne Benutzernamen über „discoverable credentials“; RP-ID und Origin kommen aus
TODOCH_ORIGIN – deshalb brauchen Passkeys einen festen Hostnamen mit HTTPS.
"""

from __future__ import annotations

import json
import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import func, select
from webauthn import (
    base64url_to_bytes,
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import bytes_to_base64url, exceptions, parse_authentication_credential_json
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    AuthenticatorTransport,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.api.deps import DB, CurrentSession, CurrentUser, Res, client_ip
from app.models import Passkey, User
from app.resources import Resources
from app.schemas.auth import UserOut
from app.schemas.passkeys import (
    LoginOptionsOut,
    LoginVerifyIn,
    PasskeyOut,
    PasskeyPatch,
    RegisterOptionsIn,
    RegisterVerifyIn,
)
from app.security.middleware import SESSION_COOKIE
from app.security.passwords import verify_password_async
from app.security.sessions import (
    create_session,
    resolve_session,
    revoke_session,
    set_session_cookies,
)
from app.services import audit

router = APIRouter(prefix="/api/auth/passkeys", tags=["passkeys"])

RP_NAME = "ToDoch"
CHALLENGE_TTL = 300
MAX_PASSKEYS = 20
LOGIN_FAILED = "Anmeldung mit Passkey fehlgeschlagen."
TRANSPORTS = {t.value for t in AuthenticatorTransport}
# Alles, was py_webauthn bei ungültigen Antworten wirft, plus Fehler beim Zerlegen
WEBAUTHN_ERRORS: tuple[type[Exception], ...] = (
    ValueError,
    TypeError,
    KeyError,
    *(
        obj
        for obj in vars(exceptions).values()
        if isinstance(obj, type) and issubclass(obj, Exception)
    ),
)


def passkey_out(passkey: Passkey) -> PasskeyOut:
    return PasskeyOut(
        id=passkey.id,
        name=passkey.name,
        created_at=passkey.created_at,
        last_used_at=passkey.last_used_at,
        backed_up=passkey.backed_up,
        device_type=passkey.device_type,
    )


# --- Challenges ----------------------------------------------------------------------------


def _key(kind: str, ref: str) -> str:
    return f"webauthn:{kind}:{ref}"


async def _store_challenge(res: Resources, kind: str, ref: str, challenge: bytes) -> None:
    await res.redis.set(_key(kind, ref), bytes_to_base64url(challenge), ex=CHALLENGE_TTL)


async def _take_challenge(res: Resources, kind: str, ref: str) -> bytes | None:
    """Einmalig: die Challenge wird beim Lesen gelöscht."""
    value = await res.redis.getdel(_key(kind, ref))
    if value is None:
        return None
    return base64url_to_bytes(value.decode() if isinstance(value, bytes) else str(value))


def _options(options: Any) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(options_to_json(options))
    return data


# --- Verwaltung ----------------------------------------------------------------------------


async def _own(db: DB, user: User, passkey_id: uuid.UUID) -> Passkey:
    passkey = await db.scalar(
        select(Passkey).where(Passkey.id == passkey_id, Passkey.user_id == user.id)
    )
    if passkey is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nicht gefunden.")
    return passkey


@router.get("", response_model=list[PasskeyOut])
async def list_passkeys(db: DB, user: CurrentUser) -> list[PasskeyOut]:
    rows = await db.scalars(
        select(Passkey).where(Passkey.user_id == user.id).order_by(Passkey.created_at)
    )
    return [passkey_out(p) for p in rows]


@router.post("/register/options")
async def register_options(
    body: RegisterOptionsIn, request: Request, db: DB, res: Res, session: CurrentSession
) -> dict[str, Any]:
    user = session.user
    ip = client_ip(request)
    await res.limiter.enforce("passkey-register", str(user.id), limit=10, window=600)
    valid, _ = await verify_password_async(user.password_hash, body.password)
    if not valid:
        audit.record(db, "passkey.register_denied", user_id=user.id, ip=ip)
        await db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Das Passwort ist falsch.")
    existing = list(await db.scalars(select(Passkey).where(Passkey.user_id == user.id)))
    if len(existing) >= MAX_PASSKEYS:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Höchstens {MAX_PASSKEYS} Passkeys möglich.")

    options = generate_registration_options(
        rp_id=res.settings.rp_id,
        rp_name=RP_NAME,
        user_name=user.email,
        user_id=user.id.bytes,
        user_display_name=user.display_name,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            # Gerätesperre (Fingerabdruck, Gesicht, PIN) Pflicht – ein Passkey ersetzt den
            # zweiten Faktor, ein gestohlener Stick ohne PIN darf das nicht
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        # Geräte, die schon einen Passkey haben, lehnen einen zweiten ab
        exclude_credentials=[
            PublicKeyCredentialDescriptor(
                id=p.credential_id,
                transports=[AuthenticatorTransport(t) for t in p.transports if t in TRANSPORTS],
            )
            for p in existing
        ],
    )
    await _store_challenge(res, "register", str(session.id), options.challenge)
    return _options(options)


@router.post("/register/verify", response_model=PasskeyOut, status_code=status.HTTP_201_CREATED)
async def register_verify(
    body: RegisterVerifyIn, request: Request, db: DB, res: Res, session: CurrentSession
) -> PasskeyOut:
    user = session.user
    challenge = await _take_challenge(res, "register", str(session.id))
    if challenge is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Die Anfrage ist abgelaufen. Bitte erneut versuchen."
        )
    try:
        verified = verify_registration_response(
            credential=body.credential,
            expected_challenge=challenge,
            expected_rp_id=res.settings.rp_id,
            expected_origin=res.settings.origin,
            require_user_verification=True,
        )
    except WEBAUTHN_ERRORS as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Der Passkey konnte nicht geprüft werden."
        ) from exc

    taken = await db.scalar(
        select(func.count())
        .select_from(Passkey)
        .where(Passkey.credential_id == verified.credential_id)
    )
    if taken:
        raise HTTPException(status.HTTP_409_CONFLICT, "Dieser Passkey ist schon eingetragen.")
    response = body.credential.get("response")
    raw_transports = response.get("transports", []) if isinstance(response, dict) else []
    transports = [t for t in raw_transports if isinstance(t, str) and t in TRANSPORTS]
    passkey = Passkey(
        user_id=user.id,
        credential_id=verified.credential_id,
        public_key=verified.credential_public_key,
        sign_count=verified.sign_count,
        transports=transports,
        aaguid=verified.aaguid,
        name=body.name,
        backed_up=verified.credential_backed_up,
        device_type=verified.credential_device_type.value,
    )
    db.add(passkey)
    await db.flush()
    audit.record(
        db, "passkey.added", user_id=user.id, ip=client_ip(request), passkey=str(passkey.id)
    )
    await db.commit()
    return passkey_out(passkey)


@router.patch("/{passkey_id}", response_model=PasskeyOut)
async def rename_passkey(
    passkey_id: uuid.UUID, body: PasskeyPatch, db: DB, user: CurrentUser
) -> PasskeyOut:
    passkey = await _own(db, user, passkey_id)
    if body.name is not None:
        passkey.name = body.name
    await db.commit()
    return passkey_out(passkey)


@router.delete("/{passkey_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_passkey(
    passkey_id: uuid.UUID, request: Request, db: DB, user: CurrentUser
) -> None:
    passkey = await _own(db, user, passkey_id)
    await db.delete(passkey)
    audit.record(
        db, "passkey.removed", user_id=user.id, ip=client_ip(request), passkey=str(passkey_id)
    )
    await db.commit()


# --- Anmeldung -----------------------------------------------------------------------------


@router.post("/login/options", response_model=LoginOptionsOut)
async def login_options(request: Request, res: Res) -> LoginOptionsOut:
    await res.limiter.enforce(
        "passkey-options", client_ip(request) or "unknown", limit=60, window=600
    )
    options = generate_authentication_options(
        rp_id=res.settings.rp_id, user_verification=UserVerificationRequirement.REQUIRED
    )
    challenge_id = secrets.token_urlsafe(24)
    await _store_challenge(res, "login", challenge_id, options.challenge)
    return LoginOptionsOut(challenge_id=challenge_id, options=_options(options))


@router.post("/login/verify", response_model=UserOut)
async def login_verify(
    body: LoginVerifyIn, request: Request, response: Response, db: DB, res: Res
) -> User:
    ip = client_ip(request)
    await res.limiter.enforce("passkey-login", ip or "unknown", limit=30, window=600)
    challenge = await _take_challenge(res, "login", body.challenge_id)

    passkey: Passkey | None = None
    user: User | None = None

    async def fail() -> HTTPException:
        audit.record(
            db, "login.failure", user_id=user.id if user else None, ip=ip, method="passkey"
        )
        await db.commit()
        return HTTPException(status.HTTP_401_UNAUTHORIZED, LOGIN_FAILED)

    try:
        credential = parse_authentication_credential_json(body.credential)
    except WEBAUTHN_ERRORS as exc:
        raise await fail() from exc
    passkey = await db.scalar(select(Passkey).where(Passkey.credential_id == credential.raw_id))
    user = await db.get(User, passkey.user_id) if passkey else None
    if challenge is None or passkey is None or user is None or not user.is_active:
        raise await fail()
    handle = credential.response.user_handle
    if handle is not None and handle != user.id.bytes:
        raise await fail()
    try:
        verified = verify_authentication_response(
            credential=credential,
            expected_challenge=challenge,
            expected_rp_id=res.settings.rp_id,
            expected_origin=res.settings.origin,
            credential_public_key=passkey.public_key,
            # Zähler darf nicht zurückspringen – sonst Verdacht auf geklonten Schlüssel
            credential_current_sign_count=passkey.sign_count,
            require_user_verification=True,
        )
    except WEBAUTHN_ERRORS as exc:
        raise await fail() from exc

    passkey.sign_count = verified.new_sign_count
    passkey.backed_up = verified.credential_backed_up
    passkey.last_used_at = datetime.now(UTC)
    previous = await resolve_session(db, request.cookies.get(SESSION_COOKIE), res.settings)
    if previous is not None:
        await revoke_session(db, previous)
    _, token = await create_session(
        db, user, res.settings, method="passkey", ip=ip,
        user_agent=request.headers.get("user-agent"),
    )  # fmt: skip
    audit.record(db, "login.success", user_id=user.id, ip=ip, method="passkey")
    await db.commit()
    set_session_cookies(response, token, res.settings)
    return user
