"""Geteilte Bereiche: Einladungslinks, Rollen, Sichtbarkeit, Verlassen."""

from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from httpx import AsyncClient
from sqlalchemy import update

from app.models import AreaInvite
from app.resources import Resources


async def _area(client: AsyncClient, name: str) -> dict[str, Any]:
    areas: list[dict[str, Any]] = (await client.get("/api/areas")).json()
    return next(a for a in areas if a["name"] == name)


async def _invite(client: AsyncClient, area_id: str, role: str = "member") -> str:
    created = await client.post(f"/api/areas/{area_id}/invites", json={"role": role})
    assert created.status_code == 201, created.text
    url = urlsplit(created.json()["url"])
    assert url.path == "/invite"
    return url.fragment


async def test_share_an_area_with_roles(alice: AsyncClient, bob: AsyncClient) -> None:
    work = await _area(alice, "Arbeit")
    secret_task = await alice.post(
        "/api/tasks", json={"title": "Quartalsbericht", "area_id": work["id"]}
    )
    token = await _invite(alice, work["id"])

    preview = (await bob.post("/api/invites/preview", json={"token": token})).json()
    assert preview == {
        "area_name": "Arbeit",
        "role": "member",
        "invited_by": "alice",
        "already_member": False,
    }
    joined = await bob.post("/api/invites/accept", json={"token": token})
    assert joined.status_code == 200, joined.text
    assert joined.json()["role"] == "member"
    again = await bob.post("/api/invites/accept", json={"token": token})
    assert again.status_code == 404  # jeder Link gilt einmal

    # Bob sieht den Bereich samt Aufgaben und kann darin arbeiten
    shared = await _area(bob, "Arbeit")
    assert shared["id"] == work["id"] and shared["role"] == "member"
    task_id = secret_task.json()["id"]
    assert (await bob.get(f"/api/tasks/{task_id}")).status_code == 200
    found = (await bob.get("/api/search", params={"q": "Quartalsbericht"})).json()
    assert [t["title"] for t in found["tasks"]] == ["Quartalsbericht"]
    created = await bob.post("/api/tasks", json={"title": "Folien", "area_id": work["id"]})
    assert created.status_code == 201
    titles = [t["title"] for t in (await alice.get("/api/tasks", params={"view": "all"})).json()]
    assert "Folien" in titles

    # … aber nicht verwalten
    assert (await bob.patch(f"/api/areas/{work['id']}", json={"name": "x"})).status_code == 403
    assert (await bob.delete(f"/api/areas/{work['id']}")).status_code == 403
    assert (await bob.post(f"/api/areas/{work['id']}/invites", json={})).status_code == 403

    members = (await alice.get(f"/api/areas/{work['id']}/members")).json()
    assert [(m["display_name"], m["role"]) for m in members] == [
        ("alice", "owner"),
        ("bob", "member"),
    ]
    bob_member = members[1]["id"]

    # Nur lesen: ansehen ja, ändern nein
    await alice.patch(f"/api/areas/{work['id']}/members/{bob_member}", json={"role": "viewer"})
    assert (await bob.get(f"/api/tasks/{task_id}")).status_code == 200
    blocked = await bob.post("/api/tasks", json={"title": "Nein", "area_id": work["id"]})
    assert blocked.status_code == 403
    assert (await bob.patch(f"/api/tasks/{task_id}", json={"title": "x"})).status_code == 403

    # Verlassen – danach ist alles wieder unsichtbar
    assert (await bob.delete(f"/api/areas/{work['id']}/membership")).status_code == 204
    assert all(a["id"] != work["id"] for a in (await bob.get("/api/areas")).json())
    assert (await bob.get(f"/api/tasks/{task_id}")).status_code == 404
    assert (await bob.get(f"/api/areas/{work['id']}/members")).status_code == 404


async def test_invites_expire_and_can_be_revoked(
    alice: AsyncClient, bob: AsyncClient, resources: Resources
) -> None:
    work = await _area(alice, "Arbeit")
    token = await _invite(alice, work["id"], "admin")
    async with resources.sessionmaker() as db:
        await db.execute(
            update(AreaInvite).values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await db.commit()
    expired = await bob.post("/api/invites/accept", json={"token": token})
    assert expired.status_code == 404
    assert expired.json()["detail"] == "Die Einladung ist ungültig oder abgelaufen."

    token = await _invite(alice, work["id"])
    invites = (await alice.get(f"/api/areas/{work['id']}/invites")).json()
    assert len(invites) == 1
    revoked = await alice.delete(f"/api/areas/{work['id']}/invites/{invites[0]['id']}")
    assert revoked.status_code == 204
    assert (await bob.post("/api/invites/accept", json={"token": token})).status_code == 404

    own = await _invite(alice, work["id"])
    assert (await alice.post("/api/invites/accept", json={"token": own})).status_code == 409
    wrong = await bob.post("/api/invites/preview", json={"token": "x" * 43})
    assert wrong.status_code == 404


async def test_admins_can_manage_but_not_delete(alice: AsyncClient, bob: AsyncClient) -> None:
    work = await _area(alice, "Arbeit")
    await bob.post("/api/invites/accept", json={"token": await _invite(alice, work["id"], "admin")})
    assert (
        await bob.patch(f"/api/areas/{work['id']}", json={"color": "#112233"})
    ).status_code == 200
    assert (await bob.post(f"/api/areas/{work['id']}/invites", json={})).status_code == 201
    denied = await bob.delete(f"/api/areas/{work['id']}", headers={"Accept-Language": "en"})
    assert denied.status_code == 403
    assert denied.json()["detail"] == "Only the owner can delete the area."
