"""ICS-Abos: geheime, widerrufbare Links auf die eigenen Termine (nur lesend)."""

from __future__ import annotations

import hashlib
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import func, or_, select

from app.api.deps import DB, CurrentUser, Res, client_ip
from app.models import Area, Event, FeedToken, User
from app.policy import Action, authorize, visible_areas
from app.schemas.feeds import FeedCreatedOut, FeedIn, FeedOut
from app.security.ratelimit import hashed
from app.services import audit
from app.services.ics import build_calendar

router = APIRouter(prefix="/api/feeds", tags=["feeds"])

MAX_FEEDS = 20
PAST_DAYS = 90
MAX_EVENTS = 5000
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{20,100}$")
TOUCH_INTERVAL = timedelta(minutes=5)


def _hash(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "Nicht gefunden.")


def feed_out(feed: FeedToken) -> FeedOut:
    return FeedOut(
        id=feed.id,
        name=feed.name,
        area_id=feed.area_id,
        area_name=feed.area.name if feed.area else None,
        detail=feed.detail,
        created_at=feed.created_at,
        last_used_at=feed.last_used_at,
    )


@router.get("", response_model=list[FeedOut])
async def list_feeds(db: DB, user: CurrentUser) -> list[FeedOut]:
    feeds = await db.scalars(
        select(FeedToken)
        .where(FeedToken.user_id == user.id, FeedToken.revoked_at.is_(None))
        .order_by(FeedToken.created_at)
    )
    return [feed_out(f) for f in feeds]


@router.post("", response_model=FeedCreatedOut, status_code=status.HTTP_201_CREATED)
async def create_feed(
    body: FeedIn, request: Request, db: DB, res: Res, user: CurrentUser
) -> FeedCreatedOut:
    active = await db.scalar(
        select(func.count())
        .select_from(FeedToken)
        .where(FeedToken.user_id == user.id, FeedToken.revoked_at.is_(None))
    )
    if (active or 0) >= MAX_FEEDS:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Höchstens {MAX_FEEDS} Abo-Links möglich.")
    area = None
    if body.area_id is not None:
        area = await db.get(Area, body.area_id)
        authorize(user, Action.VIEW, area)
    token = secrets.token_urlsafe(32)
    feed = FeedToken(
        user_id=user.id,
        area_id=area.id if area else None,
        area=area,
        name=body.name,
        token_hash=_hash(token),
        detail=body.detail,
    )
    db.add(feed)
    await db.flush()
    audit.record(
        db,
        "feed.created",
        user_id=user.id,
        ip=client_ip(request),
        feed=str(feed.id),
        detail=body.detail,
    )
    await db.commit()
    url = f"{res.settings.origin}/api/feeds/{token}.ics"
    return FeedCreatedOut(
        feed=feed_out(feed), url=url, webcal_url="webcal://" + url.split("://", 1)[1]
    )


@router.delete("/{feed_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_feed(feed_id: uuid.UUID, request: Request, db: DB, user: CurrentUser) -> None:
    feed = await db.scalar(
        select(FeedToken).where(
            FeedToken.id == feed_id, FeedToken.user_id == user.id, FeedToken.revoked_at.is_(None)
        )
    )
    if feed is None:
        raise _not_found()
    feed.revoked_at = datetime.now(UTC)
    audit.record(db, "feed.revoked", user_id=user.id, ip=client_ip(request), feed=str(feed.id))
    await db.commit()


async def _feed_events(db: DB, user: User, feed: FeedToken) -> list[Event]:
    since = datetime.now(UTC) - timedelta(days=PAST_DAYS)
    base = select(Event).join(Area, Event.area_id == Area.id).where(visible_areas(user))
    if feed.area_id is not None:
        base = base.where(Event.area_id == feed.area_id)
    main = list(
        await db.scalars(
            base.where(
                Event.series_id.is_(None), or_(Event.rrule.is_not(None), Event.end_at >= since)
            ).limit(MAX_EVENTS)
        )
    )
    series_ids = [e.id for e in main if e.rrule]
    overrides: list[Event] = []
    if series_ids:
        overrides = list(await db.scalars(base.where(Event.series_id.in_(series_ids))))
    return main + overrides


@router.get("/{token}.ics")
async def feed_calendar(token: str, request: Request, db: DB, res: Res) -> Response:
    await res.limiter.enforce("feed-ip", client_ip(request) or "unknown", limit=300, window=600)
    if not TOKEN_PATTERN.match(token):
        raise _not_found()
    await res.limiter.enforce("feed", hashed(token), limit=60, window=600)
    feed = await db.scalar(
        select(FeedToken).where(
            FeedToken.token_hash == _hash(token), FeedToken.revoked_at.is_(None)
        )
    )
    user = await db.get(User, feed.user_id) if feed else None
    if feed is None or user is None or not user.is_active:
        raise _not_found()

    events = await _feed_events(db, user, feed)
    name = f"Todoch – {feed.area.name}" if feed.area else "Todoch"
    body = build_calendar(events, name=name, detail=feed.detail)
    etag = '"' + hashlib.sha256(body).hexdigest()[:32] + '"'

    now = datetime.now(UTC)
    if feed.last_used_at is None or now - feed.last_used_at >= TOUCH_INTERVAL:
        feed.last_used_at = now
        await db.commit()

    headers = {"ETag": etag, "Cache-Control": "private, max-age=300"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    headers["Content-Disposition"] = 'inline; filename="todoch.ics"'
    return Response(body, media_type="text/calendar; charset=utf-8", headers=headers)
