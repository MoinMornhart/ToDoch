"""Abonnierte Kalender (z. B. Streamo): Abruf mit SSRF-Schutz, Zerlegen, Abgleich, nur lesbar."""

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from httpx import AsyncClient

from app.services import external_calendars as feeds
from tests.conftest import ClientFactory

# Vor dem Autouse-Fixture in conftest gemerkt, das den Abruf im Test sonst ersetzt
REAL_FETCH = feeds.fetch_ics
REAL_CHECK = feeds.check_url

# So liefert Streamo seinen Kalender: schwebende Uhrzeiten, ganztägige Termine, TRANSPARENT
STREAMO = """BEGIN:VCALENDAR\r
VERSION:2.0\r
PRODID:-//Streamo//Kalender//DE\r
X-WR-CALNAME:Streamo\r
BEGIN:VEVENT\r
UID:plan-42@streamo\r
DTSTAMP:20260911T120000Z\r
DTSTART:20260918T201500\r
DTEND:20260918T220500\r
SUMMARY:📺 Dune: Part Two\r
DESCRIPTION:Du hast dir vorgenommen\\, diesen Film zu sehen.\r
URL:http://streamo.local:3000/library\r
TRANSP:TRANSPARENT\r
END:VEVENT\r
BEGIN:VEVENT\r
UID:ep-7-2-3@streamo\r
DTSTAMP:20260911T120000Z\r
DTSTART;VALUE=DATE:20260920\r
DTEND;VALUE=DATE:20260921\r
SUMMARY:🎬 Severance S02E03\r
TRANSP:TRANSPARENT\r
END:VEVENT\r
END:VCALENDAR\r
"""

GENERIC = """BEGIN:VCALENDAR\r
VERSION:2.0\r
BEGIN:VEVENT\r
UID:weekly@example\r
DTSTART;TZID=America/New_York:20260914T090000\r
DTEND;TZID=America/New_York:20260914T093000\r
RRULE:FREQ=WEEKLY;COUNT=3\r
EXDATE;TZID=America/New_York:20260921T090000\r
SUMMARY:Standup\r
STATUS:TENTATIVE\r
END:VEVENT\r
BEGIN:VEVENT\r
UID:weekly@example\r
RECURRENCE-ID;TZID=America/New_York:20260928T090000\r
DTSTART;TZID=America/New_York:20260928T100000\r
SUMMARY:Standup (verschoben)\r
END:VEVENT\r
BEGIN:VEVENT\r
UID:odd@example\r
DTSTART:20260915T080000Z\r
DURATION:PT45M\r
RRULE:FREQ=SECONDLY\r
SUMMARY:Unbekannte Regel\r
URL:javascript:alert(1)\r
END:VEVENT\r
BEGIN:VEVENT\r
DTSTART:20260915T080000Z\r
SUMMARY:Ohne UID\r
END:VEVENT\r
END:VCALENDAR\r
"""


def test_parse_streamo_feed() -> None:
    parsed = {p.uid: p for p in feeds.parse_ics(STREAMO.encode(), "Europe/Berlin")}
    film = parsed["plan-42@streamo"]
    assert film.title == "📺 Dune: Part Two"
    assert film.start_at == datetime(2026, 9, 18, 18, 15, tzinfo=UTC)  # 20:15 Berlin (MESZ)
    assert film.end_at == datetime(2026, 9, 18, 20, 5, tzinfo=UTC)
    assert film.transparency == "transparent"
    assert film.description == "Du hast dir vorgenommen, diesen Film zu sehen."
    assert not film.all_day
    episode = parsed["ep-7-2-3@streamo"]
    assert episode.all_day
    assert episode.start_at == datetime(2026, 9, 20, tzinfo=UTC)
    assert episode.end_at == datetime(2026, 9, 21, tzinfo=UTC)


def test_parse_generic_feed() -> None:
    parsed = {p.uid: p for p in feeds.parse_ics(GENERIC.encode(), "Europe/Berlin")}
    assert set(parsed) == {"weekly@example", "odd@example"}  # ohne UID und Ausnahme übersprungen
    weekly = parsed["weekly@example"]
    assert weekly.rrule is not None and "FREQ=WEEKLY" in weekly.rrule
    assert weekly.start_at == datetime(2026, 9, 14, 13, 0, tzinfo=UTC)
    assert weekly.exdates == [datetime(2026, 9, 21, 13, 0, tzinfo=UTC)]
    assert weekly.status == "tentative"
    odd = parsed["odd@example"]
    assert odd.rrule is None  # unbekannte Regel → nur das erste Vorkommen
    assert (odd.end_at - odd.start_at).total_seconds() == 45 * 60
    assert odd.url == ""  # nur http(s)-Links


def test_invalid_file() -> None:
    with pytest.raises(feeds.FeedError):
        feeds.parse_ics(b"<html>kein Kalender</html>", "Europe/Berlin")


@pytest.mark.parametrize(
    ("url", "addresses", "admin", "ok"),
    [
        ("https://calendar.example/a.ics", ["93.184.216.34"], False, True),
        ("http://192.168.178.50:3000/api/public/calendar/x.ics", ["192.168.178.50"], True, True),
        ("http://192.168.178.50:3000/x.ics", ["192.168.178.50"], False, False),
        ("http://localhost/x.ics", ["127.0.0.1"], True, False),
        ("http://metadata/x.ics", ["169.254.169.254"], True, False),
        ("http://[::ffff:127.0.0.1]/x.ics", ["::ffff:127.0.0.1"], True, False),
        # NetBird/Tailscale/CGNAT gehören zum eigenen Netz, nicht zum Internet
        ("http://peer.netbird.cloud/x.ics", ["100.100.1.1"], False, False),
        ("http://peer.netbird.cloud/x.ics", ["100.100.1.1"], True, True),
        ("ftp://calendar.example/a.ics", ["93.184.216.34"], True, False),
        ("https://", [], True, False),
    ],
)
async def test_check_url(
    monkeypatch: pytest.MonkeyPatch, url: str, addresses: list[str], admin: bool, ok: bool
) -> None:
    async def fake_resolve(host: str, port: int) -> list[str]:
        return addresses

    monkeypatch.setattr(feeds, "resolve", fake_resolve)
    if ok:
        assert await REAL_CHECK(url, allow_private=admin)
    else:
        with pytest.raises(feeds.FeedError):
            await REAL_CHECK(url, allow_private=admin)


async def test_fetch_blocks_redirect_to_internal_address(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_resolve(host: str, port: int) -> list[str]:
        return ["127.0.0.1"] if host == "127.0.0.1" else ["93.184.216.34"]

    monkeypatch.setattr(feeds, "resolve", fake_resolve)
    monkeypatch.setattr(feeds, "check_url", REAL_CHECK)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "calendar.example":
            return httpx.Response(302, headers={"location": "http://127.0.0.1:6379/"})
        return httpx.Response(200, text=STREAMO)

    with pytest.raises(feeds.FeedError, match="nicht erlaubt"):
        await REAL_FETCH(
            "https://calendar.example/a.ics",
            allow_private=True,
            transport=httpx.MockTransport(handler),
        )


async def test_fetch_limits_and_etag(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_resolve(host: str, port: int) -> list[str]:
        return ["93.184.216.34"]

    monkeypatch.setattr(feeds, "resolve", fake_resolve)
    monkeypatch.setattr(feeds, "check_url", REAL_CHECK)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.headers.get("if-none-match") == '"v1"':
            return httpx.Response(304)
        if request.url.path == "/big.ics":
            return httpx.Response(200, content=b"x" * (feeds.MAX_BYTES + 1))
        if request.url.path == "/missing.ics":
            return httpx.Response(404)
        return httpx.Response(200, text=STREAMO, headers={"etag": '"v1"'})

    transport = httpx.MockTransport(handler)
    body, etag = await REAL_FETCH(
        "https://c.example/a.ics", allow_private=False, transport=transport
    )
    assert body is not None and etag == '"v1"'
    unchanged = await REAL_FETCH(
        "https://c.example/a.ics", allow_private=False, etag='"v1"', transport=transport
    )
    assert unchanged == (None, '"v1"')
    with pytest.raises(feeds.FeedError, match="zu groß"):
        await REAL_FETCH("https://c.example/big.ics", allow_private=False, transport=transport)
    with pytest.raises(feeds.FeedError, match="Status 404"):
        await REAL_FETCH("https://c.example/missing.ics", allow_private=False, transport=transport)


@pytest.fixture
def feed(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Steuerbarer Kalender statt echtem Abruf."""
    state: dict[str, Any] = {"body": STREAMO.encode(), "error": None, "calls": 0}

    async def fake_fetch(
        url: str, *, allow_private: bool, etag: str | None = None, **_: Any
    ) -> tuple[bytes | None, str | None]:
        state["calls"] += 1
        state["url"] = url
        if state["error"]:
            raise feeds.FeedError(state["error"])
        return state["body"], None

    monkeypatch.setattr(feeds, "fetch_ics", fake_fetch)
    return state


async def _add(client: AsyncClient, **changes: Any) -> dict[str, Any]:
    areas = (await client.get("/api/areas")).json()
    body = {
        "name": "Streamo",
        "url": "webcal://streamo.example/api/public/calendar/geheim.ics",
        "area_id": areas[1]["id"],
        **changes,
    }
    r = await client.post("/api/calendars", json=body)
    assert r.status_code == 201, r.text
    result: dict[str, Any] = r.json()
    return result


async def _events(client: AsyncClient) -> list[dict[str, Any]]:
    r = await client.get("/api/events", params={"from": "2026-09-01", "to": "2026-10-01"})
    result: list[dict[str, Any]] = r.json()
    return result


async def test_subscribe_streamo(alice: AsyncClient, feed: dict[str, Any]) -> None:
    calendar = await _add(alice)
    assert calendar["event_count"] == 2
    assert calendar["last_error"] is None
    assert calendar["host"] == "streamo.example"
    assert "geheim" not in str(calendar)  # die Adresse mit Token wird nie zurückgegeben
    assert feed["url"] == "https://streamo.example/api/public/calendar/geheim.ics"

    events = await _events(alice)
    titles = {e["title"] for e in events}
    assert titles == {"📺 Dune: Part Two", "🎬 Severance S02E03"}
    assert all(e["read_only"] and e["area_id"] == calendar["area_id"] for e in events)
    film = next(e for e in events if e["title"].startswith("📺"))
    assert film["start_local"] == "2026-09-18T20:15"

    detail = (await alice.get(f"/api/events/{film['event_id']}")).json()
    assert detail["read_only"] is True
    assert detail["calendar_name"] == "Streamo"
    blocked = await alice.patch(f"/api/events/{film['event_id']}", json={"title": "x"})
    assert blocked.status_code == 409
    assert (await alice.delete(f"/api/events/{film['event_id']}")).status_code == 409


async def test_resync_updates_adds_and_removes(alice: AsyncClient, feed: dict[str, Any]) -> None:
    calendar = await _add(alice)
    feed["body"] = (
        STREAMO.replace("Dune: Part Two", "Dune: Messiah")
        .replace("UID:ep-7-2-3@streamo", "UID:ep-7-2-4@streamo")
        .encode()
    )
    synced = (await alice.post(f"/api/calendars/{calendar['id']}/sync")).json()
    assert synced["event_count"] == 2
    events = await _events(alice)
    assert {e["title"] for e in events} == {"📺 Dune: Messiah", "🎬 Severance S02E03"}
    assert len({e["event_id"] for e in events}) == 2


async def test_errors_keep_events(alice: AsyncClient, feed: dict[str, Any]) -> None:
    calendar = await _add(alice)
    feed["error"] = "Der Kalender ist nicht erreichbar."
    synced = (await alice.post(f"/api/calendars/{calendar['id']}/sync")).json()
    assert synced["last_error"] == "Der Kalender ist nicht erreichbar."
    english = await alice.get("/api/calendars", headers={"Accept-Language": "en"})
    assert english.json()[0]["last_error"] == "The calendar cannot be reached."
    assert len(await _events(alice)) == 2


async def test_move_delete_and_limits(alice: AsyncClient, feed: dict[str, Any]) -> None:
    calendar = await _add(alice)
    areas = (await alice.get("/api/areas")).json()
    moved = await alice.patch(f"/api/calendars/{calendar['id']}", json={"area_id": areas[0]["id"]})
    assert moved.json()["area_id"] == areas[0]["id"]
    assert all(e["area_id"] == areas[0]["id"] for e in await _events(alice))

    assert (await alice.delete(f"/api/calendars/{calendar['id']}")).status_code == 204
    assert await _events(alice) == []
    assert (await alice.get("/api/calendars")).json() == []


async def test_invalid_address_is_rejected(alice: AsyncClient, feed: dict[str, Any]) -> None:
    areas = (await alice.get("/api/areas")).json()
    r = await alice.post(
        "/api/calendars",
        json={"name": "x", "url": "ftp://example.org/a.ics", "area_id": areas[0]["id"]},
    )
    assert r.status_code == 422


async def test_calendars_of_others_are_invisible(
    alice: AsyncClient, bob: AsyncClient, feed: dict[str, Any]
) -> None:
    calendar = await _add(alice)
    assert (await bob.get("/api/calendars")).json() == []
    assert (await bob.post(f"/api/calendars/{calendar['id']}/sync")).status_code == 404
    bob_events = await bob.get("/api/events", params={"from": "2026-09-01", "to": "2026-10-01"})
    assert bob_events.json() == []


async def test_worker_syncs_due_calendars(
    alice: AsyncClient, feed: dict[str, Any], client_factory: ClientFactory, resources: Any
) -> None:
    await _add(alice)
    calls = feed["calls"]
    async with resources.sessionmaker() as db:
        assert await feeds.sync_due_calendars(db, resources.crypto) == 0  # gerade erst abgeglichen
        from sqlalchemy import update

        from app.models import ExternalCalendar

        await db.execute(update(ExternalCalendar).values(last_synced_at=None))
        await db.commit()
        assert await feeds.sync_due_calendars(db, resources.crypto) == 1
    assert feed["calls"] == calls + 1
