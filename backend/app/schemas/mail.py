from __future__ import annotations

import uuid
from datetime import date, datetime, time
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

AccountName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
MailAddress = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=320, pattern=r"^[^@\s]+@[^@\s]+$"),
]
Username = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=320)]
MailPassword = Annotated[str, StringConstraints(min_length=1, max_length=500)]
Host = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=255, pattern=r"^[A-Za-z0-9][A-Za-z0-9.:-]*$"
    ),
]
# Druckbares ASCII ohne Anführungszeichen und Backslash, z. B. „INBOX“ oder „[Gmail]/All Mail“
Folder = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=200, pattern=r"^[A-Za-z0-9 ._/&+\[\]-]+$"
    ),
]
Refresh = Annotated[int, Field(ge=5, le=1440)]
Security = Literal["ssl", "starttls"]


class MailAccountIn(BaseModel):
    email: MailAddress
    password: MailPassword
    imap_host: Host
    imap_port: Annotated[int, Field(ge=1, le=65535)] = 993
    security: Security = "ssl"
    username: Username | None = None
    name: AccountName | None = None
    folder: Folder = "INBOX"
    refresh_minutes: Refresh = 15


class MailAccountPatch(BaseModel):
    name: AccountName | None = None
    password: MailPassword | None = None
    refresh_minutes: Refresh | None = None
    enabled: bool | None = None


class MailAccountOut(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    host: str
    port: int
    security: str
    username: str
    folder: str
    refresh_minutes: int
    enabled: bool
    message_count: int
    unread_count: int
    last_synced_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None
    created_at: datetime


class SuggestionOut(BaseModel):
    """Erkannter Termin in der Zeitzone des Nutzers; ``end_date`` ist bei ganztägigen inklusiv."""

    source: str
    title: str
    location: str
    all_day: bool
    start_date: date
    start_time: time | None
    end_date: date
    end_time: time | None
    status: str


class MailMessageOut(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    account_name: str
    from_name: str
    from_address: str
    subject: str
    sent_at: datetime | None
    received_at: datetime
    snippet: str
    is_read: bool
    attachment_count: int
    task_id: uuid.UUID | None
    suggestion: SuggestionOut | None = None
    event_id: uuid.UUID | None = None


class MailMessageDetail(MailMessageOut):
    message_id: str
    recipients: str
    body_text: str
    has_html: bool
    truncated: bool


class MailMessagePatch(BaseModel):
    is_read: bool | None = None


class MailTaskIn(BaseModel):
    area_id: uuid.UUID | None = None
