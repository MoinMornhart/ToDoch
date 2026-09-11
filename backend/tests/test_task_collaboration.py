"""Zusammenarbeit in geteilten Bereichen: zuständige Person und Kommentare."""

import uuid
from typing import Any
from urllib.parse import urlsplit

from httpx import AsyncClient


async def _share(owner: AsyncClient, guest: AsyncClient, area: str, role: str) -> str:
    areas = {a["name"]: a["id"] for a in (await owner.get("/api/areas")).json()}
    created = await owner.post(f"/api/areas/{areas[area]}/invites", json={"role": role})
    token = urlsplit(created.json()["url"]).fragment
    assert (await guest.post("/api/invites/accept", json={"token": token})).status_code == 200
    return areas[area]


async def _members(client: AsyncClient, area_id: str) -> dict[str, dict[str, Any]]:
    return {
        m["display_name"]: m for m in (await client.get(f"/api/areas/{area_id}/members")).json()
    }


async def test_assign_tasks_to_members(alice: AsyncClient, bob: AsyncClient) -> None:
    work = await _share(alice, bob, "Arbeit", "member")
    shared = [a for a in (await alice.get("/api/areas")).json() if a["id"] == work]
    assert shared[0]["shared"] is True
    members = await _members(alice, work)
    bob_id = members["bob"]["user_id"]

    created = await alice.post(
        "/api/tasks", json={"title": "Angebot prüfen", "area_id": work, "assignee_id": bob_id}
    )
    assert created.status_code == 201, created.text
    task = created.json()
    assert (task["assignee_id"], task["assignee_name"]) == (bob_id, "bob")

    mine = (await bob.get("/api/tasks", params={"view": "open", "assigned": "me"})).json()
    assert [t["title"] for t in mine] == ["Angebot prüfen"]
    assert (await alice.get("/api/tasks", params={"assigned": "me"})).json() == []

    stranger = await alice.patch(
        f"/api/tasks/{task['id']}", json={"assignee_id": str(uuid.uuid4())}
    )
    assert stranger.status_code == 422

    # In einen nicht geteilten Bereich verschoben → Bob ist nicht mehr zuständig
    private = next(a["id"] for a in (await alice.get("/api/areas")).json() if a["name"] == "Privat")
    moved = (await alice.patch(f"/api/tasks/{task['id']}", json={"area_id": private})).json()
    assert moved["assignee_id"] is None

    # Nur-lesen-Mitglieder übernehmen keine Aufgaben
    await alice.patch(f"/api/areas/{work}/members/{members['bob']['id']}", json={"role": "viewer"})
    viewer = await alice.post(
        "/api/tasks",
        json={"title": "x", "area_id": work, "assignee_id": bob_id},
        headers={"Accept-Language": "en"},
    )
    assert viewer.status_code == 422
    assert viewer.json()["detail"] == "This person cannot take on tasks in this area."


async def test_comments(alice: AsyncClient, bob: AsyncClient) -> None:
    work = await _share(alice, bob, "Arbeit", "member")
    task = (await alice.post("/api/tasks", json={"title": "Folien", "area_id": work})).json()

    posted = await bob.post(
        f"/api/tasks/{task['id']}/comments",
        json={"body": "Bitte **bis Freitag** <script>alert(1)</script>"},
    )
    assert posted.status_code == 201, posted.text
    comment = posted.json()
    assert "<strong>bis Freitag</strong>" in comment["body_html"]
    assert "<script" not in comment["body_html"]
    assert (comment["author_name"], comment["mine"]) == ("bob", True)

    seen = (await alice.get(f"/api/tasks/{task['id']}/comments")).json()
    assert [(c["author_name"], c["mine"]) for c in seen] == [("bob", False)]
    empty = await alice.post(f"/api/tasks/{task['id']}/comments")
    assert empty.status_code == 422

    # Fremde Kommentare löscht nur, wer verwalten darf
    own = (await alice.post(f"/api/tasks/{task['id']}/comments", json={"body": "Ok"})).json()
    denied = await bob.delete(f"/api/tasks/{task['id']}/comments/{own['id']}")
    assert denied.status_code == 403
    assert (
        await alice.delete(f"/api/tasks/{task['id']}/comments/{comment['id']}")
    ).status_code == 204
    assert (await bob.delete(f"/api/tasks/{task['id']}/comments/{own['id']}")).status_code == 403

    # Nur lesen: Kommentare sehen ja, schreiben nein
    members = await _members(alice, work)
    await alice.patch(f"/api/areas/{work}/members/{members['bob']['id']}", json={"role": "viewer"})
    assert len((await bob.get(f"/api/tasks/{task['id']}/comments")).json()) == 1
    blocked = await bob.post(f"/api/tasks/{task['id']}/comments", json={"body": "Nein"})
    assert blocked.status_code == 403
