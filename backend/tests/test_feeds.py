from typing import Any

from httpx import AsyncClient

from tests.conftest import ClientFactory


async def _event(client: AsyncClient, **fields: Any) -> dict[str, Any]:
    body = {"title": "Termin", "start_date": "2026-09-14", "start_time": "09:00", **fields}
    r = await client.post("/api/events", json=body)
    assert r.status_code == 201, r.text
    return r.json()["event"]  # type: ignore[no-any-return]


async def _areas(client: AsyncClient) -> dict[str, str]:
    return {a["name"]: a["id"] for a in (await client.get("/api/areas")).json()}


def _token(url: str) -> str:
    return url.rsplit("/", 1)[1].removesuffix(".ics")


async def test_feed_contains_events_series_and_exceptions(
    alice: AsyncClient, client_factory: ClientFactory
) -> None:
    areas = await _areas(alice)
    series = await _event(
        alice, title="Jour fixe", rrule="FREQ=WEEKLY", location="Raum 1", area_id=areas["Arbeit"]
    )
    listed = (
        await alice.get("/api/events", params={"from": "2026-09-14", "to": "2026-10-05"})
    ).json()
    await alice.delete(
        f"/api/events/{series['id']}",
        params={"scope": "this", "occurrence": listed[1]["recurrence_id"]},
    )
    await alice.patch(
        f"/api/events/{series['id']}",
        params={"scope": "this", "occurrence": listed[2]["recurrence_id"]},
        json={"title": "Jour fixe (Sonder)"},
    )
    await _event(alice, title="Privat-Termin", area_id=areas["Privat"], description="geheim")
    await _event(
        alice, title="Urlaub", all_day=True, start_date="2026-10-01", end_date="2026-10-03"
    )

    created = await alice.post("/api/feeds", json={"name": "Alles"})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["url"].startswith("https://testserver/api/feeds/")
    assert body["webcal_url"].startswith("webcal://testserver/api/feeds/")
    token = _token(body["url"])

    anonymous = await client_factory()
    r = await anonymous.get(f"/api/feeds/{token}.ics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/calendar")
    text = r.text.replace("\r\n ", "")
    for expected in (
        "BEGIN:VCALENDAR",
        "X-WR-CALNAME:ToDoch",
        "SUMMARY:Jour fixe",
        "RRULE:FREQ=WEEKLY",
        "EXDATE;TZID=Europe/Berlin",
        "RECURRENCE-ID;TZID=Europe/Berlin",
        "SUMMARY:Jour fixe (Sonder)",
        "LOCATION:Raum 1",
        "BEGIN:VTIMEZONE",
        "TZID:Europe/Berlin",
        "SUMMARY:Privat-Termin",
        "DTSTART;VALUE=DATE:20261001",
        "DTEND;VALUE=DATE:20261004",
    ):
        assert expected in text, expected

    again = await anonymous.get(
        f"/api/feeds/{token}.ics", headers={"If-None-Match": r.headers["etag"]}
    )
    assert again.status_code == 304

    feeds = (await alice.get("/api/feeds")).json()
    assert len(feeds) == 1
    assert "token" not in str(feeds[0]).lower()
    assert feeds[0]["last_used_at"] is not None


async def test_area_feed_with_busy_details(
    alice: AsyncClient, client_factory: ClientFactory
) -> None:
    areas = await _areas(alice)
    await _event(alice, title="Kunde Berger", area_id=areas["Arbeit"], location="Büro")
    await _event(alice, title="Privat-Termin", area_id=areas["Privat"])
    created = await alice.post(
        "/api/feeds", json={"name": "Für Kollegen", "area_id": areas["Arbeit"], "detail": "busy"}
    )
    feed = created.json()
    assert feed["feed"]["area_name"] == "Arbeit"
    text = (await (await client_factory()).get(f"/api/feeds/{_token(feed['url'])}.ics")).text
    assert "SUMMARY:Belegt" in text
    assert "Kunde Berger" not in text and "Büro" not in text
    assert "Privat-Termin" not in text
    assert "X-WR-CALNAME:ToDoch – Arbeit" in text


async def test_title_only_hides_details(alice: AsyncClient, client_factory: ClientFactory) -> None:
    await _event(alice, title="Arzt", location="Praxis", description="Befund mitbringen")
    feed = (await alice.post("/api/feeds", json={"name": "Titel", "detail": "title"})).json()
    text = (await (await client_factory()).get(f"/api/feeds/{_token(feed['url'])}.ics")).text
    assert "SUMMARY:Arzt" in text
    assert "Praxis" not in text and "Befund" not in text


async def test_revoked_and_invalid_tokens(
    alice: AsyncClient, client_factory: ClientFactory
) -> None:
    feed = (await alice.post("/api/feeds", json={"name": "Weg"})).json()
    anonymous = await client_factory()
    assert (await anonymous.get(f"/api/feeds/{_token(feed['url'])}.ics")).status_code == 200
    assert (await alice.delete(f"/api/feeds/{feed['feed']['id']}")).status_code == 204
    assert (await anonymous.get(f"/api/feeds/{_token(feed['url'])}.ics")).status_code == 404
    assert (await anonymous.get("/api/feeds/kurz.ics")).status_code == 404
    assert (await anonymous.get(f"/api/feeds/{'x' * 43}.ics")).status_code == 404
    assert (await alice.get("/api/feeds")).json() == []


async def test_feed_rate_limit(alice: AsyncClient, client_factory: ClientFactory) -> None:
    feed = (await alice.post("/api/feeds", json={"name": "Oft"})).json()
    anonymous = await client_factory()
    url = f"/api/feeds/{_token(feed['url'])}.ics"
    statuses = [(await anonymous.get(url)).status_code for _ in range(62)]
    assert statuses[0] == 200
    assert statuses[-1] == 429


async def test_feeds_are_private(alice: AsyncClient, bob: AsyncClient) -> None:
    areas = await _areas(alice)
    feed = (await alice.post("/api/feeds", json={"name": "Alice"})).json()
    assert (await bob.delete(f"/api/feeds/{feed['feed']['id']}")).status_code == 404
    assert (await bob.get("/api/feeds")).json() == []
    foreign = await bob.post("/api/feeds", json={"name": "x", "area_id": areas["Arbeit"]})
    assert foreign.status_code == 404
