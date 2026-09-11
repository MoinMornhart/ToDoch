"""E-Mail per IMAP: Text statt HTML, sichere Verbindung, Abgleich, Aufgaben aus Mails."""

import ssl
from datetime import UTC, date, datetime
from email.message import EmailMessage
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.models import MailAccount
from app.services import external_calendars as feeds
from app.services import mail
from tests.fake_imap import FakeImap, FakeMailbox, make_mail

ACCOUNT = {"email": "alice@example.org", "password": "imap-geheim", "imap_host": "imap.example.org"}
TODAY = date(2026, 9, 11)
EN = {"Accept-Language": "en"}


def _target(**changes: Any) -> mail.ImapTarget:
    values: dict[str, Any] = {
        "host": "imap.example.org",
        "port": 993,
        "security": "ssl",
        "username": "alice",
        "password": "pw",
        **changes,
    }
    return mail.ImapTarget(**values)


# --- Mails lesen ----------------------------------------------------------------------------


def test_plain_mail_with_encoded_headers() -> None:
    raw = (
        b"Subject: =?utf-8?q?Rechnung_f=C3=BCr_September?=\r\n"
        b"From: =?utf-8?q?J=C3=BCrgen_M=C3=BCller?= <juergen@example.org>\r\n"
        b"To: alice@example.org, Bob <bob@example.org>\r\n"
        b"Date: Fri, 11 Sep 2026 08:30:00 +0200\r\n"
        b"Message-ID: <abc@example.org>\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
        b"Hallo Alice,\r\n\r\n\r\n\r\nbitte bis Freitag zahlen.\x00\r\n"
    )
    parsed = mail.parse_mail(7, raw, seen=True)
    assert parsed.subject == "Rechnung für September"
    assert (parsed.from_name, parsed.from_address) == ("Jürgen Müller", "juergen@example.org")
    assert parsed.recipients == "alice@example.org, bob@example.org"
    assert parsed.sent_at == datetime(2026, 9, 11, 6, 30, tzinfo=UTC)
    assert parsed.message_id == "<abc@example.org>"
    assert parsed.body_text == "Hallo Alice,\n\nbitte bis Freitag zahlen."
    assert parsed.snippet == "Hallo Alice, bitte bis Freitag zahlen."
    assert parsed.seen and not parsed.has_html and not parsed.truncated


def test_html_only_mail_becomes_safe_text() -> None:
    message = EmailMessage()
    message["Subject"] = "Newsletter"
    message["From"] = "news@example.org"
    message.set_content(
        "<html><head><title>Titel</title><style>p{color:red}</style></head><body>"
        "<p>Hallo&nbsp;<b>Alice</b></p><script>alert(1)</script>"
        '<img src="https://track.example/pixel.gif"><div>Zeile&nbsp;2 &amp; mehr</div>'
        '<a href="https://example.org">Link</a></body></html>',
        subtype="html",
    )
    message.add_attachment(b"%PDF-1.4", maintype="application", subtype="pdf", filename="a.pdf")
    parsed = mail.parse_mail(1, bytes(message))
    assert parsed.body_text == "Hallo Alice\nZeile 2 & mehr\nLink"
    assert parsed.has_html
    assert parsed.attachment_count == 1


def test_plain_text_is_preferred_over_html() -> None:
    raw = make_mail("Beides", "Nur der Text.", html="<p>HTML-Fassung</p>")
    parsed = mail.parse_mail(1, raw)
    assert parsed.body_text == "Nur der Text."
    assert parsed.has_html


def test_broken_mails_do_not_crash() -> None:
    unknown = (
        b"Subject: x\r\nContent-Type: text/plain; charset=x-unbekannt\r\n\r\nGr\xc3\xbc\xc3\x9fe"
    )
    assert mail.parse_mail(1, unknown).body_text == "Grüße"
    garbage = mail.parse_mail(2, b"\xff\xfe kein Kopf \x00", size=10_000_000)
    assert garbage.subject == "" and garbage.truncated
    assert mail.parse_mail(3, b"Date: gestern\r\n\r\nx").sent_at is None


# --- IMAP -----------------------------------------------------------------------------------


def test_first_sync_takes_the_newest_mails_and_flags() -> None:
    box = FakeMailbox()
    for i in range(5):
        box.add(make_mail(f"Mail {i}"), seen=i == 4)
    result = mail._fetch(FakeImap(box), _target(), None, 0, 3, TODAY)
    assert [m.uid for m in result.messages] == [3, 4, 5]
    assert [m.seen for m in result.messages] == [False, False, True]
    assert (result.last_uid, result.uidvalidity) == (5, 1)
    assert box.searches == [("SINCE", "12-Aug-2026")]


def test_later_syncs_only_fetch_new_mails_in_order() -> None:
    box = FakeMailbox()
    for i in range(3):
        box.add(make_mail(f"Alt {i}"))
    for i in range(4):
        box.add(make_mail(f"Neu {i}"))
    first = mail._fetch(FakeImap(box), _target(), 1, 3, 2, TODAY)
    assert [m.subject for m in first.messages] == ["Neu 0", "Neu 1"]
    assert first.last_uid == 5
    rest = mail._fetch(FakeImap(box), _target(), 1, 5, 200, TODAY)
    assert [m.subject for m in rest.messages] == ["Neu 2", "Neu 3"]
    # „8:*“ liefert bei echten Servern die letzte Mail – sie wird nicht doppelt geholt
    nothing = mail._fetch(FakeImap(box), _target(), 1, 7, 200, TODAY)
    assert (nothing.messages, nothing.last_uid) == ([], 7)
    assert box.searches[-1] == ("UID", "8:*")


def test_renumbered_mailbox_starts_over() -> None:
    box = FakeMailbox(uidvalidity=2)
    box.add(make_mail("Nach Umzug"))
    result = mail._fetch(FakeImap(box), _target(), 1, 40, 200, TODAY)
    assert [m.subject for m in result.messages] == ["Nach Umzug"]
    assert result.uidvalidity == 2


def test_login_and_folder_errors() -> None:
    box = FakeMailbox(password="richtig")
    with pytest.raises(mail.MailError, match="Anmeldung am Postfach"):
        mail._fetch(FakeImap(box), _target(password="falsch"), None, 0, 10, TODAY)
    with pytest.raises(mail.MailError, match="Ordner"):
        mail._fetch(FakeImap(box), _target(password="richtig", folder="Archiv"), None, 0, 10, TODAY)


def test_connection_uses_checked_address_and_hostname(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, Any] = {}

    def fake_create_connection(address: tuple[str, int], timeout: float | None = None) -> str:
        calls["address"] = address
        return "socket"

    class Context:
        def wrap_socket(self, sock: str, server_hostname: str) -> str:
            calls["sni"] = server_hostname
            return sock

    monkeypatch.setattr(mail.socket, "create_connection", fake_create_connection)
    conn: Any = mail._PinnedSSL.__new__(mail._PinnedSSL)
    conn.host, conn.port, conn._address, conn.ssl_context = (
        "imap.example.org",
        993,
        "93.184.216.34",
        Context(),
    )
    assert conn._create_socket(5) == "socket"
    assert calls == {"address": ("93.184.216.34", 993), "sni": "imap.example.org"}


def test_tls_is_verified() -> None:
    context = mail.tls_context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname
    assert context.minimum_version >= ssl.TLSVersion.TLSv1_2


async def test_internal_mail_servers_are_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    async def loopback(host: str, port: int) -> list[str]:
        return ["127.0.0.1"]

    monkeypatch.setattr(feeds, "resolve", loopback)
    with pytest.raises(mail.MailError, match="nicht erlaubt"):
        await mail.fetch_mailbox(_target(), allow_private=True, uidvalidity=None, last_uid=0)


# --- API ------------------------------------------------------------------------------------


async def test_add_account_read_and_make_task(alice: AsyncClient, mailbox: FakeMailbox) -> None:
    mailbox.add(
        make_mail(
            "Angebot prüfen",
            "Bitte bis **Freitag** ansehen.\nDanke",
            sender="Berger <b@berger.example>",
        )
    )
    r = await alice.post("/api/mail/accounts", json=ACCOUNT)
    assert r.status_code == 201, r.text
    account = r.json()
    assert (account["message_count"], account["unread_count"]) == (2, 2)
    assert account["username"] == account["name"] == "alice@example.org"
    assert "imap-geheim" not in r.text  # das Passwort wird nie zurückgegeben
    assert mailbox.connections == [("imap.example.org", "93.184.216.34")]

    messages = (await alice.get("/api/mail/messages")).json()
    assert [m["subject"] for m in messages] == ["Angebot prüfen", "Willkommen"]
    first = messages[0]
    assert "body_text" not in first and first["is_read"] is False
    detail = (await alice.get(f"/api/mail/messages/{first['id']}")).json()
    assert detail["body_text"] == "Bitte bis **Freitag** ansehen.\nDanke"
    assert detail["is_read"] is True
    assert (await alice.get("/api/mail/accounts")).json()[0]["unread_count"] == 1

    task = (await alice.post(f"/api/mail/messages/{first['id']}/task", json={})).json()
    assert (task["title"], task["source"]) == ("Angebot prüfen", "mail")
    assert task["notes"].startswith("Aus E-Mail von Berger <b@berger.example>")
    assert "> Bitte bis **Freitag** ansehen.\n> Danke" in task["notes"]
    again = (await alice.post(f"/api/mail/messages/{first['id']}/task")).json()
    assert again["id"] == task["id"]
    assert (await alice.get(f"/api/mail/messages/{first['id']}")).json()["task_id"] == task["id"]

    found = (await alice.get("/api/mail/messages", params={"q": "berger"})).json()
    assert [m["subject"] for m in found] == ["Angebot prüfen"]
    unread = (await alice.get("/api/mail/messages", params={"unread": "true"})).json()
    assert [m["subject"] for m in unread] == ["Willkommen"]
    await alice.patch(f"/api/mail/messages/{unread[0]['id']}", json={"is_read": True})
    assert (await alice.get("/api/mail/messages", params={"unread": "true"})).json() == []


async def test_sync_fetches_only_new_mails(
    alice: AsyncClient, mailbox: FakeMailbox, resources: Any
) -> None:
    account = (await alice.post("/api/mail/accounts", json=ACCOUNT)).json()
    mailbox.add(make_mail("Zweite"))
    synced = (await alice.post(f"/api/mail/accounts/{account['id']}/sync")).json()
    assert synced["message_count"] == 2
    assert mailbox.searches[-1] == ("UID", "2:*")

    async with resources.sessionmaker() as db:
        assert await mail.sync_due_accounts(db, resources.crypto) == 0  # gerade erst abgeholt
        await db.execute(update(MailAccount).values(last_synced_at=None))
        await db.commit()
        mailbox.add(make_mail("Dritte"))
        assert await mail.sync_due_accounts(db, resources.crypto) == 1
    assert (await alice.get("/api/mail/accounts")).json()[0]["message_count"] == 3

    # Neu nummeriertes Postfach: alte Mails fallen weg, die neuen kommen
    mailbox.uidvalidity = 2
    mailbox.messages = {}
    mailbox.add(make_mail("Nach Umzug"))
    await alice.post(f"/api/mail/accounts/{account['id']}/sync")
    subjects = [m["subject"] for m in (await alice.get("/api/mail/messages")).json()]
    assert subjects == ["Nach Umzug"]


async def test_wrong_password_is_not_saved(alice: AsyncClient, mailbox: FakeMailbox) -> None:
    mailbox.password = "richtig"
    r = await alice.post("/api/mail/accounts", json=ACCOUNT, headers=EN)
    assert r.status_code == 422
    assert (
        r.json()["detail"] == "Signing in to the mailbox failed. Check the user name and password."
    )
    assert (await alice.get("/api/mail/accounts")).json() == []

    account = (
        await alice.post("/api/mail/accounts", json={**ACCOUNT, "password": "richtig"})
    ).json()
    changed = await alice.patch(f"/api/mail/accounts/{account['id']}", json={"password": "alt"})
    assert changed.json()["last_error"].startswith("Anmeldung am Postfach fehlgeschlagen")
    fixed = await alice.patch(f"/api/mail/accounts/{account['id']}", json={"password": "richtig"})
    assert fixed.json()["last_error"] is None


async def test_only_encrypted_and_allowed_servers(
    alice: AsyncClient, bob: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    plain = await alice.post("/api/mail/accounts", json={**ACCOUNT, "security": "none"})
    assert plain.status_code == 422
    quote = await alice.post("/api/mail/accounts", json={**ACCOUNT, "folder": 'INBOX" x'})
    assert quote.status_code == 422

    async def home_network(host: str, port: int) -> list[str]:
        return ["192.168.178.20"]

    monkeypatch.setattr(feeds, "resolve", home_network)
    r = await bob.post("/api/mail/accounts", json={**ACCOUNT, "imap_host": "nas.fritz.box"})
    assert r.status_code == 422
    assert r.json()["detail"] == "Adressen im eigenen Netz kann nur ein Admin einbinden."
    admin = await alice.post("/api/mail/accounts", json={**ACCOUNT, "imap_host": "nas.fritz.box"})
    assert admin.status_code == 201


async def test_delete_account_removes_its_mails(alice: AsyncClient, bob: AsyncClient) -> None:
    account = (await alice.post("/api/mail/accounts", json=ACCOUNT)).json()
    others = await bob.get("/api/mail/messages", params={"account_id": account["id"]})
    assert others.json() == []
    assert (await alice.delete(f"/api/mail/accounts/{account['id']}")).status_code == 204
    assert (await alice.get("/api/mail/messages")).json() == []
    assert (await alice.get("/api/mail/accounts")).json() == []
