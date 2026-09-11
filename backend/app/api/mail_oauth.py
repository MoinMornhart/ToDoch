"""„Mit Google verbinden“ / „Mit Microsoft verbinden“: Postfach per OAuth einbinden.

Der Rücksprung vom Anbieter landet hier (GET, oberste Ebene – das Sitzungscookie mit
``SameSite=Lax`` wird mitgeschickt) und leitet anschließend zurück nach ``/mail``.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select

from app.api import calendar_sync as calendar_api
from app.api.deps import DB, CurrentUser, Res, client_ip
from app.api.mail import MAX_ACCOUNTS
from app.models import MailAccount, User
from app.schemas.mail import OAuthProvidersOut, OAuthStartOut
from app.services import audit, mail
from app.services import calendar_sync as calendar_sync_service
from app.services import mail_oauth as oauth

router = APIRouter(prefix="/api/mail/oauth", tags=["mail"])

ProviderName = Literal["google", "microsoft"]
STATE_PREFIX = "mailoauth:"


def _back(**params: str) -> RedirectResponse:
    return RedirectResponse(f"/mail?{urlencode(params)}", status_code=status.HTTP_303_SEE_OTHER)


def _back_areas(**params: str) -> RedirectResponse:
    """Kalender-Verbindung: zurück zu „Bereiche“ (?calendar_connected / ?calendar_error)."""
    renamed = {
        ("calendar_connected" if key == "connected" else "calendar_error"): value
        for key, value in params.items()
    }
    return RedirectResponse(f"/areas?{urlencode(renamed)}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/providers", response_model=OAuthProvidersOut)
async def providers(res: Res, user: CurrentUser) -> OAuthProvidersOut:
    return OAuthProvidersOut(**oauth.configured(res.settings))


@router.post("/{provider}/start", response_model=OAuthStartOut)
async def start(provider: ProviderName, res: Res, user: CurrentUser) -> OAuthStartOut:
    config = oauth.provider(res.settings, provider)
    if config is None:
        raise HTTPException(status.HTTP_409_CONFLICT, oauth.NOT_CONFIGURED)
    await res.limiter.enforce("mail-oauth", str(user.id), limit=20, window=600)
    state = oauth.new_state()
    verifier, challenge = oauth.new_pkce()
    record = {"user": str(user.id), "provider": provider, "verifier": verifier}
    await res.redis.set(STATE_PREFIX + state, json.dumps(record), ex=oauth.STATE_TTL)
    url = oauth.authorization_url(
        config, oauth.redirect_uri(res.settings, provider), state, challenge
    )
    return OAuthStartOut(url=url)


async def _save(
    db: DB,
    res: Res,
    user: User,
    config: oauth.Provider,
    email: str,
    refresh_token: str,
    result: mail.FetchResult,
    request: Request,
) -> str | None:
    """Neues Postfach anlegen oder ein vorhandenes neu verbinden; liefert einen Fehlercode."""
    existing = await db.scalar(
        select(MailAccount).where(
            MailAccount.owner_id == user.id,
            MailAccount.auth == "oauth2",
            MailAccount.oauth_provider == config.name,
            MailAccount.email == email,
        )
    )
    ip = client_ip(request)
    if existing is not None:
        existing.password_encrypted = res.crypto.encrypt(
            refresh_token, context=mail.password_context(existing.id)
        )
        existing.enabled = True
        existing.last_error = None
        audit.record(db, "mail.oauth_reconnected", user_id=user.id, ip=ip, account=str(existing.id))
        await db.commit()
        return None
    count = await db.scalar(
        select(func.count()).select_from(MailAccount).where(MailAccount.owner_id == user.id)
    )
    if (count or 0) >= MAX_ACCOUNTS:
        return "limit"
    now = datetime.now(UTC)
    account_id = uuid.uuid4()
    account = MailAccount(
        id=account_id,
        owner_id=user.id,
        name=email,
        email=email,
        imap_host=config.imap_host,
        imap_port=993,
        security="ssl",
        username=email,
        password_encrypted=res.crypto.encrypt(
            refresh_token, context=mail.password_context(account_id)
        ),
        folder="INBOX",
        refresh_minutes=15,
        enabled=True,
        last_uid=0,
        message_count=0,
        last_synced_at=now,
        last_success_at=now,
        auth="oauth2",
        oauth_provider=config.name,
    )
    db.add(account)
    await db.flush()
    await mail.apply_result(db, account, result, tzid=user.timezone)
    audit.record(
        db,
        "mail.account_added",
        user_id=user.id,
        ip=ip,
        account=str(account_id),
        host=config.imap_host,
        provider=config.name,
    )
    await db.commit()
    return None


@router.get("/{provider}/callback", include_in_schema=False)
async def callback(
    provider: ProviderName,
    request: Request,
    db: DB,
    res: Res,
    user: CurrentUser,
    code: Annotated[str | None, Query(max_length=4000)] = None,
    state: Annotated[str | None, Query(max_length=200)] = None,
    error: Annotated[str | None, Query(max_length=200)] = None,
) -> RedirectResponse:
    if not state:
        return _back(oauth_error="failed")
    raw = await res.redis.getdel(STATE_PREFIX + state)
    if raw is None:
        return _back(oauth_error="expired")
    record = json.loads(raw)
    # Derselbe Rücksprung dient auch „Google Kalender verbinden“ (api/calendar_sync.py)
    for_calendar = record.get("purpose") == "calendar"
    back = _back_areas if for_calendar else _back
    if record.get("user") != str(user.id) or record.get("provider") != provider:
        return back(oauth_error="failed")
    if error or not code:
        return back(oauth_error="denied")
    config = (
        calendar_sync_service.calendar_provider(res.settings, provider)
        if for_calendar
        else oauth.provider(res.settings, provider)
    )
    if config is None:
        return back(oauth_error="failed")
    try:
        tokens = await oauth.exchange_code(
            config, code, record["verifier"], oauth.redirect_uri(res.settings, provider)
        )
    except oauth.OAuthError:
        return back(oauth_error="failed")
    if for_calendar:
        failure = await calendar_api.finish(db, res, user, provider, record, tokens, request)
        return back(oauth_error=failure) if failure else back(connected=provider)
    if not tokens.email:
        return _back(oauth_error="noemail")
    if not tokens.refresh_token:
        return _back(oauth_error="failed")
    target = mail.ImapTarget(
        host=config.imap_host,
        port=993,
        security="ssl",
        username=tokens.email,
        password="",
        access_token=tokens.access_token,
    )
    try:
        result = await mail.fetch_mailbox(
            target, allow_private=False, uidvalidity=None, last_uid=0, limit=mail.FIRST_BATCH
        )
    except mail.MailError:
        return _back(oauth_error="imap")
    failure = await _save(
        db, res, user, config, tokens.email, tokens.refresh_token, result, request
    )
    if failure:
        return _back(oauth_error=failure)
    return _back(connected=provider)
