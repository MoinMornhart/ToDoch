from httpx import AsyncClient


async def test_area_calendar_settings(alice: AsyncClient) -> None:
    default = (await alice.get("/api/areas")).json()[0]
    assert (default["week_days"], default["day_start"], default["day_end"]) == (127, 0, 24)

    created = await alice.post(
        "/api/areas", json={"name": "Büro", "week_days": 31, "day_start": 8, "day_end": 18}
    )
    assert created.status_code == 201, created.text
    area = created.json()
    assert (area["week_days"], area["day_start"], area["day_end"]) == (31, 8, 18)

    changed = await alice.patch(f"/api/areas/{area['id']}", json={"day_end": 20})
    assert changed.json()["day_end"] == 20

    # Beginn nach Ende, ungültige Werte
    assert (
        await alice.patch(f"/api/areas/{area['id']}", json={"day_start": 21})
    ).status_code == 422
    for bad in ({"week_days": 0}, {"week_days": 128}, {"day_start": 24}, {"day_end": 0}):
        assert (await alice.patch(f"/api/areas/{area['id']}", json=bad)).status_code == 422
    assert (
        await alice.post("/api/areas", json={"name": "X", "day_start": 10, "day_end": 9})
    ).status_code == 422
    unchanged = next(a for a in (await alice.get("/api/areas")).json() if a["id"] == area["id"])
    assert (unchanged["day_start"], unchanged["day_end"]) == (8, 20)
