"""Web-Push: Geräte für Erinnerungen registrieren, entfernen, testen."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import delete, func, select

from app.api.deps import DB, CurrentUser, Res, client_ip
from app.models import PushSubscription, User
from app.schemas.push import (
    PushKeyOut,
    PushTestOut,
    SubscriptionIn,
    SubscriptionOut,
    UnsubscribeIn,
)
from app.services import audit
from app.services.push import encrypt_auth, push_to_user, vapid_keys
from app.services.reminders import texts

router = APIRouter(prefix="/api/push", tags=["push"])

MAX_SUBSCRIPTIONS = 10


def subscription_out(subscription: PushSubscription) -> SubscriptionOut:
    return SubscriptionOut(
        id=subscription.id,
        user_agent=subscription.user_agent,
        created_at=subscription.created_at,
        last_success_at=subscription.last_success_at,
    )


@router.get("/key", response_model=PushKeyOut)
async def public_key(db: DB, res: Res, user: CurrentUser) -> PushKeyOut:
    key, _ = await vapid_keys(db, res.crypto)
    return PushKeyOut(public_key=key)


@router.get("/subscriptions", response_model=list[SubscriptionOut])
async def list_subscriptions(db: DB, user: CurrentUser) -> list[SubscriptionOut]:
    found = await db.scalars(
        select(PushSubscription)
        .where(PushSubscription.user_id == user.id)
        .order_by(PushSubscription.created_at)
    )
    return [subscription_out(s) for s in found]


@router.post("/subscriptions", response_model=SubscriptionOut, status_code=status.HTTP_201_CREATED)
async def subscribe(
    body: SubscriptionIn, request: Request, db: DB, res: Res, user: CurrentUser
) -> SubscriptionOut:
    existing = await db.scalar(
        select(PushSubscription).where(PushSubscription.endpoint == body.endpoint)
    )
    if existing is not None and existing.user_id != user.id:
        # Der Browser gehört jetzt einem anderen Konto – altes Abo entfernen.
        await db.delete(existing)
        await db.flush()
        existing = None
    if existing is None:
        count = await db.scalar(
            select(func.count())
            .select_from(PushSubscription)
            .where(PushSubscription.user_id == user.id)
        )
        if (count or 0) >= MAX_SUBSCRIPTIONS:
            raise HTTPException(status.HTTP_409_CONFLICT, "Zu viele Geräte registriert.")
        subscription_id = uuid.uuid4()
        existing = PushSubscription(
            id=subscription_id,
            user_id=user.id,
            endpoint=body.endpoint,
            p256dh=body.keys.p256dh,
            auth_enc=encrypt_auth(res.crypto, subscription_id, body.keys.auth),
            user_agent=(request.headers.get("user-agent") or "")[:300] or None,
            failures=0,
        )
        db.add(existing)
        audit.record(db, "push.subscribed", user_id=user.id, ip=client_ip(request))
    else:
        existing.p256dh = body.keys.p256dh
        existing.auth_enc = encrypt_auth(res.crypto, existing.id, body.keys.auth)
        existing.failures = 0
    await db.commit()
    return subscription_out(existing)


@router.post("/unsubscribe", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(body: UnsubscribeIn, db: DB, user: CurrentUser) -> None:
    await db.execute(
        delete(PushSubscription).where(
            PushSubscription.endpoint == body.endpoint, PushSubscription.user_id == user.id
        )
    )
    await db.commit()


@router.delete("/subscriptions/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_subscription(subscription_id: uuid.UUID, db: DB, user: CurrentUser) -> None:
    found = await db.scalar(
        select(PushSubscription).where(
            PushSubscription.id == subscription_id, PushSubscription.user_id == user.id
        )
    )
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nicht gefunden.")
    await db.delete(found)
    await db.commit()


@router.post("/test", response_model=PushTestOut)
async def send_test(db: DB, res: Res, user: CurrentUser) -> PushTestOut:
    await res.limiter.enforce("push-test", str(user.id), limit=5, window=600)
    has_devices = await db.scalar(
        select(func.count())
        .select_from(PushSubscription)
        .where(PushSubscription.user_id == user.id)
    )
    if not has_devices:
        raise HTTPException(status.HTTP_409_CONFLICT, "Auf keinem Gerät aktiviert.")
    delivered = await push_to_user(
        db, res.crypto, user.id, _test_payload(user), subject=res.settings.origin
    )
    return PushTestOut(delivered=delivered)


def _test_payload(user: User) -> dict[str, str]:
    words = texts(user)
    return {"title": words["test_title"], "body": words["test"], "url": "/settings", "tag": "test"}
