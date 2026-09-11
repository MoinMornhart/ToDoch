"""Nachgebauter IMAP-Server für Tests: dieselben Antworten wie imaplib, ohne Netzwerk."""

from __future__ import annotations

import imaplib
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Any


def make_mail(
    subject: str = "Willkommen",
    body: str = "Hallo und willkommen bei ToDoch.",
    *,
    sender: str = "Team <team@example.org>",
    date: str = "Fri, 11 Sep 2026 08:30:00 +0200",
    html: str | None = None,
) -> bytes:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = "alice@example.org"
    message["Date"] = date
    message["Message-ID"] = f"<{abs(hash(subject))}@example.org>"
    message.set_content(body)
    if html is not None:
        message.add_alternative(html, subtype="html")
    return bytes(message)


@dataclass
class FakeMailbox:
    folder: str = "INBOX"
    uidvalidity: int = 1
    password: str | None = None  # None: jedes Passwort passt
    messages: dict[int, tuple[bytes, bool]] = field(default_factory=dict)
    connections: list[tuple[str, str]] = field(default_factory=list)
    searches: list[tuple[str, ...]] = field(default_factory=list)

    def add(self, raw: bytes, *, seen: bool = False) -> int:
        uid = max(self.messages, default=0) + 1
        self.messages[uid] = (raw, seen)
        return uid

    def connect(self, target: Any, address: str) -> FakeImap:
        self.connections.append((target.host, address))
        return FakeImap(self)


class FakeImap:
    def __init__(self, box: FakeMailbox) -> None:
        self.box = box

    def login(self, user: str, password: str) -> tuple[str, list[bytes]]:
        if self.box.password is not None and password != self.box.password:
            raise imaplib.IMAP4.error("[AUTHENTICATIONFAILED] Invalid credentials")
        return "OK", [b"Logged in"]

    def select(self, mailbox: str, readonly: bool = False) -> tuple[str, list[bytes]]:
        assert readonly, "ToDoch wählt Postfächer nur lesend aus"
        if mailbox.strip('"') != self.box.folder:
            return "NO", [b"Mailbox doesn't exist"]
        return "OK", [str(len(self.box.messages)).encode()]

    def response(self, code: str) -> tuple[str, list[bytes | None]]:
        assert code == "UIDVALIDITY"
        return code, [str(self.box.uidvalidity).encode()]

    def uid(self, command: str, *args: str) -> tuple[str, list[Any]]:
        uids = sorted(self.box.messages)
        if command == "SEARCH":
            self.box.searches.append(args)
            kind, value = args
            if kind == "UID":
                start = int(value.split(":", 1)[0])
                # Wie echte Server: „n:*“ liefert immer mindestens die letzte Mail
                found = [u for u in uids if u >= start] or uids[-1:]
            else:
                found = uids
            return "OK", [" ".join(str(u) for u in found).encode()]
        if command == "FETCH":
            uid_set, items = args
            assert "BODY.PEEK[]" in items, "Mails nie als gelesen markieren"
            data: list[Any] = []
            for uid in (int(u) for u in uid_set.split(",")):
                raw, seen = self.box.messages[uid]
                head = f"{uid} (UID {uid} RFC822.SIZE {len(raw)} BODY[]<0> {{{len(raw)}}}"
                data.append((head.encode(), raw))
                data.append(f" FLAGS ({'\\Seen' if seen else ''}))".encode())
            return "OK", data
        raise imaplib.IMAP4.error(f"unexpected {command}")

    def logout(self) -> tuple[str, list[bytes]]:
        return "BYE", [b"Logging out"]
