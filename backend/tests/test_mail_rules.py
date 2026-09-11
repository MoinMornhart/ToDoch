"""Regeln für Mails: reiner Textvergleich, Aufgaben und „gelesen“ automatisch, Prüfungen."""

import uuid

from httpx import AsyncClient

from app.models import MailMessage, MailRule
from app.services.mail_rules import matches
from tests.fake_imap import FakeMailbox, make_mail

ACCOUNT = {"email": "alice@example.org", "password": "imap-geheim", "imap_host": "imap.example.org"}
EN = {"Accept-Language": "en"}


async def _areas(client: AsyncClient) -> dict[str, str]:
    return {a["name"]: a["id"] for a in (await client.get("/api/areas")).json()}


def test_matching_is_plain_text_and_case_insensitive() -> None:
    account = uuid.uuid4()
    rule = MailRule(from_contains="Stadtwerke", subject_contains="", body_contains="")
    message = MailMessage(
        account_id=account,
        from_name="",
        from_address="rechnung@STADTWERKE.example",
        subject="Rechnung",
        body_text="",
    )
    assert matches(rule, message)
    rule.body_contains = "(a+)+$"  # kein regulärer Ausdruck – wird wörtlich gesucht
    assert not matches(rule, message)
    message.body_text = "Muster (a+)+$ im Text"
    assert matches(rule, message)
    rule.account_id = uuid.uuid4()  # nur für ein anderes Postfach
    assert not matches(rule, message)
    empty = MailRule(from_contains="", subject_contains="", body_contains="")
    assert not matches(empty, message)


async def test_rules_create_tasks_and_mark_read(alice: AsyncClient, mailbox: FakeMailbox) -> None:
    areas = await _areas(alice)
    created = await alice.post(
        "/api/mail/rules",
        json={
            "name": "Stadtwerke",
            "from_contains": "stadtwerke",
            "subject_contains": "rechnung",
            "area_id": areas["Privat"],
            "priority": 2,
            "tags": ["finanzen"],
        },
    )
    assert created.status_code == 201, created.text
    assert (created.json()["area_name"], created.json()["account_name"]) == ("Privat", None)
    newsletter = {"name": "Newsletter", "from_contains": "news@", "create_task": False}
    await alice.post("/api/mail/rules", json={**newsletter, "mark_read": True})

    stadtwerke = "Stadtwerke <rechnung@stadtwerke.example>"
    mailbox.add(make_mail("Ihre Rechnung September", "Betrag: 42 €", sender=stadtwerke))
    mailbox.add(make_mail("Neues im September", "Hallo", sender="news@shop.example"))
    mailbox.add(make_mail("Rechnung vom Handwerker", "Anbei", sender="m@handwerk.example"))
    assert (await alice.post("/api/mail/accounts", json=ACCOUNT)).status_code == 201

    messages = {m["subject"]: m for m in (await alice.get("/api/mail/messages")).json()}
    task_id = messages["Ihre Rechnung September"]["task_id"]
    assert task_id is not None
    task = (await alice.get(f"/api/tasks/{task_id}")).json()
    assert (task["title"], task["area_id"], task["priority"], task["tags"], task["source"]) == (
        "Ihre Rechnung September",
        areas["Privat"],
        2,
        ["finanzen"],
        "mail_rule",
    )
    assert "> Betrag: 42 €" in task["notes"]
    news = messages["Neues im September"]
    assert (news["is_read"], news["task_id"]) == (True, None)
    assert messages["Rechnung vom Handwerker"]["task_id"] is None  # nur eine Bedingung passt
    rules = {r["name"]: r for r in (await alice.get("/api/mail/rules")).json()}
    assert rules["Stadtwerke"]["match_count"] == 1
    assert rules["Newsletter"]["match_count"] == 1


async def test_apply_rule_to_existing_mails(alice: AsyncClient, mailbox: FakeMailbox) -> None:
    mailbox.add(make_mail("Angebot 4711", "Siehe Anhang", sender="Berger <b@berger.example>"))
    await alice.post("/api/mail/accounts", json=ACCOUNT)
    rule = await alice.post("/api/mail/rules", json={"name": "Berger", "from_contains": "berger"})
    rule_id = rule.json()["id"]
    assert (await alice.post(f"/api/mail/rules/{rule_id}/apply")).json() == {"matched": 1}
    assert (await alice.post(f"/api/mail/rules/{rule_id}/apply")).json() == {"matched": 1}
    tasks = (await alice.get("/api/tasks", params={"view": "all"})).json()
    assert [t["title"] for t in tasks].count("Angebot 4711") == 1  # nicht doppelt


async def test_rule_checks(alice: AsyncClient, bob: AsyncClient) -> None:
    empty = await alice.post("/api/mail/rules", json={"name": "Leer"}, headers=EN)
    assert empty.status_code == 422
    assert "Enter at least one condition." in empty.text
    nothing = await alice.post(
        "/api/mail/rules",
        json={"name": "x", "subject_contains": "a", "create_task": False, "mark_read": False},
    )
    assert nothing.status_code == 422
    assert "Mindestens eine Aktion wählen." in nothing.text

    rule = (await alice.post("/api/mail/rules", json={"name": "A", "subject_contains": "a"})).json()
    cleared = await alice.patch(f"/api/mail/rules/{rule['id']}", json={"subject_contains": ""})
    assert cleared.status_code == 422
    paused = await alice.patch(f"/api/mail/rules/{rule['id']}", json={"enabled": False})
    assert paused.json()["enabled"] is False

    alice_area = (await _areas(alice))["Arbeit"]
    foreign_area = await bob.post(
        "/api/mail/rules", json={"name": "B", "subject_contains": "b", "area_id": alice_area}
    )
    assert foreign_area.status_code == 404
    foreign_account = await bob.post(
        "/api/mail/rules",
        json={"name": "B", "subject_contains": "b", "account_id": str(uuid.uuid4())},
    )
    assert foreign_account.status_code == 404

    assert (await alice.delete(f"/api/mail/rules/{rule['id']}")).status_code == 204
    assert (await alice.get("/api/mail/rules")).json() == []
