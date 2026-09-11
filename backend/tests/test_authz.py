"""Autorisierung: Fremde Objekte sind nie sichtbar oder änderbar (IDOR-Tests)."""

import re
import uuid
from typing import Any

import pytest
from httpx import AsyncClient

from app.main import create_app
from app.models import CalendarConnection
from app.resources import Resources
from tests.conftest import ClientFactory, create_user, login, make_settings
from tests.webauthn_soft import SoftAuthenticator, register_passkey


async def _alice_objects(alice: AsyncClient) -> dict[str, Any]:
    areas = (await alice.get("/api/areas")).json()
    task = (
        await alice.post(
            "/api/tasks",
            json={"title": "Geheimprojekt", "notes": "vertraulich", "area_id": areas[0]["id"]},
        )
    ).json()
    session = (await alice.get("/api/auth/sessions")).json()[0]
    event = (
        await alice.post(
            "/api/events",
            json={
                "title": "Besprechung",
                "start_date": "2026-09-14",
                "start_time": "09:00",
                "rrule": "FREQ=WEEKLY",
                "area_id": areas[0]["id"],
            },
        )
    ).json()["event"]
    feed = (await alice.post("/api/feeds", json={"name": "Alice"})).json()["feed"]
    subscription = (
        await alice.post(
            "/api/push/subscriptions",
            json={
                "endpoint": "https://fcm.googleapis.com/fcm/send/alice",
                "keys": {"p256dh": "B" + "A" * 86, "auth": "c2VjcmV0LWF1dGgtMTIzNA"},
            },
        )
    ).json()
    contact = (await alice.post("/api/contacts", json={"name": "Vertraulich"})).json()
    passkey = await register_passkey(alice, SoftAuthenticator())
    calendar = (
        await alice.post(
            "/api/calendars",
            json={"name": "Streamo", "url": "https://s.example/c.ics", "area_id": areas[0]["id"]},
        )
    ).json()
    account = (
        await alice.post(
            "/api/mail/accounts",
            json={
                "email": "alice@example.org",
                "password": "imap-geheim",
                "imap_host": "imap.example.org",
            },
        )
    ).json()
    message = (await alice.get("/api/mail/messages")).json()[0]
    rule = (
        await alice.post("/api/mail/rules", json={"name": "Geheim", "subject_contains": "Geheim"})
    ).json()
    return {
        "rule": rule,
        "area": areas[0],
        "account": account,
        "mail": message,
        "task": task,
        "session": session,
        "event": event,
        "feed": feed,
        "subscription": subscription,
        "contact": contact,
        "passkey": passkey,
        "calendar": calendar,
    }


async def test_foreign_task_is_invisible(alice: AsyncClient, bob: AsyncClient) -> None:
    objects = await _alice_objects(alice)
    task_id = objects["task"]["id"]

    assert (await bob.get(f"/api/tasks/{task_id}")).status_code == 404
    assert (await bob.patch(f"/api/tasks/{task_id}", json={"title": "x"})).status_code == 404
    assert (await bob.delete(f"/api/tasks/{task_id}")).status_code == 404
    assert (await bob.post(f"/api/tasks/{task_id}/complete")).status_code == 404
    assert (await bob.post(f"/api/tasks/{task_id}/reopen")).status_code == 404

    task = (await alice.get(f"/api/tasks/{task_id}")).json()
    assert task["title"] == "Geheimprojekt"
    assert task["status"] == "open"


async def test_foreign_area_is_invisible(alice: AsyncClient, bob: AsyncClient) -> None:
    objects = await _alice_objects(alice)
    area_id = objects["area"]["id"]

    assert (await bob.patch(f"/api/areas/{area_id}", json={"name": "x"})).status_code == 404
    assert (await bob.delete(f"/api/areas/{area_id}")).status_code == 404
    assert (
        await bob.post("/api/tasks", json={"title": "Einschleusen", "area_id": area_id})
    ).status_code == 404
    assert (
        await bob.post("/api/tasks/quick", json={"text": "Einschleusen", "area_id": area_id})
    ).status_code == 404

    own = (await bob.post("/api/tasks", json={"title": "Meins"})).json()
    moved = await bob.patch(f"/api/tasks/{own['id']}", json={"area_id": area_id})
    assert moved.status_code == 404

    bob_areas = (await bob.get("/api/areas")).json()
    r = await bob.delete(f"/api/areas/{bob_areas[0]['id']}", params={"move_to": area_id})
    assert r.status_code == 404


async def test_lists_and_search_do_not_leak(alice: AsyncClient, bob: AsyncClient) -> None:
    objects = await _alice_objects(alice)
    area_id = objects["area"]["id"]

    for view in ("today", "upcoming", "open", "done", "archived", "all"):
        assert (await bob.get("/api/tasks", params={"view": view})).json() == []
    assert (await bob.get("/api/tasks", params={"area_id": area_id})).json() == []
    empty = {"tasks": [], "events": []}
    for word in ("geheim", "vertraulich", "besprechung"):
        assert (await bob.get("/api/search", params={"q": word})).json() == empty
    bob_events = await bob.get("/api/events", params={"from": "2026-09-01", "to": "2026-10-01"})
    assert bob_events.json() == []
    other_area = await bob.get(
        "/api/events", params={"from": "2026-09-01", "to": "2026-10-01", "area_id": area_id}
    )
    assert other_area.json() == []
    assert all(a["id"] != area_id for a in (await bob.get("/api/areas")).json())
    quick = await bob.post("/api/tasks/quick/preview", json={"text": "x @Arbeit"})
    assert quick.json()["area_id"] != area_id


async def test_foreign_session_cannot_be_revoked(alice: AsyncClient, bob: AsyncClient) -> None:
    objects = await _alice_objects(alice)
    r = await bob.delete(f"/api/auth/sessions/{objects['session']['id']}")
    assert r.status_code == 404
    assert (await alice.get("/api/auth/me")).status_code == 200


def _object_routes() -> list[tuple[str, str]]:
    """Alle Routen mit Objekt-ID im Pfad – aus dem OpenAPI-Schema, damit neue Routen
    automatisch mitgetestet werden."""
    schema = create_app(make_settings()).openapi()
    routes: list[tuple[str, str]] = []
    for path, operations in schema["paths"].items():
        if re.search(r"\{\w+_id\}", path):
            routes.extend((method.upper(), path) for method in sorted(operations))
    return routes


OBJECT_ROUTES = _object_routes()


def test_every_object_route_is_covered() -> None:
    assert len(OBJECT_ROUTES) >= 8
    params = {p for _, path in OBJECT_ROUTES for p in re.findall(r"\{(\w+_id)\}", path)}
    known = {
        "task_id",
        "area_id",
        "session_id",
        "event_id",
        "feed_id",
        "subscription_id",
        "contact_id",
        "passkey_id",
        "calendar_id",
        "account_id",
        "mail_id",
        "rule_id",
        "connection_id",
        "member_id",
        "invite_id",
        "comment_id",
    }
    assert params <= known, params


@pytest.mark.parametrize(("method", "path"), OBJECT_ROUTES)
async def test_every_object_route_rejects_foreign_ids(
    alice: AsyncClient,
    bob: AsyncClient,
    resources: Resources,
    client_factory: ClientFactory,
    method: str,
    path: str,
) -> None:
    objects = await _alice_objects(alice)
    me = (await alice.get("/api/auth/me")).json()
    async with resources.sessionmaker() as db:
        connection = CalendarConnection(
            owner_id=uuid.UUID(me["id"]),
            area_id=uuid.UUID(objects["area"]["id"]),
            provider="google",
            account_email="alice@gmail.com",
            remote_calendar_id="primary",
            token_encrypted="verschlüsselt",
            enabled=True,
            event_count=0,
        )
        db.add(connection)
        await db.commit()
        connection_id = str(connection.id)
    # Carol ist Mitglied in Alice' Bereich, Bob nicht; eine Einladung bleibt offen
    area_id = objects["area"]["id"]
    for _ in range(2):
        created = await alice.post(f"/api/areas/{area_id}/invites", json={"role": "member"})
        assert created.status_code == 201
    token = created.json()["url"].split("#", 1)[1]
    open_invite = (await alice.get(f"/api/areas/{area_id}/invites")).json()[0]["id"]
    await create_user(resources, "carol@example.org")
    carol = await client_factory()
    await login(carol, "carol@example.org")
    assert (await carol.post("/api/invites/accept", json={"token": token})).status_code == 200
    members = (await alice.get(f"/api/areas/{area_id}/members")).json()
    member_id = next(m["id"] for m in members if m["display_name"] == "carol")
    comment = await alice.post(
        f"/api/tasks/{objects['task']['id']}/comments", json={"body": "vertraulich"}
    )
    ids = {
        "comment_id": comment.json()["id"],
        "member_id": member_id,
        "invite_id": open_invite,
        "connection_id": connection_id,
        "task_id": objects["task"]["id"],
        "area_id": objects["area"]["id"],
        "session_id": objects["session"]["id"],
        "event_id": objects["event"]["id"],
        "feed_id": objects["feed"]["id"],
        "subscription_id": objects["subscription"]["id"],
        "contact_id": objects["contact"]["id"],
        "passkey_id": objects["passkey"]["id"],
        "calendar_id": objects["calendar"]["id"],
        "account_id": objects["account"]["id"],
        "mail_id": objects["mail"]["id"],
        "rule_id": objects["rule"]["id"],
    }
    url = re.sub(r"\{(\w+_id)\}", lambda m: ids[m.group(1)], path)
    body = {} if method in ("PATCH", "PUT") else None
    response = await bob.request(method, url, json=body)
    assert response.status_code in (403, 404), (method, url, response.status_code)
    # Alice' Daten sind unverändert vorhanden
    assert (await alice.get(f"/api/tasks/{ids['task_id']}")).status_code == 200
    contact = await alice.get(f"/api/contacts/{ids['contact_id']}")
    assert contact.json()["name"] == "Vertraulich"
    assert len((await alice.get("/api/mail/accounts")).json()) == 1
    assert (await bob.get("/api/mail/messages")).json() == []
    assert (await bob.get("/api/mail/rules")).json() == []
    assert len((await alice.get("/api/mail/rules")).json()) == 1
