"""Terminvorschläge aus Mails: Einladungen, Datum im Text, Bestätigung per API."""

from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.utils import format_datetime
from typing import Any

from httpx import AsyncClient

from app.services import mail
from app.services.mail_suggestions import detect
from tests.fake_imap import FakeMailbox, make_mail

NOW = datetime(2026, 9, 11, 8, 0, tzinfo=UTC)  # Freitag, 10:00 in Berlin
TZ = "Europe/Berlin"
ACCOUNT = {"email": "alice@example.org", "password": "imap-geheim", "imap_host": "imap.example.org"}
INVITE = (
    "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Test//DE\r\nMETHOD:REQUEST\r\n"
    "BEGIN:VEVENT\r\nUID:projekt@example.org\r\nDTSTAMP:20260911T080000Z\r\n"
    "DTSTART:20300115T090000Z\r\nDTEND:20300115T100000Z\r\n"
    "SUMMARY:Projektstart\r\nLOCATION:Raum 3\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
)


def invite_mail(ics: str = INVITE) -> bytes:
    message = EmailMessage()
    message["Subject"] = "Einladung: Projektstart"
    message["From"] = "Chefin <chefin@example.org>"
    message["Date"] = format_datetime(datetime.now(UTC))
    message.set_content("Bitte zusagen.")
    message.add_attachment(ics, subtype="calendar", filename="invite.ics")
    return bytes(message)


def test_german_appointment_in_the_body() -> None:
    body = "Hallo Alice,\nam 15.10. um 14:30 Uhr passt es bei uns.\nViele Grüße"
    found = detect([], "Termin beim Zahnarzt", body, NOW, TZ, NOW)
    assert found is not None
    assert (found.source, found.title) == ("text", "Termin beim Zahnarzt")
    assert found.start == datetime(2026, 10, 15, 12, 30, tzinfo=UTC)
    assert found.end - found.start == timedelta(hours=1)


def test_english_subject_relative_to_the_sent_date() -> None:
    found = detect([], "Re: Meeting tomorrow 3pm", "", NOW, TZ, NOW)
    assert found is not None
    assert found.title == "Meeting"
    assert found.start == datetime(2026, 9, 12, 13, 0, tzinfo=UTC)


def test_no_appointment_without_a_reason() -> None:
    assert detect([], "Rechnung", "Bitte bis morgen 14 Uhr zahlen.", NOW, TZ, NOW) is None
    assert detect([], "Termin", "Wann passt es dir?", NOW, TZ, NOW) is None  # ohne Datum


def test_quotes_and_past_dates_are_ignored() -> None:
    body = "Danke!\n\nAm 10.09.2026 um 14:03 schrieb Max:\n> Termin am 20.08. um 9 Uhr?"
    assert detect([], "AW: Termin", body, NOW, TZ, NOW) is None
    assert detect([], "Termin am 01.09.2026 um 9 Uhr", "", NOW, TZ, NOW) is None


def test_invitations_win_and_cancellations_are_skipped() -> None:
    found = detect([INVITE.encode()], "Einladung: Projektstart", "", NOW, TZ, NOW)
    assert found is not None
    assert (found.source, found.title, found.location) == ("invite", "Projektstart", "Raum 3")
    assert found.start == datetime(2030, 1, 15, 9, 0, tzinfo=UTC)
    cancelled = INVITE.replace("METHOD:REQUEST", "METHOD:CANCEL").encode()
    assert detect([cancelled], "Abgesagt: Projektstart", "", NOW, TZ, NOW) is None
    assert detect([b"kaputt"], "Einladung", "", NOW, TZ, NOW) is None


def test_parse_mail_collects_invitations() -> None:
    parsed = mail.parse_mail(1, invite_mail())
    assert len(parsed.invites) == 1
    assert b"SUMMARY:Projektstart" in parsed.invites[0]
    assert parsed.body_text == "Bitte zusagen."


async def test_confirm_and_dismiss_suggestions(alice: AsyncClient, mailbox: FakeMailbox) -> None:
    mailbox.add(invite_mail())
    sent = format_datetime(datetime.now(UTC))
    mailbox.add(make_mail("Besprechung", "Treffen wir uns morgen um 10 Uhr?", date=sent))
    assert (await alice.post("/api/mail/accounts", json=ACCOUNT)).status_code == 201

    pending = (await alice.get("/api/mail/suggestions")).json()
    by_subject: dict[str, Any] = {m["subject"]: m for m in pending}
    assert set(by_subject) == {"Einladung: Projektstart", "Besprechung"}
    invite = by_subject["Einladung: Projektstart"]
    suggestion = invite["suggestion"]
    assert suggestion["title"] == "Projektstart"
    assert (suggestion["start_date"], suggestion["start_time"]) == ("2030-01-15", "10:00:00")
    assert (suggestion["source"], suggestion["status"]) == ("invite", "pending")

    accepted = await alice.post(f"/api/mail/messages/{invite['id']}/suggestion/accept")
    assert accepted.status_code == 201, accepted.text
    event = accepted.json()["event"]
    assert (event["title"], event["location"], event["source"]) == (
        "Projektstart",
        "Raum 3",
        "mail",
    )
    assert event["description"].startswith("Aus E-Mail von Chefin")
    events = await alice.get("/api/events", params={"from": "2030-01-01", "to": "2030-02-01"})
    assert [e["title"] for e in events.json()] == ["Projektstart"]
    again = await alice.post(f"/api/mail/messages/{invite['id']}/suggestion/accept")
    assert again.status_code == 409
    detail = (await alice.get(f"/api/mail/messages/{invite['id']}")).json()
    assert detail["suggestion"]["status"] == "accepted"
    assert detail["event_id"] == event["id"]

    other = by_subject["Besprechung"]
    assert other["suggestion"]["start_time"] == "10:00:00"
    dismissed = await alice.post(f"/api/mail/messages/{other['id']}/suggestion/dismiss")
    assert dismissed.status_code == 204
    assert (await alice.get("/api/mail/suggestions")).json() == []
