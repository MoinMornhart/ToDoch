"""Zwei-Wege-Abgleich mit Google Kalender: holen, senden, löschen, verschieben, Fehler."""

from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from httpx import AsyncClient

from app.resources import Resources
from app.services import calendar_sync as sync
from app.services import mail_oauth as oauth
from tests.conftest import make_settings
from tests.fake_google_calendar import FakeGoogleCalendar


@pytest.fixture
def google(monkeypatch: pytest.MonkeyPatch, resources: Resources) -> FakeGoogleCalendar:
    settings = make_settings(
        google_client_id="123-abc.apps.googleusercontent.com", google_client_secret="GOCSPX-x"
    )
    object.__setattr__(resources, "settings", settings)
    fake = FakeGoogleCalendar()
    state: dict[str, Any] = {"fail": False}

    async def exchange(p: oauth.Provider, code: str, verifier: str, redirect: str) -> oauth.Tokens:
        assert "calendar.events" in p.scope
        return oauth.Tokens("access-1", "refresh-1", "alice@gmail.com")

    async def refresh(p: oauth.Provider, token: str) -> oauth.Tokens:
        if state["fail"]:
            raise oauth.OAuthError(oauth.EXPIRED)
        return oauth.Tokens("access-1", None, None)

    monkeypatch.setattr(oauth, "exchange_code", exchange)
    monkeypatch.setattr(oauth, "refresh_access", refresh)
    monkeypatch.setattr(sync, "TRANSPORT", httpx.MockTransport(fake.handler))
    fake.state = state  # type: ignore[attr-defined]
    return fake


async def _areas(client: AsyncClient) -> dict[str, str]:
    return {a["name"]: a["id"] for a in (await client.get("/api/areas")).json()}


async def _connect(client: AsyncClient, area_id: str) -> dict[str, Any]:
    started = await client.post("/api/calendar-sync/google/start", json={"area_id": area_id})
    assert started.status_code == 200, started.text
    url = urlsplit(started.json()["url"])
    params = {k: v[0] for k, v in parse_qs(url.query).items()}
    assert "https://www.googleapis.com/auth/calendar.events" in params["scope"]
    assert params["redirect_uri"] == "https://testserver/api/mail/oauth/google/callback"
    back = await client.get(
        "/api/mail/oauth/google/callback", params={"code": "c", "state": params["state"]}
    )
    assert back.status_code == 303
    assert back.headers["location"] == "/areas?calendar_connected=google"
    connections = (await client.get("/api/calendar-sync")).json()
    assert len(connections) == 1
    result: dict[str, Any] = connections[0]
    return result


async def _events(client: AsyncClient) -> dict[str, dict[str, Any]]:
    found = await client.get("/api/events", params={"from": "2026-09-01", "to": "2026-11-30"})
    result: dict[str, dict[str, Any]] = {}
    for e in found.json():
        result.setdefault(e["title"], e)  # bei Serien das erste Vorkommen
    return result


async def test_two_way_sync_with_google(alice: AsyncClient, google: FakeGoogleCalendar) -> None:
    areas = await _areas(alice)
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
    work = await alice.post(
        "/api/events",
        json={
            "title": "Nur Arbeit",
            "start_date": "2026-10-02",
            "start_time": "09:00",
            "area_id": areas["Arbeit"],
        },
    )
    assert work.status_code == 201
    weekly = google.add(
        summary="Team-Meeting",
        start={"dateTime": "2026-09-14T09:00:00+02:00", "timeZone": "Europe/Berlin"},
        end={"dateTime": "2026-09-14T09:30:00+02:00", "timeZone": "Europe/Berlin"},
        recurrence=["RRULE:FREQ=WEEKLY", "EXDATE;TZID=Europe/Berlin:20260921T090000"],
    )
    holiday = google.add(summary="Urlaub", start={"date": "2026-10-12"}, end={"date": "2026-10-17"})
    google.add(
        summary="Uralt",
        start={"dateTime": "2020-01-01T10:00:00Z"},
        end={"dateTime": "2020-01-01T11:00:00Z"},
    )

    conn = await _connect(alice, areas["Privat"])
    assert (conn["account_email"], conn["area_name"], conn["last_error"]) == (
        "alice@gmail.com",
        "Privat",
        None,
    )
    events = await _events(alice)
    assert {"Team-Meeting", "Urlaub", "Zahnarzt", "Nur Arbeit"} <= set(events)
    assert "Uralt" not in str(events)
    meeting = events["Team-Meeting"]
    assert meeting["start_local"] == "2026-09-14T09:00" and meeting["area_id"] == areas["Privat"]
    assert not meeting["read_only"]
    assert events["Urlaub"]["all_day"]
    series = await alice.get("/api/events", params={"from": "2026-09-20", "to": "2026-09-23"})
    assert series.json() == []  # Ausnahme vom 21.09. übernommen

    # ToDoch → Google: nur Termine des verbundenen Bereichs
    live = {e["summary"]: e for e in google.live().values()}
    assert live["Zahnarzt"]["start"] == {
        "dateTime": "2026-10-01T10:00:00",
        "timeZone": "Europe/Berlin",
    }
    assert "Nur Arbeit" not in live
    assert conn["event_count"] == 3

    # Nichts geändert → nichts gesendet
    google.requests.clear()
    await alice.post(f"/api/calendar-sync/{conn['id']}/sync")
    assert [m for m, _ in google.requests] == ["GET"]

    # Änderung in ToDoch landet bei Google
    zahnarzt = events["Zahnarzt"]
    await alice.patch(f"/api/events/{zahnarzt['event_id']}", json={"title": "Zahnarzt Dr. Berg"})
    await alice.post(f"/api/calendar-sync/{conn['id']}/sync")
    assert "Zahnarzt Dr. Berg" in {e["summary"] for e in google.live().values()}

    # Löschen in ToDoch löscht bei Google
    assert (await alice.delete(f"/api/events/{meeting['event_id']}")).status_code == 204
    await alice.post(f"/api/calendar-sync/{conn['id']}/sync")
    assert google.events[weekly]["status"] == "cancelled"

    # Änderungen und Löschungen bei Google kommen an
    google.change(holiday, summary="Urlaub Italien")
    zahnarzt_remote = next(k for k, v in google.live().items() if v["summary"].startswith("Zahn"))
    google.remove(zahnarzt_remote)
    await alice.post(f"/api/calendar-sync/{conn['id']}/sync")
    events = await _events(alice)
    assert "Urlaub Italien" in events and "Urlaub" not in events
    assert "Zahnarzt Dr. Berg" not in events

    # In einen anderen Bereich verschoben → bei Google entfernt, in ToDoch bleibt er
    italy = events["Urlaub Italien"]
    await alice.patch(f"/api/events/{italy['event_id']}", json={"area_id": areas["Arbeit"]})
    await alice.post(f"/api/calendar-sync/{conn['id']}/sync")
    assert google.events[holiday]["status"] == "cancelled"
    assert "Urlaub Italien" in await _events(alice)

    # Abgelaufener syncToken: alles neu holen, ohne Doppelte
    google.expire_sync_token = True
    synced = (await alice.post(f"/api/calendar-sync/{conn['id']}/sync")).json()
    assert synced["last_error"] is None
    october = await alice.get("/api/events", params={"from": "2026-10-01", "to": "2026-10-31"})
    assert [e["title"] for e in october.json()].count("Urlaub Italien") == 1


async def test_errors_and_disconnect(alice: AsyncClient, google: FakeGoogleCalendar) -> None:
    areas = await _areas(alice)
    conn = await _connect(alice, areas["Privat"])
    google.state["fail"] = True  # type: ignore[attr-defined]
    failed = (await alice.post(f"/api/calendar-sync/{conn['id']}/sync")).json()
    assert "neu verbinden" in failed["last_error"]
    english = await alice.get("/api/calendar-sync", headers={"Accept-Language": "en"})
    assert "reconnect" in english.json()[0]["last_error"]

    google.state["fail"] = False  # type: ignore[attr-defined]
    paused = await alice.patch(f"/api/calendar-sync/{conn['id']}", json={"enabled": False})
    assert paused.json()["enabled"] is False
    assert (await alice.delete(f"/api/calendar-sync/{conn['id']}")).status_code == 204
    assert (await alice.get("/api/calendar-sync")).json() == []


async def test_not_configured_and_foreign_area(alice: AsyncClient, bob: AsyncClient) -> None:
    areas = await _areas(alice)
    missing = await alice.post("/api/calendar-sync/google/start", json={"area_id": areas["Privat"]})
    assert missing.status_code == 409


async def test_foreign_area_is_rejected(
    alice: AsyncClient, bob: AsyncClient, google: FakeGoogleCalendar
) -> None:
    areas = await _areas(alice)
    stolen = await bob.post("/api/calendar-sync/google/start", json={"area_id": areas["Privat"]})
    assert stolen.status_code == 404


def test_google_mapping() -> None:
    fields = sync.fields_from_google(
        {
            "summary": "Serie",
            "start": {"date": "2026-10-12"},
            "end": {"date": "2026-10-13"},
            "recurrence": ["RRULE:FREQ=YEARLY", "EXDATE;VALUE=DATE:20271012", "RDATE:x"],
            "transparency": "transparent",
        },
        "Europe/Berlin",
    )
    assert fields["all_day"] and fields["rrule"] is not None and "YEARLY" in fields["rrule"]
    assert fields["exdates"] == [datetime(2027, 10, 12, tzinfo=UTC)]
    assert fields["transparency"] == "transparent"
    odd = sync.fields_from_google(
        {
            "start": {"dateTime": "2026-10-01T08:00:00Z", "timeZone": "Mars/Olympus"},
            "end": {"dateTime": "2026-10-01T07:00:00Z"},
            "recurrence": ["RRULE:FREQ=SECONDLY"],
        },
        "Europe/Berlin",
    )
    assert (odd["title"], odd["tzid"], odd["rrule"]) == ("–", "Europe/Berlin", None)
    assert odd["end_at"] == odd["start_at"]
