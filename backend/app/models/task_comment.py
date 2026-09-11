from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamps, UUIDPk
from app.models.user import User


class TaskComment(UUIDPk, Timestamps, Base):
    """Kommentar an einer Aufgabe (Markdown, serverseitig bereinigt angezeigt)."""

    __tablename__ = "task_comments"

    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    body: Mapped[str] = mapped_column(Text)

    author: Mapped[User | None] = relationship(lazy="joined")
