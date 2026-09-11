from typing import Any

from httpx import AsyncClient

WEEK = {"from": "2026-09-14", "to": "2026-10-05"}  # drei Wochen ab Montag


async def _create(client: AsyncClient, **fields: Any) -> dict[str, Any]:
    body = {"title": "Termin", "start_date": "2026-09-14", "start_time": "09:00", **fields}
    r = await client.post("/api/events", json=body)
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


async def _list(client: AsyncClient, **params: str) -> list[dict[str, Any]]:
    r = await client.get("/api/events", params={**WEEK, **params})
    assert r.status_code == 200, r.text
    return r.json()  # type: ignore[no-any-return]


async def test_create_and_list(alice: AsyncClient) -> None:
    created = await _create(
        alice,
        title="Zahnarzt",
        location="Praxis Dr. Weiß",
        description="**Karte** mitnehmen",
        end_time="10:30",
        reminders=[60, 15, 15],
        attendees=[{"name": "Dr. Weiß", "email": "praxis@example.org"}],
    )
    event = created["event"]
    assert event["start_time"] == "09:00:00" and event["end_time"] == "10:30:00"
    assert event["reminders"] == [15, 60]
    assert "<strong>Karte</strong>" in event["description_html"]
    assert event["uid"].endswith("@todoch")

    items = await _list(alice)
    assert len(items) == 1
    assert items[0]["start_local"] == "2026-09-14T09:00"
    assert items[0]["end_local"] == "2026-09-14T10:30"
    assert items[0]["start"] == "2026-09-14T07:00:00Z"  # Berlin = UTC+2


async def test_defaults_and_validation(alice: AsyncClient) -> None:
    one_hour = (await _create(alice))["event"]
    assert one_hour["end_time"] == "10:00:00"
    bad = await alice.post(
        "/api/events",
        json={"title": "x", "start_date": "2026-09-14", "start_time": "10:00", "end_time": "09:00"},
    )
    assert bad.status_code == 422
    no_time = await alice.post("/api/events", json={"title": "x", "start_date": "2026-09-14"})
    assert no_time.status_code == 422
    bad_rule = await alice.post(
        "/api/events",
        json={
            "title": "x",
            "start_date": "2026-09-14",
            "start_time": "9:00",
            "rrule": "FREQ=SECONDLY",
        },
    )
    assert bad_rule.status_code == 422
    bad_url = await alice.post(
        "/api/events",
        json={
            "title": "x",
            "start_date": "2026-09-14",
            "start_time": "9:00",
            "url": "javascript:alert(1)",
        },
    )
    assert bad_url.status_code == 422
    too_long = await alice.get("/api/events", params={"from": "2026-01-01", "to": "2028-01-01"})
    assert too_long.status_code == 422


async def test_all_day(alice: AsyncClient) -> None:
    created = await _create(
        alice,
        title="Urlaub",
        all_day=True,
        start_date="2026-09-16",
        end_date="2026-09-18",
        start_time=None,
    )
    assert created["event"]["end_date"] == "2026-09-18"
    items = await _list(alice)
    assert items[0]["all_day"] is True
    assert items[0]["start_local"] == "2026-09-16"
    assert items[0]["end_local"] == "2026-09-19"  # exklusiv
    assert await _list(alice, **{"from": "2026-09-19", "to": "2026-09-20"}) == []


async def test_recurring_edit_this_occurrence(alice: AsyncClient) -> None:
    series = (await _create(alice, title="Jour fixe", rrule="FREQ=WEEKLY"))["event"]
    items = await _list(alice)
    assert [i["start_local"] for i in items] == [
        "2026-09-14T09:00",
        "2026-09-21T09:00",
        "2026-09-28T09:00",
    ]
    second = items[1]
    r = await alice.patch(
        f"/api/events/{series['id']}",
        params={"scope": "this", "occurrence": second["recurrence_id"]},
        json={
            "start_date": "2026-09-22",
            "start_time": "11:00",
            "end_time": "12:00",
            "title": "Jour fixe (verschoben)",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["event"]["series_id"] == series["id"]

    items = await _list(alice)
    assert [(i["start_local"], i["title"]) for i in items] == [
        ("2026-09-14T09:00", "Jour fixe"),
        ("2026-09-22T11:00", "Jour fixe (verschoben)"),
        ("2026-09-28T09:00", "Jour fixe"),
    ]

    # Das geänderte Vorkommen lädt man über seine eigene ID
    override_id = items[1]["event_id"]
    got = await alice.get(f"/api/events/{override_id}")
    assert got.json()["title"] == "Jour fixe (verschoben)"


async def test_recurring_delete_this_and_following(alice: AsyncClient) -> None:
    series = (await _create(alice, title="Sport", rrule="FREQ=WEEKLY"))["event"]
    items = await _list(alice)
    r = await alice.delete(
        f"/api/events/{series['id']}",
        params={"scope": "this", "occurrence": items[0]["recurrence_id"]},
    )
    assert r.status_code == 204
    assert [i["start_local"][:10] for i in await _list(alice)] == ["2026-09-21", "2026-09-28"]

    r = await alice.delete(
        f"/api/events/{series['id']}",
        params={"scope": "following", "occurrence": items[2]["recurrence_id"]},
    )
    assert r.status_code == 204
    assert [i["start_local"][:10] for i in await _list(alice)] == ["2026-09-21"]


async def test_recurring_edit_following_splits_series(alice: AsyncClient) -> None:
    series = (await _create(alice, title="Kurs", rrule="FREQ=WEEKLY;COUNT=3"))["event"]
    items = await _list(alice)
    r = await alice.patch(
        f"/api/events/{series['id']}",
        params={"scope": "following", "occurrence": items[1]["recurrence_id"]},
        json={"title": "Kurs (neuer Raum)", "location": "Raum 2"},
    )
    assert r.status_code == 200, r.text
    new_series = r.json()["event"]
    assert new_series["id"] != series["id"]
    assert new_series["rrule"] == "FREQ=WEEKLY;COUNT=2"
    assert [i["title"] for i in await _list(alice)] == [
        "Kurs",
        "Kurs (neuer Raum)",
        "Kurs (neuer Raum)",
    ]
    old = await alice.get(f"/api/events/{series['id']}")
    assert old.json()["rrule"] == "FREQ=WEEKLY;COUNT=1"


async def test_recurring_edit_all_shifts_everything(alice: AsyncClient) -> None:
    series = (await _create(alice, title="Standup", rrule="FREQ=WEEKLY"))["event"]
    items = await _list(alice)
    await alice.patch(
        f"/api/events/{series['id']}",
        params={"scope": "this", "occurrence": items[2]["recurrence_id"]},
        json={"title": "Standup (Sonder)"},
    )
    await alice.delete(
        f"/api/events/{series['id']}",
        params={"scope": "this", "occurrence": items[1]["recurrence_id"]},
    )
    # Vom ersten Vorkommen aus eine Stunde später – für alle
    r = await alice.patch(
        f"/api/events/{series['id']}",
        params={"scope": "all", "occurrence": items[0]["recurrence_id"]},
        json={"start_date": "2026-09-14", "start_time": "10:00", "end_time": "11:00"},
    )
    assert r.status_code == 200, r.text
    after = await _list(alice)
    assert [(i["start_local"], i["title"]) for i in after] == [
        ("2026-09-14T10:00", "Standup"),
        ("2026-09-28T10:00", "Standup (Sonder)"),
    ]


async def test_delete_all_removes_overrides(alice: AsyncClient) -> None:
    series = (await _create(alice, rrule="FREQ=DAILY;COUNT=5"))["event"]
    items = await _list(alice)
    await alice.patch(
        f"/api/events/{series['id']}",
        params={"scope": "this", "occurrence": items[1]["recurrence_id"]},
        json={"title": "anders"},
    )
    assert (await alice.delete(f"/api/events/{series['id']}")).status_code == 204
    assert await _list(alice) == []


async def test_conflicts_only_in_same_area(alice: AsyncClient) -> None:
    areas = {a["name"]: a["id"] for a in (await alice.get("/api/areas")).json()}
    await _create(alice, title="Kunde A", area_id=areas["Arbeit"], end_time="10:00")
    clash = await _create(
        alice, title="Kunde B", area_id=areas["Arbeit"], start_time="09:30", end_time="10:30"
    )
    assert [c["title"] for c in clash["conflicts"]] == ["Kunde A"]
    other_area = await _create(alice, title="Privat", area_id=areas["Privat"], start_time="09:30")
    assert other_area["conflicts"] == []
    back_to_back = await _create(alice, title="Danach", area_id=areas["Arbeit"], start_time="10:30")
    assert back_to_back["conflicts"] == []
    free = await _create(
        alice, title="Frei", area_id=areas["Arbeit"], start_time="09:00", transparency="transparent"
    )
    assert free["conflicts"] == []


async def test_area_filter_and_move(alice: AsyncClient) -> None:
    areas = {a["name"]: a["id"] for a in (await alice.get("/api/areas")).json()}
    event = (await _create(alice, area_id=areas["Arbeit"]))["event"]
    assert len(await _list(alice, area_id=areas["Privat"])) == 0
    await alice.patch(f"/api/events/{event['id']}", json={"area_id": areas["Privat"]})
    assert len(await _list(alice, area_id=areas["Privat"])) == 1


async def test_search_includes_events(alice: AsyncClient) -> None:
    await _create(alice, title="Elternabend", location="Grundschule")
    r = await alice.get("/api/search", params={"q": "grundschule"})
    assert r.status_code == 200
    body = r.json()
    assert body["tasks"] == []
    assert [e["title"] for e in body["events"]] == ["Elternabend"]
    assert body["events"][0]["start_local"] == "2026-09-14T09:00"


async def test_tasks_in_date_range(alice: AsyncClient) -> None:
    for title, due in (("vorher", "2026-09-13"), ("drin", "2026-09-20"), ("danach", "2026-10-05")):
        await alice.post("/api/tasks", json={"title": title, "due_date": due})
    r = await alice.get("/api/tasks", params={"view": "all", **WEEK})
    assert [t["title"] for t in r.json()] == ["drin"]
