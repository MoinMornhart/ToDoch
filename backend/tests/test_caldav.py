"""CalDAV ohne Einrichtung: finden, verbinden, in beide Richtungen abgleichen, sicher lesen."""

from typing import Any

import httpx
import pytest
from httpx import AsyncClient

from app.services import caldav
from app.services import calendar_sync as sync
from app.services import external_calendars as feeds
from tests.fake_caldav import PERSONAL, FakeCalDav

SERVER = "https://cloud.example.org"
CALENDAR = f"{SERVER}{PERSONAL}"
SUMMERFEST = (
    "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Nextcloud//DE\r\nBEGIN:VEVENT\r\n"
    "UID:sommerfest@nextcloud\r\nDTSTAMP:20260911T080000Z\r\n"
    "DTSTART;TZID=Europe/Berlin:20260926T180000\r\nDTEND;TZID=Europe/Berlin:20260926T220000\r\n"
    "SUMMARY:Sommerfest\r\nLOCATION:Garten & Terrasse\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
)
CHOIR = (
    "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Nextcloud//DE\r\nBEGIN:VEVENT\r\n"
    "UID:chor@nextcloud\r\nDTSTAMP:20260911T080000Z\r\n"
    "DTSTART:20260916T170000Z\r\nDTEND:20260916T183000Z\r\nRRULE:FREQ=WEEKLY;BYDAY=WE\r\n"
    "SUMMARY:Chor\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
)


@pytest.fixture
def nextcloud(monkeypatch: pytest.MonkeyPatch) -> FakeCalDav:
    fake = FakeCalDav()
    fake.add("sommerfest.ics", SUMMERFEST)
    fake.add("chor.ics", CHOIR)
    monkeypatch.setattr(sync, "TRANSPORT", httpx.MockTransport(fake.handler))
    return fake


def _login(**changes: str) -> dict[str, str]:
    return {"url": SERVER, "username": "alice", "password": "app-pass-123", **changes}


async def _events(client: AsyncClient) -> dict[str, dict[str, Any]]:
    found = await client.get("/api/events", params={"from": "2026-09-01", "to": "2026-12-31"})
    result: dict[str, dict[str, Any]] = {}
    for e in found.json():
        result.setdefault(e["title"], e)
    return result


async def test_discover_and_sync_with_nextcloud(alice: AsyncClient, nextcloud: FakeCalDav) -> None:
    areas = {a["name"]: a["id"] for a in (await alice.get("/api/areas")).json()}
    local = await alice.post(
        "/api/events",
        json={
            "title": "Zahnarzt",
            "start_date": "2026-10-01",
            "start_time": "10:00",
            "area_id": areas["Privat"],
        },
    )
    assert local.status_code == 201

    # Nur der Server – der Kalender wird gefunden, die Aufgabenliste nicht
    found = await alice.post("/api/calendar-sync/caldav/discover", json=_login())
    assert found.status_code == 200, found.text
    assert found.json() == [{"url": CALENDAR, "name": "Persönlich"}]
    wrong = await alice.post("/api/calendar-sync/caldav/discover", json=_login(password="falsch"))
    assert wrong.status_code == 422 and "abgelehnt" in wrong.json()["detail"]

    connected = await alice.post(
        "/api/calendar-sync/caldav",
        json={**_login(), "calendar_url": CALENDAR, "area_id": areas["Privat"]},
    )
    assert connected.status_code == 201, connected.text
    conn = connected.json()
    assert (conn["provider"], conn["server"], conn["account_email"], conn["last_error"]) == (
        "caldav",
        "cloud.example.org",
        "alice",
        None,
    )
    assert conn["event_count"] == 3
    assert "app-pass-123" not in connected.text

    events = await _events(alice)
    assert events["Sommerfest"]["start_local"] == "2026-09-26T18:00"
    detail = (await alice.get(f"/api/events/{events['Sommerfest']['event_id']}")).json()
    assert detail["location"] == "Garten & Terrasse"
    assert "Chor" in events and not events["Chor"]["read_only"]
    pushed = [data for path, data in nextcloud.objects.items() if b"SUMMARY:Zahnarzt" in data]
    assert len(pushed) == 1 and b"@todoch" in pushed[0]

    # Änderungen aus ToDoch – auch an übernommenen Terminen, deren UID bleibt
    await alice.patch(
        f"/api/events/{events['Sommerfest']['event_id']}", json={"title": "Sommerfest 2026"}
    )
    await alice.post(f"/api/calendar-sync/{conn['id']}/sync")
    summer = nextcloud.objects[f"{PERSONAL}sommerfest.ics"]
    assert b"SUMMARY:Sommerfest 2026" in summer
    assert b"UID:sommerfest@nextcloud" in summer

    # Änderungen und Löschungen in Nextcloud kommen an
    nextcloud.objects[f"{PERSONAL}chor.ics"] = CHOIR.replace(
        "SUMMARY:Chor", "SUMMARY:Chorprobe"
    ).encode()
    del nextcloud.objects[f"{PERSONAL}sommerfest.ics"]
    await alice.post(f"/api/calendar-sync/{conn['id']}/sync")
    events = await _events(alice)
    assert "Chorprobe" in events and "Chor" not in events
    assert "Sommerfest 2026" not in events

    # Löschen in ToDoch löscht in Nextcloud
    await alice.delete(f"/api/events/{events['Zahnarzt']['event_id']}")
    synced = (await alice.post(f"/api/calendar-sync/{conn['id']}/sync")).json()
    assert synced["last_error"] is None
    assert not any(b"SUMMARY:Zahnarzt" in data for data in nextcloud.objects.values())


async def test_plain_http_only_at_home(
    alice: AsyncClient, nextcloud: FakeCalDav, monkeypatch: pytest.MonkeyPatch
) -> None:
    public = await alice.post(
        "/api/calendar-sync/caldav/discover", json=_login(url="http://cloud.example.org")
    )
    assert public.status_code == 422
    assert "http://" in public.json()["detail"]

    async def blocked(host: str, port: int) -> list[str]:
        return ["169.254.169.254"]

    monkeypatch.setattr(feeds, "resolve", blocked)
    metadata = await alice.post("/api/calendar-sync/caldav/discover", json=_login())
    assert metadata.status_code == 422


def test_xml_bombs_are_refused() -> None:
    bomb = (
        b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">'
        b'<!ENTITY lol2 "&lol;&lol;&lol;">]><d:multistatus xmlns:d="DAV:">&lol2;</d:multistatus>'
    )
    with pytest.raises(sync.SyncError, match="nicht wie erwartet"):
        caldav.responses(bomb)
    with pytest.raises(sync.SyncError):
        caldav.responses(b"kein xml")
