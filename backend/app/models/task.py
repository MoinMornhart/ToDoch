from __future__ import annotations

import uuid
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Computed,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.area import Area
from app.models.base import Base, Timestamps, UUIDPk

TASK_STATUSES = ("open", "done", "archived")


class Task(UUIDPk, Timestamps, Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("status in ('open', 'done', 'archived')", name="status"),
        CheckConstraint("priority between 0 and 3", name="priority"),
        CheckConstraint("due_time is null or due_date is not null", name="time_needs_date"),
        Index("ix_tasks_search", "search_vector", postgresql_using="gin"),
        Index("ix_tasks_tags", "tags", postgresql_using="gin"),
        Index("ix_tasks_area_status_due", "area_id", "status", "due_date"),
    )

    area_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("areas.id", ondelete="CASCADE"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(300))
    notes: Mapped[str] = mapped_column(Text, default="")
    # Fälligkeit als „schwebendes“ Datum in der Zeitzone des Nutzers.
    due_date: Mapped[date | None]
    due_time: Mapped[time | None]
    priority: Mapped[int] = mapped_column(SmallInteger, default=0)
    status: Mapped[str] = mapped_column(String(10), default="open")
    completed_at: Mapped[datetime | None]
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list)
    recurrence: Mapped[str | None] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(20), default="manual")
    sort_order: Mapped[int] = mapped_column(default=0)
    search_vector: Mapped[Any] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(notes, ''))",
            persisted=True,
        ),
        deferred=True,
    )

    area: Mapped[Area] = relationship(lazy="joined", innerjoin=True)
    checklist: Mapped[list[ChecklistItem]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="ChecklistItem.position",
        lazy="selectin",
        passive_deletes=True,
    )


class ChecklistItem(UUIDPk, Base):
    __tablename__ = "task_checklist_items"

    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(String(300))
    done: Mapped[bool] = mapped_column(default=False)
    position: Mapped[int] = mapped_column(default=0)

    task: Mapped[Task] = relationship(back_populates="checklist")
