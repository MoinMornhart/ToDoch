"""Kontakte: Vorschläge beim Tippen, Bearbeiten und Löschen. Jeder sieht nur seine eigenen."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select

from app.api.deps import DB, CurrentUser
from app.models import Contact, User
from app.schemas.contacts import ContactIn, ContactOut, ContactPatch

router = APIRouter(prefix="/api/contacts", tags=["contacts"])

MAX_CONTACTS = 5000


def contact_out(contact: Contact) -> ContactOut:
    return ContactOut(
        id=contact.id,
        name=contact.name,
        company=contact.company,
        phone=contact.phone,
        email=contact.email,
        address=contact.address,
        use_count=contact.use_count,
        last_used_at=contact.last_used_at,
    )


async def load_contact(db: DB, user: User, contact_id: uuid.UUID) -> Contact:
    """Fremde Kontakte sind wie nicht vorhandene: 404."""
    contact = await db.get(Contact, contact_id)
    if contact is None or contact.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nicht gefunden.")
    return contact


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("", response_model=list[ContactOut])
async def list_contacts(
    db: DB,
    user: CurrentUser,
    q: str = Query(default="", max_length=100),
    limit: int = Query(default=8, ge=1, le=500),
) -> list[ContactOut]:
    query = select(Contact).where(Contact.owner_id == user.id)
    words = q.split()[:5]
    for word in words:
        pattern = f"%{_escape_like(word)}%"
        query = query.where(
            or_(
                Contact.name.ilike(pattern, escape="\\"),
                Contact.company.ilike(pattern, escape="\\"),
                Contact.phone.ilike(pattern, escape="\\"),
                Contact.email.ilike(pattern, escape="\\"),
            )
        )
    if words:
        # Beim Tippen: häufig und kürzlich genutzte Kontakte zuerst
        query = query.order_by(
            Contact.use_count.desc(), Contact.last_used_at.desc().nulls_last(), Contact.name
        )
    else:
        query = query.order_by(func.lower(Contact.name))
    return [contact_out(c) for c in await db.scalars(query.limit(limit))]


async def create_contact_row(db: DB, user: User, body: ContactIn) -> Contact:
    count = await db.scalar(
        select(func.count()).select_from(Contact).where(Contact.owner_id == user.id)
    )
    if (count or 0) >= MAX_CONTACTS:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Höchstens {MAX_CONTACTS} Kontakte möglich.")
    contact = Contact(
        owner_id=user.id,
        name=body.name,
        company=body.company,
        phone=body.phone,
        email=body.email or "",
        address=body.address,
    )
    db.add(contact)
    await db.flush()
    return contact


@router.post("", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
async def create_contact(body: ContactIn, db: DB, user: CurrentUser) -> ContactOut:
    contact = await create_contact_row(db, user, body)
    await db.commit()
    return contact_out(contact)


@router.get("/{contact_id}", response_model=ContactOut)
async def get_contact(contact_id: uuid.UUID, db: DB, user: CurrentUser) -> ContactOut:
    return contact_out(await load_contact(db, user, contact_id))


def apply_contact(contact: Contact, body: ContactPatch | ContactIn) -> None:
    fields = body.model_fields_set
    for name in ("name", "company", "phone", "address"):
        value = getattr(body, name)
        if name in fields and value is not None:
            setattr(contact, name, value)
    if "email" in fields:
        contact.email = body.email or ""


@router.patch("/{contact_id}", response_model=ContactOut)
async def update_contact(
    contact_id: uuid.UUID, body: ContactPatch, db: DB, user: CurrentUser
) -> ContactOut:
    contact = await load_contact(db, user, contact_id)
    apply_contact(contact, body)
    await db.commit()
    return contact_out(contact)


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(contact_id: uuid.UUID, db: DB, user: CurrentUser) -> None:
    """Termine bleiben erhalten, verlieren aber die Verknüpfung (ON DELETE SET NULL)."""
    contact = await load_contact(db, user, contact_id)
    await db.delete(contact)
    await db.commit()
