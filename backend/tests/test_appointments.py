"""Telefontermine: Kontakt, Termin und Folgeaufgabe in einem Schritt; Kontaktvorschläge; ICS."""

from datetime import date, timedelta
from typing import Any

from httpx import AsyncClient

NEXT_WEEK = (date.today() + timedelta(days=7)).isoformat()


def _appointment(**changes: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "contact": {
            "name": "Anna Berger",
            "company": "Berger GmbH",
            "phone": "+49 (0)30 123-456",
            "email": "anna@berger.example",
            "address": "Hauptstraße 1\n10115 Berlin",
        },
        "event": {
            "title": "Beratung Berger",
            "start_date": NEXT_WEEK,
            "start_time": "10:00",
            "end_time": "11:00",
            "location": "Telefonisch",
            "description": "Vertrag besprechen, **Aktenzeichen 4711**",
            "channel": "phone",
            "agreed_on": date.today().isoformat(),
            "agreed_with": "Frau Berger",
            "priority": 2,
            "tags": ["kunde"],
            "reminders": [60],
        },
        "follow_up": {"title": "Unterlagen vorbereiten", "days_before": 2},
    }
    body.update(changes)
    return body


async def test_appointment_creates_contact_event_and_task(alice: AsyncClient) -> None:
    r = await alice.post("/api/appointments", json=_appointment())
    assert r.status_code == 201, r.text
    data = r.json()
    event, task, contact = data["event"], data["task"], data["contact"]

    assert event["source"] == "form"
    assert event["channel"] == "phone"
    assert event["agreed_with"] == "Frau Berger"
    assert event["priority"] == 2
    assert event["contact"]["id"] == contact["id"]
    assert contact["use_count"] == 1
    assert contact["phone"] == "+49 (0)30 123-456"

    assert task["event_id"] == event["id"]
    assert task["due_date"] == (date.today() + timedelta(days=5)).isoformat()
    assert task["tags"] == ["kunde"]
    assert task["area_id"] == event["area_id"]

    loaded = (await alice.get(f"/api/events/{event['id']}")).json()
    assert [t["title"] for t in loaded["tasks"]] == ["Unterlagen vorbereiten"]
    assert loaded["contact"]["name"] == "Anna Berger"

    # Notizen sind durchsuchbar
    found = (await alice.get("/api/search", params={"q": "aktenzeichen"})).json()
    assert [e["id"] for e in found["events"]] == [event["id"]]


async def test_follow_up_is_never_due_in_the_past(alice: AsyncClient) -> None:
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    body = _appointment(follow_up={"title": "Vorbereiten", "days_before": 7})
    body["event"]["start_date"] = tomorrow
    task = (await alice.post("/api/appointments", json=body)).json()["task"]
    assert task["due_date"] == date.today().isoformat()


async def test_existing_contact_is_reused_and_updated(alice: AsyncClient) -> None:
    first = (await alice.post("/api/appointments", json=_appointment(follow_up=None))).json()
    contact_id = first["contact"]["id"]
    assert first["task"] is None

    second = await alice.post(
        "/api/appointments",
        json=_appointment(
            contact_id=contact_id,
            contact={"name": "Anna Berger", "phone": "030 999"},
            follow_up=None,
        ),
    )
    assert second.status_code == 201
    assert second.json()["contact"]["id"] == contact_id
    contact = (await alice.get(f"/api/contacts/{contact_id}")).json()
    assert contact["use_count"] == 2
    assert contact["phone"] == "030 999"
    assert contact["company"] == "Berger GmbH"  # nicht mitgeschickt → unverändert
    assert len((await alice.get("/api/contacts")).json()) == 1


async def test_appointment_without_contact(alice: AsyncClient) -> None:
    r = await alice.post("/api/appointments", json=_appointment(contact=None, follow_up=None))
    assert r.status_code == 201
    assert r.json()["contact"] is None
    assert r.json()["event"]["contact"] is None


async def test_contact_suggestions(alice: AsyncClient) -> None:
    for name, company in (("Anna Berger", "Berger GmbH"), ("Bernd Adler", ""), ("Clara 50%", "")):
        assert (
            await alice.post("/api/contacts", json={"name": name, "company": company})
        ).status_code == 201

    def names(result: list[dict[str, Any]]) -> list[str]:
        return [c["name"] for c in result]

    assert names((await alice.get("/api/contacts", params={"q": "ber"})).json()) == [
        "Anna Berger",
        "Bernd Adler",
    ]
    assert names((await alice.get("/api/contacts", params={"q": "gmbh"})).json()) == ["Anna Berger"]
    assert names((await alice.get("/api/contacts", params={"q": "anna ber"})).json()) == [
        "Anna Berger"
    ]
    # Platzhalter werden wörtlich genommen
    assert names((await alice.get("/api/contacts", params={"q": "%"})).json()) == ["Clara 50%"]
    assert names((await alice.get("/api/contacts", params={"q": "_"})).json()) == []


async def test_contact_validation(alice: AsyncClient) -> None:
    assert (await alice.post("/api/contacts", json={"name": ""})).status_code == 422
    assert (
        await alice.post("/api/contacts", json={"name": "X", "phone": "030<script>"})
    ).status_code == 422
    assert (
        await alice.post("/api/contacts", json={"name": "X", "email": "keine-mail"})
    ).status_code == 422


async def test_foreign_contacts_are_invisible(alice: AsyncClient, bob: AsyncClient) -> None:
    contact = (await alice.post("/api/contacts", json={"name": "Geheimkontakt"})).json()
    assert (await bob.get("/api/contacts")).json() == []
    assert (await bob.get("/api/contacts", params={"q": "geheim"})).json() == []
    stolen = await bob.post(
        "/api/appointments", json=_appointment(contact_id=contact["id"], contact=None)
    )
    assert stolen.status_code == 404
    event = (
        await bob.post(
            "/api/events", json={"title": "x", "start_date": NEXT_WEEK, "start_time": "09:00"}
        )
    ).json()["event"]
    linked = await bob.patch(f"/api/events/{event['id']}", json={"contact_id": contact["id"]})
    assert linked.status_code == 404
    created = await bob.post(
        "/api/events",
        json={
            "title": "y",
            "start_date": NEXT_WEEK,
            "start_time": "09:00",
            "contact_id": contact["id"],
        },
    )
    assert created.status_code == 404


async def test_event_contact_can_be_changed_and_removed(alice: AsyncClient) -> None:
    data = (await alice.post("/api/appointments", json=_appointment(follow_up=None))).json()
    event_id = data["event"]["id"]
    other = (await alice.post("/api/contacts", json={"name": "Carl"})).json()

    changed = await alice.patch(
        f"/api/events/{event_id}", json={"contact_id": other["id"], "channel": None}
    )
    assert changed.json()["event"]["contact"]["name"] == "Carl"
    assert changed.json()["event"]["channel"] is None
    assert changed.json()["event"]["agreed_with"] == "Frau Berger"

    removed = await alice.patch(f"/api/events/{event_id}", json={"contact_id": None})
    assert removed.json()["event"]["contact"] is None


async def test_deleting_contact_keeps_event(alice: AsyncClient) -> None:
    data = (await alice.post("/api/appointments", json=_appointment())).json()
    assert (await alice.delete(f"/api/contacts/{data['contact']['id']}")).status_code == 204
    event = (await alice.get(f"/api/events/{data['event']['id']}")).json()
    assert event["contact"] is None
    assert event["title"] == "Beratung Berger"


async def test_deleting_event_keeps_follow_up_task(alice: AsyncClient) -> None:
    data = (await alice.post("/api/appointments", json=_appointment())).json()
    assert (await alice.delete(f"/api/events/{data['event']['id']}")).status_code == 204
    task = (await alice.get(f"/api/tasks/{data['task']['id']}")).json()
    assert task["event_id"] is None


async def test_appointment_in_other_timezone(alice: AsyncClient) -> None:
    body = _appointment(follow_up=None)
    body["event"].update(start_date="2026-09-21", start_time="09:00", end_time="09:30")
    body["event"]["tzid"] = "America/New_York"
    event = (await alice.post("/api/appointments", json=body)).json()["event"]
    assert event["tzid"] == "America/New_York"
    # 09:00 in New York (EDT, UTC−4) = 15:00 in Berlin (CEST)
    assert event["start_time"] == "15:00:00"

    body["event"]["tzid"] = "Mars/Olympus"
    assert (await alice.post("/api/appointments", json=body)).status_code == 422


async def test_single_event_ics_hides_notes_by_default(alice: AsyncClient) -> None:
    event = (await alice.post("/api/appointments", json=_appointment())).json()["event"]
    public = await alice.get(f"/api/events/{event['id']}/ics")
    assert public.status_code == 200
    assert public.headers["content-type"].startswith("text/calendar")
    assert "attachment" in public.headers["content-disposition"]
    assert "SUMMARY:Beratung Berger" in public.text
    assert "LOCATION:Telefonisch" in public.text
    assert "Aktenzeichen" not in public.text

    full = await alice.get(f"/api/events/{event['id']}/ics", params={"detail": "full"})
    assert "Aktenzeichen" in full.text


async def test_invalid_channel_is_rejected(alice: AsyncClient) -> None:
    body = _appointment()
    body["event"]["channel"] = "brieftaube"
    assert (await alice.post("/api/appointments", json=body)).status_code == 422
