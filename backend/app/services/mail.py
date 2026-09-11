"""E-Mail-Postfächer per IMAP: sicher verbinden, neue Mails holen, als Text speichern.

Verbindung: nur verschlüsselt (IMAPS oder STARTTLS, mindestens TLS 1.2), Zertifikat und
Hostname werden geprüft. Der Servername wird vorher aufgelöst und geprüft wie bei abonnierten
Kalendern – kein Loopback, keine Cloud-Metadaten, Heimnetz nur für Admins – und verbunden wird
genau mit der geprüften Adresse (kein DNS-Rebinding).

Inhalt: Das Postfach wird nur gelesen (schreibgeschützt ausgewählt, BODY.PEEK – nichts wird als
gelesen markiert), höchstens 512 KB je Mail und 200 Mails je Abgleich. Gespeichert wird reiner
Text: HTML wird nie angezeigt, sondern in Text umgewandelt – Skripte, Styles, Bilder und
Tracking-Pixel fallen dabei weg.
"""

from __future__ import annotations

import contextlib
import email
import email.policy
import html
import imaplib
import logging
import re
import socket
import ssl
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from email.utils import getaddresses, parseaddr, parsedate_to_datetime
from typing import Any

import anyio.to_thread
import nh3
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MailAccount, MailMessage, User
from app.security.crypto import Crypto, DecryptionError
from app.services import external_calendars as feeds
from app.services.mail_rules import enabled_rules, run_rules
from app.services.mail_suggestions import detect

log = logging.getLogger(__name__)

MAX_MESSAGE_BYTES = 512 * 1024
BATCH = 200
FIRST_BATCH = 50
FIRST_SYNC_DAYS = 30
FETCH_CHUNK = 25
MAX_STORED = 2000
MAX_BODY_CHARS = 100_000
TIMEOUT = 20
CALENDAR_TYPES = ("text/calendar", "application/ics")
MAX_INVITES = 3
MAX_INVITE_BYTES = 256 * 1024
IMAP_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


class MailError(Exception):
    """Verständliche Fehlermeldung (Deutsch; übersetzt in app/i18n.py)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def password_context(account_id: object) -> str:
    return f"mail_account:{account_id}:password"


@dataclass
class ImapTarget:
    host: str
    port: int
    security: str
    username: str
    password: str
    folder: str = "INBOX"


@dataclass
class ParsedMail:
    uid: int
    message_id: str = ""
    from_name: str = ""
    from_address: str = ""
    recipients: str = ""
    subject: str = ""
    sent_at: datetime | None = None
    body_text: str = ""
    snippet: str = ""
    has_html: bool = False
    attachment_count: int = 0
    seen: bool = False
    truncated: bool = False
    # Kalendereinladungen (text/calendar, .ics) für die Terminerkennung
    invites: list[bytes] = field(default_factory=list)


@dataclass
class FetchResult:
    uidvalidity: int
    last_uid: int
    messages: list[ParsedMail] = field(default_factory=list)


# --- Mails in Text verwandeln ---------------------------------------------------------------

CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
HEAD = re.compile(r"(?is)<head\b.*?</head\s*>")
BLOCK_END = re.compile(r"(?i)<\s*(?:br|/p|/div|/tr|/li|/h[1-6]|/table|/blockquote)\b[^>]*>")


def _tidy(text: str) -> str:
    text = CONTROL.sub("", text.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " "))
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def html_to_text(markup: str) -> str:
    """HTML → Text über die Allowlist von nh3 ohne erlaubte Tags (Skripte fallen ganz weg)."""
    markup = BLOCK_END.sub("\n", HEAD.sub("", markup))
    return _tidy(html.unescape(nh3.clean(markup, tags=set())))


def _one_line(value: str, limit: int) -> str:
    return re.sub(r"\s+", " ", CONTROL.sub("", value)).strip()[:limit]


def _header(message: Any, name: str) -> str:
    try:
        values = message.get_all(name) or []
        return ", ".join(str(v) for v in values)
    except Exception:  # kaputte Kopfzeile – dann eben leer
        return ""


def _content(part: Any) -> str:
    try:
        return str(part.get_content())
    except (LookupError, ValueError, AssertionError):  # unbekannter Zeichensatz o. Ä.
        payload = part.get_payload(decode=True)
        return payload.decode("utf-8", errors="replace") if isinstance(payload, bytes) else ""


def _sent_at(message: Any) -> datetime | None:
    try:
        raw = str(message.get("date") or "")
        value = parsedate_to_datetime(raw) if raw else None
    except Exception:  # unlesbares Datum
        return None
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def parse_mail(uid: int, raw: bytes, *, seen: bool = False, size: int | None = None) -> ParsedMail:
    message = email.message_from_bytes(raw, policy=email.policy.default)
    body = message.get_body(preferencelist=("plain", "html"))
    text = ""
    if body is not None:
        content = _content(body)
        text = html_to_text(content) if body.get_content_type() == "text/html" else _tidy(content)
    has_html, attachments = False, 0
    invites: list[bytes] = []
    try:
        for part in message.walk():
            kind = part.get_content_type()
            has_html = has_html or kind == "text/html"
            is_calendar = kind in CALENDAR_TYPES or (part.get_filename() or "").lower().endswith(
                ".ics"
            )
            if is_calendar and len(invites) < MAX_INVITES:
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes) and payload:
                    invites.append(payload[:MAX_INVITE_BYTES])
        attachments = sum(1 for _ in message.iter_attachments())
    except Exception:  # abgeschnittene oder kaputte Struktur
        log.debug("Aufbau der Mail %s nicht lesbar", uid, exc_info=True)
    from_name, from_address = parseaddr(_header(message, "from"))
    recipients = [
        address or name
        for name, address in getaddresses([_header(message, "to"), _header(message, "cc")])
        if address or name
    ]
    return ParsedMail(
        uid=uid,
        message_id=_one_line(_header(message, "message-id"), 500),
        from_name=_one_line(from_name, 200),
        from_address=_one_line(from_address, 320),
        recipients=_one_line(", ".join(recipients), 1000),
        subject=_one_line(_header(message, "subject"), 500),
        sent_at=_sent_at(message),
        body_text=text[:MAX_BODY_CHARS],
        snippet=_one_line(text, 200),
        has_html=has_html,
        attachment_count=attachments,
        seen=seen,
        truncated=size is not None and size > len(raw),
        invites=invites,
    )


# --- IMAP -----------------------------------------------------------------------------------


class _PinnedSSL(imaplib.IMAP4_SSL):
    """IMAPS zur vorher geprüften IP – Zertifikat und SNI gelten weiter für den Hostnamen."""

    def __init__(self, host: str, port: int, address: str, context: ssl.SSLContext) -> None:
        self._address = address
        super().__init__(host, port, ssl_context=context, timeout=TIMEOUT)

    def _create_socket(self, timeout: float | None = None) -> socket.socket:
        sock = socket.create_connection((self._address, self.port), timeout)
        wrapped: socket.socket = self.ssl_context.wrap_socket(sock, server_hostname=self.host)
        return wrapped


class _PinnedPlain(imaplib.IMAP4):
    """Für STARTTLS: verbindet zur geprüften IP, vor der Anmeldung wird verschlüsselt."""

    def __init__(self, host: str, port: int, address: str) -> None:
        self._address = address
        super().__init__(host, port, timeout=TIMEOUT)

    def _create_socket(self, timeout: float | None = None) -> socket.socket:
        return socket.create_connection((self._address, self.port), timeout)


def tls_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return context


def open_connection(target: ImapTarget, address: str) -> Any:
    """Baut die verschlüsselte Verbindung auf (in Tests ersetzt)."""
    if target.security == "ssl":
        return _PinnedSSL(target.host, target.port, address, tls_context())
    conn = _PinnedPlain(target.host, target.port, address)
    try:
        conn.starttls(tls_context())
    except imaplib.IMAP4.error as exc:
        with contextlib.suppress(Exception):
            conn.shutdown()
        raise MailError(
            "Der Mailserver unterstützt keine verschlüsselte Verbindung (STARTTLS)."
        ) from exc
    return conn


def _imap_date(day: date) -> str:
    return f"{day.day:02d}-{IMAP_MONTHS[day.month - 1]}-{day.year}"


def _numbers(data: list[Any]) -> list[int]:
    words = b" ".join(d for d in data if isinstance(d, bytes)).split()
    return sorted({int(w) for w in words if w.isdigit()})


def _fetch(
    conn: Any, target: ImapTarget, uidvalidity: int | None, last_uid: int, limit: int, today: date
) -> FetchResult:
    try:
        conn.login(target.username, target.password)
    except imaplib.IMAP4.error as exc:
        raise MailError(
            "Anmeldung am Postfach fehlgeschlagen. Benutzername und Passwort prüfen."
        ) from exc
    status, _ = conn.select(f'"{target.folder}"', readonly=True)
    if status != "OK":
        raise MailError("Den Ordner gibt es im Postfach nicht.")
    _, values = conn.response("UIDVALIDITY")
    current = int(values[0]) if values and values[0] and bytes(values[0]).isdigit() else 0
    if uidvalidity is not None and current != uidvalidity:
        last_uid = 0  # Postfach wurde neu nummeriert: von vorn beginnen

    if last_uid:
        status, data = conn.uid("SEARCH", "UID", f"{last_uid + 1}:*")
    else:
        since = today - timedelta(days=FIRST_SYNC_DAYS)
        status, data = conn.uid("SEARCH", "SINCE", _imap_date(since))
    if status != "OK":
        raise MailError("Das Postfach antwortet nicht wie erwartet.")
    uids = [uid for uid in _numbers(data) if uid > last_uid]
    if last_uid:
        chosen = uids[:limit]  # der Reihe nach, damit keine Mail übersprungen wird
        new_last = chosen[-1] if chosen else last_uid
    else:
        chosen = uids[-limit:]  # erster Abgleich: die neuesten
        new_last = uids[-1] if uids else 0

    messages: list[ParsedMail] = []
    items = f"(UID FLAGS RFC822.SIZE BODY.PEEK[]<0.{MAX_MESSAGE_BYTES}>)"
    for start in range(0, len(chosen), FETCH_CHUNK):
        chunk = ",".join(str(uid) for uid in chosen[start : start + FETCH_CHUNK])
        status, data = conn.uid("FETCH", chunk, items)
        if status != "OK":
            raise MailError("Das Postfach antwortet nicht wie erwartet.")
        # Jede Mail kommt als (Kopf, Inhalt); Angaben nach dem Inhalt folgen als eigenes Stück
        entries: list[tuple[str, bytes]] = []
        for item in data:
            if isinstance(item, tuple) and len(item) >= 2:
                entries.append((bytes(item[0]).decode("ascii", "replace"), bytes(item[1])))
            elif isinstance(item, bytes) and entries:
                meta, raw = entries[-1]
                entries[-1] = (meta + " " + item.decode("ascii", "replace"), raw)
        for meta, raw in entries:
            uid_match = re.search(r"\bUID (\d+)", meta)
            if uid_match is None:
                continue
            flags = re.search(r"\bFLAGS \(([^)]*)\)", meta)
            size = re.search(r"\bRFC822\.SIZE (\d+)", meta)
            try:
                messages.append(
                    parse_mail(
                        int(uid_match[1]),
                        raw,
                        seen=bool(flags and "\\seen" in flags[1].lower()),
                        size=int(size[1]) if size else None,
                    )
                )
            except Exception:  # eine kaputte Mail darf den Abgleich nicht aufhalten
                log.warning("Mail %s ließ sich nicht lesen", uid_match[1], exc_info=True)
    return FetchResult(uidvalidity=current, last_uid=new_last, messages=messages)


async def fetch_mailbox(
    target: ImapTarget,
    *,
    allow_private: bool,
    uidvalidity: int | None,
    last_uid: int,
    limit: int = BATCH,
) -> FetchResult:
    try:
        addresses = await feeds.check_address(target.host, target.port, allow_private=allow_private)
    except feeds.FeedError as exc:
        raise MailError(exc.message) from exc
    address = next((a for a in addresses if ":" not in a), addresses[0])
    today = datetime.now(UTC).date()

    def work() -> FetchResult:
        try:
            conn = open_connection(target, address)
        except ssl.SSLCertVerificationError as exc:
            raise MailError("Das Zertifikat des Mailservers ist ungültig.") from exc
        except (OSError, imaplib.IMAP4.error) as exc:
            raise MailError("Der Mailserver ist nicht erreichbar.") from exc
        try:
            return _fetch(conn, target, uidvalidity, last_uid, limit, today)
        except (imaplib.IMAP4.abort, OSError) as exc:
            raise MailError("Die Verbindung zum Mailserver ist abgebrochen.") from exc
        except imaplib.IMAP4.error as exc:
            raise MailError("Das Postfach antwortet nicht wie erwartet.") from exc
        finally:
            with contextlib.suppress(Exception):
                conn.logout()

    return await anyio.to_thread.run_sync(work)


# --- Speichern ------------------------------------------------------------------------------


def target_for(account: MailAccount, password: str) -> ImapTarget:
    return ImapTarget(
        host=account.imap_host,
        port=account.imap_port,
        security=account.security,
        username=account.username,
        password=password,
        folder=account.folder,
    )


async def apply_result(
    db: AsyncSession,
    account: MailAccount,
    result: FetchResult,
    *,
    tzid: str,
    now: datetime | None = None,
) -> int:
    """Neue Mails speichern (samt Terminvorschlag); liefert, wie viele dazugekommen sind."""
    now = now or datetime.now(UTC)
    if account.uidvalidity is not None and result.uidvalidity != account.uidvalidity:
        await db.execute(delete(MailMessage).where(MailMessage.account_id == account.id))
    account.uidvalidity = result.uidvalidity
    account.last_uid = result.last_uid
    uids = [m.uid for m in result.messages]
    existing = set(
        await db.scalars(
            select(MailMessage.uid).where(
                MailMessage.account_id == account.id, MailMessage.uid.in_(uids)
            )
        )
    )
    fresh: list[MailMessage] = []
    for item in result.messages:
        if item.uid in existing:
            continue
        existing.add(item.uid)
        suggestion = detect(item.invites, item.subject, item.body_text, item.sent_at, tzid, now)
        fresh.append(
            MailMessage(
                account_id=account.id,
                uid=item.uid,
                message_id=item.message_id,
                from_name=item.from_name,
                from_address=item.from_address,
                recipients=item.recipients,
                subject=item.subject,
                sent_at=item.sent_at,
                snippet=item.snippet,
                body_text=item.body_text,
                has_html=item.has_html,
                attachment_count=item.attachment_count,
                truncated=item.truncated,
                is_read=item.seen,
                suggestion=suggestion.to_json() if suggestion else None,
                suggestion_status="pending" if suggestion else None,
            )
        )
    db.add_all(fresh)
    await db.flush()
    if fresh:  # Regeln des Nutzers auf die neuen Mails anwenden
        rules = await enabled_rules(db, account.owner_id)
        owner = await db.get(User, account.owner_id) if rules else None
        if owner is not None:
            await run_rules(db, owner, rules, fresh, now)
            await db.flush()
    count = (
        await db.scalar(
            select(func.count())
            .select_from(MailMessage)
            .where(MailMessage.account_id == account.id)
        )
        or 0
    )
    if count > MAX_STORED:  # älteste Mails entfernen
        oldest = (
            select(MailMessage.id)
            .where(MailMessage.account_id == account.id)
            .order_by(MailMessage.uid.desc())
            .offset(MAX_STORED)
        )
        await db.execute(delete(MailMessage).where(MailMessage.id.in_(oldest)))
        count = MAX_STORED
    account.message_count = count
    return len(fresh)


async def sync_account(
    db: AsyncSession, crypto: Crypto, account: MailAccount, owner: User, *, limit: int = BATCH
) -> int:
    """Einmal abgleichen. Fehler landen in ``last_error``, gespeicherte Mails bleiben."""
    now = datetime.now(UTC)
    account.last_synced_at = now
    added = 0
    try:
        password = crypto.decrypt_str(
            account.password_encrypted, context=password_context(account.id)
        )
        result = await fetch_mailbox(
            target_for(account, password),
            allow_private=owner.is_admin,
            uidvalidity=account.uidvalidity,
            last_uid=account.last_uid,
            limit=limit,
        )
        added = await apply_result(db, account, result, tzid=owner.timezone)
        account.last_success_at = now
        account.last_error = None
    except MailError as exc:
        account.last_error = exc.message[:300]
    except DecryptionError:
        account.last_error = "Das gespeicherte Passwort lässt sich nicht entschlüsseln."
    await db.commit()
    return added


async def sync_due_accounts(db: AsyncSession, crypto: Crypto) -> int:
    """Für den Worker: alle fälligen Postfächer abgleichen."""
    now = datetime.now(UTC)
    accounts = list(await db.scalars(select(MailAccount).where(MailAccount.enabled.is_(True))))
    done = 0
    for account in accounts:
        due = (
            account.last_synced_at is None
            or account.last_synced_at + timedelta(minutes=account.refresh_minutes) <= now
        )
        if not due:
            continue
        owner = await db.get(User, account.owner_id)
        if owner is None or not owner.is_active:
            continue
        try:
            await sync_account(db, crypto, account, owner)
        except Exception:  # ein kaputtes Postfach darf die anderen nicht aufhalten
            log.exception("Abgleich von Postfach %s fehlgeschlagen", account.id)
            await db.rollback()
        done += 1
    return done
