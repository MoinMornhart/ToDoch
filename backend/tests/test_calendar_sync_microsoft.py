"""Zwei-Wege-Abgleich mit Outlook (Microsoft Graph): volle Liste, Serienmuster, UTC-Zeiten."""

from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from httpx import AsyncClient

from app.models import Event
from app.resources import Resources
from app.services import calendar_sync as sync
from app.services import mail_oauth as oauth
from app.services.event_recurrence import normalize_event_rule
from tests.conftest import make_settings
from tests.fake_graph_calendar import FakeGraphCalendar


@pytest.fixture
def outlook(monkeypatch: pytest.MonkeyPatch, resources: Resources) -> FakeGraphCalendar:
    settings = make_settings(
        microsoft_client_id="00000000-1111-2222-3333-444444444444",
        microsoft_client_secret="ms~geheim",
    )
    object.__setattr__(resources, "settings", settings)
    fake = FakeGraphCalendar()

    async def exchange(p: oauth.Provider, code: str, verifier: str, redirect: str) -> oauth.Tokens:
        assert "Calendars.ReadWrite" in p.scope
        return oauth.Tokens("access-1", "refresh-1", "alice@outlook.de")

    async def refresh(p: oauth.Provider, token: str) -> oauth.Tokens:
        assert "Calendars.ReadWrite" in p.scope
        return oauth.Tokens("access-1", None, None)

    monkeypatch.setattr(oauth, "exchange_code", exchange)
    monkeypatch.setattr(oauth, "refresh_access", refresh)
    monkeypatch.setattr(sync, "TRANSPORT", httpx.MockTransport(fake.handler))
    return fake


async def _events(client: AsyncClient) -> dict[str, dict[str, Any]]:
    found = await client.get("/api/events", params={"from": "2026-09-01", "to": "2026-12-31"})
    result: dict[str, dict[str, Any]] = {}
    for e in found.json():
        result.setdefault(e["title"], e)
    return result


async def test_two_way_sync_with_outlook(alice: AsyncClient, outlook: FakeGraphCalendar) -> None:
    areas = {a["name"]: a["id"] for a in (await alice.get("/api/areas")).json()}
    for body in (
        {"title": "Zahnarzt", "start_date": "2026-10-01", "start_time": "10:00"},
        {
            "title": "Sport",
            "start_date": "2026-09-15",
            "start_time": "18:00",
            "rrule": "FREQ=WEEKLY;BYDAY=TU,TH",
        },
    ):
        created = await alice.post("/api/events", json={**body, "area_id": areas["Privat"]})
        assert created.status_code == 201, created.text
    jour = outlook.add(
        subject="Jour fixe",
        body={"contentType": "text", "content": "Agenda im Wiki\r\n"},
        location={"displayName": "Raum 3"},
        start={"dateTime": "2026-10-05T10:00:00", "timeZone": "Europe/Berlin"},
        end={"dateTime": "2026-10-05T11:00:00", "timeZone": "Europe/Berlin"},
        recurrence={
            "pattern": {
                "type": "relativeMonthly",
                "interval": 1,
                "daysOfWeek": ["monday"],
                "index": "first",
            },
            "range": {"type": "noEnd", "startDate": "2026-10-05"},
        },
        showAs="busy",
    )
    fair = outlook.add(
        subject="Messe",
        isAllDay=True,
        start={"dateTime": "2026-10-20T00:00:00", "timeZone": "Europe/Berlin"},
        end={"dateTime": "2026-10-23T00:00:00", "timeZone": "Europe/Berlin"},
        showAs="free",
    )

    started = await alice.post(
        "/api/calendar-sync/microsoft/start", json={"area_id": areas["Privat"]}
    )
    assert started.status_code == 200, started.text
    params = {k: v[0] for k, v in parse_qs(urlsplit(started.json()["url"]).query).items()}
    assert "https://graph.microsoft.com/Calendars.ReadWrite" in params["scope"]
    back = await alice.get(
        "/api/mail/oauth/microsoft/callback", params={"code": "c", "state": params["state"]}
    )
    assert back.headers["location"] == "/areas?calendar_connected=microsoft"
    conn = (await alice.get("/api/calendar-sync")).json()[0]
    assert (conn["provider"], conn["account_email"], conn["last_error"]) == (
        "microsoft",
        "alice@outlook.de",
        None,
    )

    events = await _events(alice)
    assert events["Jour fixe"]["start_local"] == "2026-10-05T10:00"
    detail = (await alice.get(f"/api/events/{events['Jour fixe']['event_id']}")).json()
    assert detail["rrule"] == "FREQ=MONTHLY;BYDAY=1MO"
    assert (detail["location"], detail["description"]) == ("Raum 3", "Agenda im Wiki")
    fair_event = (await alice.get(f"/api/events/{events['Messe']['event_id']}")).json()
    assert fair_event["all_day"] and fair_event["start_date"] == "2026-10-20"
    assert fair_event["end_date"] == "2026-10-22"
    assert fair_event["transparency"] == "transparent"

    remote = {e["subject"]: e for e in outlook.events.values()}
    assert remote["Zahnarzt"]["start"] == {
        "dateTime": "2026-10-01T10:00:00",
        "timeZone": "Europe/Berlin",
    }
    assert remote["Sport"]["recurrence"]["pattern"] == {
        "interval": 1,
        "firstDayOfWeek": "monday",
        "type": "weekly",
        "daysOfWeek": ["tuesday", "thursday"],
    }
    assert remote["Sport"]["recurrence"]["range"]["type"] == "noEnd"

    # Änderung in ToDoch wird nicht von der vollständigen Liste überschrieben
    zahnarzt = events["Zahnarzt"]
    await alice.patch(f"/api/events/{zahnarzt['event_id']}", json={"title": "Zahnarzt Dr. Berg"})
    await alice.post(f"/api/calendar-sync/{conn['id']}/sync")
    assert "Zahnarzt Dr. Berg" in await _events(alice)
    assert "Zahnarzt Dr. Berg" in {e["subject"] for e in outlook.events.values()}

    # Änderung und Löschung in Outlook kommen an
    outlook.events[jour]["subject"] = "Jour fixe (neu)"
    del outlook.events[fair]
    await alice.post(f"/api/calendar-sync/{conn['id']}/sync")
    events = await _events(alice)
    assert "Jour fixe (neu)" in events and "Jour fixe" not in events
    assert "Messe" not in events

    # Löschen in ToDoch löscht in Outlook
    assert (await alice.delete(f"/api/events/{events['Sport']['event_id']}")).status_code == 204
    synced = (await alice.post(f"/api/calendar-sync/{conn['id']}/sync")).json()
    assert synced["last_error"] is None
    assert "Sport" not in {e["subject"] for e in outlook.events.values()}

    # Nichts geändert → nur lesen
    outlook.requests.clear()
    await alice.post(f"/api/calendar-sync/{conn['id']}/sync")
    assert {m for m, _ in outlook.requests} == {"GET"}


def _event(rule: str, **changes: Any) -> Event:
    values: dict[str, Any] = {
        "title": "x",
        "start_at": datetime(2026, 10, 5, 8, 0, tzinfo=UTC),
        "end_at": datetime(2026, 10, 5, 9, 0, tzinfo=UTC),
        "all_day": False,
        "tzid": "Europe/Berlin",
        "rrule": rule,
        **changes,
    }
    return Event(**values)


@pytest.mark.parametrize(
    "rule",
    [
        "FREQ=DAILY;INTERVAL=2",
        "FREQ=WEEKLY;BYDAY=MO,FR;COUNT=10",
        "FREQ=MONTHLY;BYMONTHDAY=5",
        "FREQ=MONTHLY;BYDAY=-1FR",
        "FREQ=YEARLY;BYMONTH=10;BYMONTHDAY=5",
        "FREQ=YEARLY;BYMONTH=11;BYDAY=4TH;UNTIL=20301231",
    ],
)
def test_rules_survive_the_round_trip(rule: str) -> None:
    graph = sync.graph_recurrence(_event(rule))
    assert graph is not None
    assert sync.rrule_from_graph(graph) == normalize_event_rule(rule)


def test_rules_outlook_cannot_express() -> None:
    assert sync.graph_recurrence(_event("FREQ=MONTHLY;BYDAY=MO")) is None
    assert sync.rrule_from_graph({"pattern": {"type": "hourly"}}) is None
    assert sync.rrule_from_graph("kaputt") is None
    weekly = sync.graph_recurrence(_event("FREQ=WEEKLY"))
    assert weekly is not None and weekly["pattern"]["daysOfWeek"] == ["monday"]
