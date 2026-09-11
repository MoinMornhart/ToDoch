import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient

from app.resources import Resources
from app.services import push as push_service
from app.services.push import endpoint_allowed
from app.services.reminders import send_due_reminders

ENDPOINT = "https://fcm.googleapis.com/fcm/send/abc123"
KEYS = {"p256dh": "B" + "A" * 86, "auth": "c2VjcmV0LWF1dGgtMTIzNA"}


class FakeSender:
    def __init__(self, status: int = 201) -> None:
        self.status = status
        self.calls: list[tuple[dict[str, Any], dict[str, Any], str]] = []

    def __call__(self, info: dict[str, Any], payload: str, pem: bytes, subject: str) -> int:
        assert pem.startswith(b"-----BEGIN PRIVATE KEY-----")
        self.calls.append((info, json.loads(payload), subject))
        return self.status


@pytest.mark.parametrize(
    ("url", "ok"),
    [
        ("https://fcm.googleapis.com/fcm/send/x", True),
        ("https://updates.push.services.mozilla.com/wpush/v2/x", True),
        ("https://web.push.apple.com/abc", True),
        ("https://db5p.notify.windows.com/w/?token=x", True),
        ("http://fcm.googleapis.com/x", False),
        ("https://evil.example/x", False),
        ("https://127.0.0.1/x", False),
        ("https://fcm.googleapis.com.evil.example/x", False),
        ("https://fcm.googleapis.com:8443/x", False),
        ("javascript:alert(1)", False),
    ],
)
def test_endpoint_allowlist(url: str, ok: bool) -> None:
    assert endpoint_allowed(url) is ok


async def test_vapid_key_is_generated_once(alice: AsyncClient) -> None:
    first = (await alice.get("/api/push/key")).json()["public_key"]
    second = (await alice.get("/api/push/key")).json()["public_key"]
    assert first == second
    assert len(first) == 87  # 65 Byte, Base64url


async def test_subscribe_and_unsubscribe(alice: AsyncClient) -> None:
    bad = await alice.post(
        "/api/push/subscriptions", json={"endpoint": "https://evil.example/x", "keys": KEYS}
    )
    assert bad.status_code == 422
    for _ in range(2):  # gleicher Endpunkt → kein zweites Gerät
        r = await alice.post("/api/push/subscriptions", json={"endpoint": ENDPOINT, "keys": KEYS})
        assert r.status_code == 201, r.text
    listed = (await alice.get("/api/push/subscriptions")).json()
    assert len(listed) == 1
    assert "auth" not in json.dumps(listed)
    r = await alice.post("/api/push/unsubscribe", json={"endpoint": ENDPOINT})
    assert r.status_code == 204
    assert (await alice.get("/api/push/subscriptions")).json() == []


async def _setup_reminder(alice: AsyncClient) -> None:
    await alice.patch("/api/auth/me", json={"timezone": "UTC"})
    await alice.post(
        "/api/events",
        json={
            "title": "Zahnarzt",
            "start_date": "2026-09-14",
            "start_time": "09:00",
            "end_time": "10:00",
            "location": "Praxis",
            "reminders": [15, 60],
        },
    )
    await alice.post("/api/push/subscriptions", json={"endpoint": ENDPOINT, "keys": KEYS})


async def test_reminder_is_sent_exactly_once(alice: AsyncClient, resources: Resources) -> None:
    await _setup_reminder(alice)
    sender = FakeSender()
    now = datetime(2026, 9, 14, 8, 46, tzinfo=UTC)  # 14 Min. vor Beginn → 15-Min.-Erinnerung fällig
    async with resources.sessionmaker() as db:
        sent = await send_due_reminders(
            db, resources.crypto, subject="https://testserver", now=now, sender=sender
        )
        again = await send_due_reminders(
            db, resources.crypto, subject="https://testserver", now=now, sender=sender
        )
    assert (sent, again) == (1, 0)
    info, payload, subject = sender.calls[0]
    assert info["endpoint"] == ENDPOINT
    assert info["keys"]["auth"] == KEYS["auth"]  # verschlüsselt gespeichert, korrekt entschlüsselt
    assert payload["title"] == "Zahnarzt"
    assert payload["body"] == "09:00–10:00 · Praxis"
    assert payload["url"] == "/calendar?view=day&date=2026-09-14"
    assert subject == "https://testserver"


async def test_nothing_due_outside_window(alice: AsyncClient, resources: Resources) -> None:
    await _setup_reminder(alice)
    sender = FakeSender()
    for now in (datetime(2026, 9, 14, 8, 30, tzinfo=UTC), datetime(2026, 9, 14, 9, 30, tzinfo=UTC)):
        async with resources.sessionmaker() as db:
            await send_due_reminders(
                db, resources.crypto, subject="https://t", now=now, sender=sender
            )
    assert sender.calls == []


async def test_gone_subscription_is_removed(alice: AsyncClient, resources: Resources) -> None:
    await _setup_reminder(alice)
    async with resources.sessionmaker() as db:
        await send_due_reminders(
            db,
            resources.crypto,
            subject="https://t",
            now=datetime(2026, 9, 14, 8, 50, tzinfo=UTC),
            sender=FakeSender(status=410),
        )
    assert (await alice.get("/api/push/subscriptions")).json() == []


async def test_series_reminder_uses_occurrence(alice: AsyncClient, resources: Resources) -> None:
    await alice.patch("/api/auth/me", json={"timezone": "UTC"})
    await alice.post(
        "/api/events",
        json={
            "title": "Sport",
            "start_date": "2026-09-01",
            "start_time": "18:00",
            "rrule": "FREQ=WEEKLY",
            "reminders": [30],
        },
    )
    await alice.post("/api/push/subscriptions", json={"endpoint": ENDPOINT, "keys": KEYS})
    sender = FakeSender()
    now = datetime(2026, 9, 15, 17, 30, tzinfo=UTC) + timedelta(minutes=1)
    async with resources.sessionmaker() as db:
        await send_due_reminders(db, resources.crypto, subject="https://t", now=now, sender=sender)
    assert [c[1]["url"] for c in sender.calls] == ["/calendar?view=day&date=2026-09-15"]


async def test_test_notification(alice: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    assert (await alice.post("/api/push/test")).status_code == 409
    await alice.post("/api/push/subscriptions", json={"endpoint": ENDPOINT, "keys": KEYS})
    sender = FakeSender()
    monkeypatch.setattr(push_service, "send_notification_sync", sender)
    r = await alice.post("/api/push/test")
    assert r.status_code == 200
    assert r.json() == {"delivered": 1}
    assert sender.calls[0][1]["body"] == "Benachrichtigungen funktionieren."


async def test_devices_are_private(alice: AsyncClient, bob: AsyncClient) -> None:
    created = await alice.post("/api/push/subscriptions", json={"endpoint": ENDPOINT, "keys": KEYS})
    assert (await bob.delete(f"/api/push/subscriptions/{created.json()['id']}")).status_code == 404
    assert (await bob.get("/api/push/subscriptions")).json() == []
    # Übernimmt ein anderes Konto denselben Browser, gehört das Abo danach Bob.
    await bob.post("/api/push/subscriptions", json={"endpoint": ENDPOINT, "keys": KEYS})
    assert (await alice.get("/api/push/subscriptions")).json() == []
