from datetime import date, timedelta
from typing import Any

from httpx import AsyncClient


async def _areas(client: AsyncClient) -> dict[str, str]:
    return {a["name"]: a["id"] for a in (await client.get("/api/areas")).json()}


async def _create(client: AsyncClient, **fields: Any) -> dict[str, Any]:
    r = await client.post("/api/tasks", json={"title": "Aufgabe", **fields})
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


async def test_crud(alice: AsyncClient) -> None:
    areas = await _areas(alice)
    task = await _create(
        alice,
        title="  Steuer  ",
        notes="**wichtig** <script>x</script>",
        area_id=areas["Privat"],
        due_date="2026-10-01",
        due_time="09:30",
        priority=2,
        tags=["Finanzen", "finanzen", "amt"],
        checklist=[{"text": "Belege"}, {"text": "Formular"}],
    )
    assert task["title"] == "Steuer"
    assert task["area_id"] == areas["Privat"]
    assert task["tags"] == ["finanzen", "amt"]
    assert "<strong>wichtig</strong>" in task["notes_html"]
    assert "<script" not in task["notes_html"]
    assert [c["text"] for c in task["checklist"]] == ["Belege", "Formular"]

    first = task["checklist"][0]
    r = await alice.patch(
        f"/api/tasks/{task['id']}",
        json={
            "title": "Steuererklärung",
            "checklist": [{"id": first["id"], "text": "Belege", "done": True}, {"text": "Abgeben"}],
        },
    )
    assert r.status_code == 200
    updated = r.json()
    assert updated["title"] == "Steuererklärung"
    assert [(c["text"], c["done"]) for c in updated["checklist"]] == [
        ("Belege", True),
        ("Abgeben", False),
    ]
    assert updated["checklist"][0]["id"] == first["id"]

    cleared = await alice.patch(
        f"/api/tasks/{task['id']}", json={"due_date": None, "due_time": None}
    )
    assert cleared.json()["due_date"] is None

    assert (await alice.get(f"/api/tasks/{task['id']}")).status_code == 200
    assert (await alice.delete(f"/api/tasks/{task['id']}")).status_code == 204
    assert (await alice.get(f"/api/tasks/{task['id']}")).status_code == 404


async def test_validation(alice: AsyncClient) -> None:
    assert (await alice.post("/api/tasks", json={"title": ""})).status_code == 422
    assert (await alice.post("/api/tasks", json={"title": "x" * 301})).status_code == 422
    assert (
        await alice.post("/api/tasks", json={"title": "x", "due_time": "10:00"})
    ).status_code == 422
    assert (
        await alice.post("/api/tasks", json={"title": "x", "recurrence": "FREQ=HOURLY"})
    ).status_code == 422
    assert (await alice.post("/api/tasks", json={"title": "x", "priority": 5})).status_code == 422
    assert (
        await alice.post("/api/tasks", json={"title": "x", "tags": ["mit leerzeichen"]})
    ).status_code == 422
    assert (
        await alice.post("/api/tasks", json={"title": "x", "notes": "n" * 50_001})
    ).status_code == 422
    task = await _create(alice)
    r = await alice.patch(f"/api/tasks/{task['id']}", json={"due_time": "10:00"})
    assert r.status_code == 422


async def test_views(alice: AsyncClient) -> None:
    today = date.today()
    await _create(alice, title="überfällig", due_date=str(today - timedelta(days=2)))
    await _create(alice, title="heute", due_date=str(today))
    await _create(alice, title="bald", due_date=str(today + timedelta(days=3)))
    await _create(alice, title="später", due_date=str(today + timedelta(days=30)))
    await _create(alice, title="ohne Datum")
    done = await _create(alice, title="erledigt")
    await alice.post(f"/api/tasks/{done['id']}/complete")

    async def titles(**params: str) -> list[str]:
        return [t["title"] for t in (await alice.get("/api/tasks", params=params)).json()]

    assert await titles(view="today") == ["überfällig", "heute"]
    assert await titles(view="upcoming") == ["bald"]
    assert await titles(view="open") == ["überfällig", "heute", "bald", "später", "ohne Datum"]
    assert await titles(view="done") == ["erledigt"]
    assert await titles(day=str(today)) == ["heute"]


async def test_area_filter_and_tag_filter(alice: AsyncClient) -> None:
    areas = await _areas(alice)
    await _create(alice, title="A", area_id=areas["Arbeit"], tags=["x"])
    await _create(alice, title="P", area_id=areas["Privat"])
    arbeit = (await alice.get("/api/tasks", params={"area_id": areas["Arbeit"]})).json()
    assert [t["title"] for t in arbeit] == ["A"]
    tagged = (await alice.get("/api/tasks", params={"tag": "X"})).json()
    assert [t["title"] for t in tagged] == ["A"]


async def test_quick_add(alice: AsyncClient) -> None:
    areas = await _areas(alice)
    preview = await alice.post(
        "/api/tasks/quick/preview",
        json={"text": "Rechnung zahlen morgen 14:00 !hoch #finanzen @PRIV"},
    )
    assert preview.status_code == 200
    p = preview.json()
    assert p["title"] == "Rechnung zahlen"
    assert p["area_id"] == areas["Privat"]
    assert p["area_unknown"] is False
    assert p["priority"] == 3

    created = await alice.post(
        "/api/tasks/quick", json={"text": "Rechnung zahlen morgen 14:00 !hoch #finanzen @privat"}
    )
    assert created.status_code == 201
    task = created.json()
    assert task["area_id"] == areas["Privat"]
    assert task["due_time"] == "14:00:00"
    assert task["tags"] == ["finanzen"]

    unknown = await alice.post("/api/tasks/quick/preview", json={"text": "X @gibtsnicht"})
    assert unknown.json()["area_unknown"] is True
    assert unknown.json()["area_id"] == areas["Arbeit"]


async def test_complete_recurring_creates_next(alice: AsyncClient) -> None:
    today = date.today()
    task = await _create(
        alice,
        title="Gießen",
        due_date=str(today),
        recurrence="FREQ=DAILY;INTERVAL=2",
        checklist=[{"text": "Balkon", "done": True}],
    )
    r = await alice.post(f"/api/tasks/{task['id']}/complete")
    assert r.status_code == 200
    body = r.json()
    assert body["task"]["status"] == "done"
    assert body["task"]["recurrence"] is None
    following = body["next"]
    assert following["due_date"] == str(today + timedelta(days=2))
    assert following["recurrence"] == "FREQ=DAILY;INTERVAL=2"
    assert following["checklist"][0]["done"] is False

    again = await alice.post(f"/api/tasks/{task['id']}/complete")
    assert again.json()["next"] is None
    open_titles = [t["title"] for t in (await alice.get("/api/tasks")).json()]
    assert open_titles == ["Gießen"]

    reopened = await alice.post(f"/api/tasks/{task['id']}/reopen")
    assert reopened.json()["status"] == "open"


async def test_search(alice: AsyncClient) -> None:
    await _create(alice, title="Steuererklärung abgeben", notes="Belege vom Finanzamt")
    await _create(alice, title="Einkaufen", tags=["haushalt"])
    await _create(alice, title="Nichts")

    async def found(q: str) -> list[str]:
        response = await alice.get("/api/search", params={"q": q})
        return [t["title"] for t in response.json()["tasks"]]

    assert await found("steuer") == ["Steuererklärung abgeben"]
    assert await found("finanzamt") == ["Steuererklärung abgeben"]
    assert await found("haushalt") == ["Einkaufen"]
    assert await found("'; drop table tasks; --") == []
    assert await found("&|!:*") == []


async def test_areas_crud(alice: AsyncClient) -> None:
    r = await alice.post("/api/areas", json={"name": "Verein", "color": "#AABBCC", "icon": "users"})
    assert r.status_code == 201
    area = r.json()
    assert area["color"] == "#aabbcc"
    assert area["role"] == "owner"
    assert (await alice.post("/api/areas", json={"name": "Verein"})).status_code == 409
    assert (await alice.post("/api/areas", json={"name": "X", "color": "red"})).status_code == 422
    assert (await alice.post("/api/areas", json={"name": "X", "icon": "bomb"})).status_code == 422

    renamed = await alice.patch(f"/api/areas/{area['id']}", json={"name": "Sportverein"})
    assert renamed.json()["name"] == "Sportverein"

    await _create(alice, title="Beitrag", area_id=area["id"])
    blocked = await alice.delete(f"/api/areas/{area['id']}")
    assert blocked.status_code == 409

    areas = await _areas(alice)
    moved = await alice.delete(f"/api/areas/{area['id']}", params={"move_to": areas["Privat"]})
    assert moved.status_code == 204
    privat = (await alice.get("/api/tasks", params={"area_id": areas["Privat"]})).json()
    assert [t["title"] for t in privat] == ["Beitrag"]


async def test_last_area_cannot_be_deleted(alice: AsyncClient) -> None:
    areas = await _areas(alice)
    assert (await alice.delete(f"/api/areas/{areas['Privat']}")).status_code == 204
    assert (await alice.delete(f"/api/areas/{areas['Arbeit']}")).status_code == 409


async def test_open_count(alice: AsyncClient) -> None:
    areas = await _areas(alice)
    await _create(alice, area_id=areas["Arbeit"])
    await _create(alice, area_id=areas["Arbeit"])
    listed = {a["name"]: a["open_count"] for a in (await alice.get("/api/areas")).json()}
    assert listed == {"Arbeit": 2, "Privat": 0}
