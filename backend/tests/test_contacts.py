"""Kontakte und Terminangaben: Vorschläge, Verknüpfung am Termin, ICS ohne interne Notizen."""

from datetime import date, timedelta
from typing import Any

from httpx import AsyncClient

NEXT_WEEK = (date.today() + timedelta(days=7)).isoformat()


async def _event(client: AsyncClient, **changes: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "title": "Beratung Berger",
        "start_date": NEXT_WEEK,
        "start_time": "10:00",
        "end_time": "11:00",
        "location": "Telefonisch",
        "description": "Vertrag besprechen, **Aktenzeichen 4711**",
        "channel": "phone",
        "agreed_with": "Frau Berger",
        **changes,
    }
    r = await client.post("/api/events", json=body)
    assert r.status_code == 201, r.text
    result: dict[str, Any] = r.json()["event"]
    return result


async def test_contact_suggestions(alice: AsyncClient) -> None:
    for name, company in (("Anna Berger", "Berger GmbH"), ("Bernd Adler", ""), ("Clara 50%", "")):
        created = await alice.post("/api/contacts", json={"name": name, "company": company})
        assert created.status_code == 201

    def names(result: list[dict[str, Any]]) -> list[str]:
        return [c["name"] for c in result]

    assert names((await alice.get("/api/contacts", params={"q": "ber"})).json()) == [
        "Anna Berger",
        "Bernd Adler",
    ]
    assert names((await alice.get("/api/contacts", params={"q": "gmbh"})).json()) == ["Anna Berger"]
    # Platzhalter werden wörtlich genommen
    assert names((await alice.get("/api/contacts", params={"q": "%"})).json()) == ["Clara 50%"]
    assert names((await alice.get("/api/contacts", params={"q": "_"})).json()) == []


async def test_contact_validation(alice: AsyncClient) -> None:
    assert (await alice.post("/api/contacts", json={"name": ""})).status_code == 422
    bad_phone = await alice.post("/api/contacts", json={"name": "X", "phone": "030<script>"})
    assert bad_phone.status_code == 422
    bad_mail = await alice.post("/api/contacts", json={"name": "X", "email": "keine-mail"})
    assert bad_mail.status_code == 422


async def test_event_contact_link_and_unlink(alice: AsyncClient) -> None:
    contact = (await alice.post("/api/contacts", json={"name": "Anna", "phone": "030 1"})).json()
    event = await _event(alice, contact_id=contact["id"])
    assert event["contact"]["phone"] == "030 1"
    assert event["channel"] == "phone"

    changed = await alice.patch(f"/api/events/{event['id']}", json={"channel": None})
    assert changed.json()["event"]["channel"] is None
    assert changed.json()["event"]["agreed_with"] == "Frau Berger"
    removed = await alice.patch(f"/api/events/{event['id']}", json={"contact_id": None})
    assert removed.json()["event"]["contact"] is None


async def test_deleting_contact_keeps_event(alice: AsyncClient) -> None:
    contact = (await alice.post("/api/contacts", json={"name": "Anna"})).json()
    event = await _event(alice, contact_id=contact["id"])
    assert (await alice.delete(f"/api/contacts/{contact['id']}")).status_code == 204
    loaded = (await alice.get(f"/api/events/{event['id']}")).json()
    assert loaded["contact"] is None
    assert loaded["title"] == "Beratung Berger"


async def test_foreign_contacts_are_invisible(alice: AsyncClient, bob: AsyncClient) -> None:
    contact = (await alice.post("/api/contacts", json={"name": "Geheimkontakt"})).json()
    assert (await bob.get("/api/contacts")).json() == []
    assert (await bob.get("/api/contacts", params={"q": "geheim"})).json() == []
    stolen = await bob.post(
        "/api/events",
        json={
            "title": "y",
            "start_date": NEXT_WEEK,
            "start_time": "09:00",
            "contact_id": contact["id"],
        },
    )
    assert stolen.status_code == 404
    own = await _event(bob)
    linked = await bob.patch(f"/api/events/{own['id']}", json={"contact_id": contact["id"]})
    assert linked.status_code == 404


async def test_event_in_other_timezone(alice: AsyncClient) -> None:
    event = await _event(
        alice,
        start_date="2026-09-21",
        start_time="09:00",
        end_time="09:30",
        tzid="America/New_York",
    )
    assert event["tzid"] == "America/New_York"
    # 09:00 in New York (EDT, UTC−4) = 15:00 in Berlin (CEST)
    assert event["start_time"] == "15:00:00"
    bad = await alice.post(
        "/api/events",
        json={"title": "x", "start_date": NEXT_WEEK, "start_time": "09:00", "tzid": "Mars/Olympus"},
    )
    assert bad.status_code == 422


async def test_single_event_ics_hides_notes_by_default(alice: AsyncClient) -> None:
    event = await _event(alice)
    public = await alice.get(f"/api/events/{event['id']}/ics")
    assert public.status_code == 200
    assert public.headers["content-type"].startswith("text/calendar")
    assert "attachment" in public.headers["content-disposition"]
    assert "SUMMARY:Beratung Berger" in public.text
    assert "Aktenzeichen" not in public.text
    full = await alice.get(f"/api/events/{event['id']}/ics", params={"detail": "full"})
    assert "Aktenzeichen" in full.text


async def test_invalid_channel_is_rejected(alice: AsyncClient) -> None:
    r = await alice.post(
        "/api/events",
        json={
            "title": "x",
            "start_date": NEXT_WEEK,
            "start_time": "09:00",
            "channel": "brieftaube",
        },
    )
    assert r.status_code == 422
