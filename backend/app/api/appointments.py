"""Telefontermin: Kontakt, Termin und Folgeaufgabe in einem Schritt anlegen."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, status

from app.api.contacts import apply_contact, contact_out, create_contact_row, load_contact
from app.api.deps import DB, CurrentUser, user_today
from app.api.events import conflicts_out, create_event_row, event_out
from app.api.tasks import task_out
from app.models import Contact, Task
from app.schemas.appointments import AppointmentIn, AppointmentOut

router = APIRouter(prefix="/api/appointments", tags=["appointments"])


@router.post("", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
async def create_appointment(body: AppointmentIn, db: DB, user: CurrentUser) -> AppointmentOut:
    contact: Contact | None = None
    if body.contact_id is not None:
        contact = await load_contact(db, user, body.contact_id)
        if body.contact is not None:
            apply_contact(contact, body.contact)  # Angaben aktuell halten
    elif body.contact is not None:
        contact = await create_contact_row(db, user, body.contact)
    if contact is not None:
        contact.use_count += 1
        contact.last_used_at = datetime.now(UTC)

    event_body = body.event.model_copy(update={"contact_id": contact.id if contact else None})
    event, conflicts = await create_event_row(db, user, event_body, source="form")

    task: Task | None = None
    if body.follow_up is not None:
        # Nie in der Vergangenheit fällig – kurzfristige Termine landen auf „Heute“.
        due = max(
            body.event.start_date - timedelta(days=body.follow_up.days_before), user_today(user)
        )
        task = Task(
            area_id=event.area_id,
            area=event.area,
            created_by=user.id,
            title=body.follow_up.title,
            due_date=min(due, body.event.start_date),
            priority=body.follow_up.priority,
            tags=list(event.tags),
            source="form",
            event_id=event.id,
            checklist=[],
        )
        db.add(task)
    await db.commit()
    return AppointmentOut(
        event=event_out(event, user.timezone, tasks=[task] if task else []),
        task=task_out(task) if task else None,
        contact=contact_out(contact) if contact else None,
        conflicts=conflicts_out(conflicts, user.timezone),
    )
