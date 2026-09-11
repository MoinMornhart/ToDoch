"""SQLAlchemy-Modelle. Alembic liest ``Base.metadata`` von hier."""

from app.models.area import Area
from app.models.area_member import AreaInvite, AreaMember
from app.models.audit import AuditEvent
from app.models.base import Base
from app.models.calendar import ExternalCalendar
from app.models.calendar_connection import CalendarConnection, CalendarTombstone
from app.models.contact import Contact
from app.models.event import Event
from app.models.feed import FeedToken
from app.models.mail import MailAccount, MailMessage
from app.models.mail_rule import MailRule
from app.models.passkey import Passkey
from app.models.push import PushSubscription, ReminderLog, ServerKey
from app.models.task import ChecklistItem, Task
from app.models.user import RecoveryCode, User, UserSession

__all__ = [
    "Area",
    "AreaInvite",
    "AreaMember",
    "AuditEvent",
    "Base",
    "CalendarConnection",
    "CalendarTombstone",
    "ChecklistItem",
    "Contact",
    "Event",
    "ExternalCalendar",
    "FeedToken",
    "MailAccount",
    "MailMessage",
    "MailRule",
    "Passkey",
    "PushSubscription",
    "RecoveryCode",
    "ReminderLog",
    "ServerKey",
    "Task",
    "User",
    "UserSession",
]
