"""Zentrale Autorisierung: ``can(user, action, obj)``.

Jede Route prüft Objekte ausschließlich über dieses Modul. Listen und Suche filtern
über ``visible_areas()``. Nicht sichtbare Objekte ergeben 404 (keine Existenz-Leaks),
sichtbare, aber nicht erlaubte Aktionen ergeben 403.
"""

from __future__ import annotations

import uuid
from enum import StrEnum

from fastapi import HTTPException, status
from sqlalchemy import ColumnElement, or_, select

from app.models import Area, AreaMember, Event, Task, User


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class Action(StrEnum):
    VIEW = "view"
    CREATE = "create"
    EDIT = "edit"
    DELETE = "delete"
    MANAGE = "manage"


PERMISSIONS: dict[Role, frozenset[Action]] = {
    Role.OWNER: frozenset(Action),
    Role.ADMIN: frozenset(Action),
    Role.MEMBER: frozenset({Action.VIEW, Action.CREATE, Action.EDIT, Action.DELETE}),
    Role.VIEWER: frozenset({Action.VIEW}),
}

Protected = Area | Task | Event


def _area_of(obj: Protected) -> Area:
    return obj if isinstance(obj, Area) else obj.area


def member_roles(user: User) -> dict[uuid.UUID, str]:
    """Rollen in geteilten Bereichen – je Anfrage beim Anmelden geladen (api/deps.py)."""
    roles: dict[uuid.UUID, str] = getattr(user, "area_roles", None) or {}
    return roles


def role_for(user: User, obj: Protected) -> Role | None:
    area = _area_of(obj)
    if area.owner_id == user.id:
        return Role.OWNER
    shared = member_roles(user).get(area.id)
    return Role(shared) if shared else None


def can(user: User, action: Action, obj: Protected) -> bool:
    role = role_for(user, obj)
    return role is not None and action in PERMISSIONS[role]


def authorize(user: User, action: Action, obj: Protected | None) -> None:
    """Wirft 404, wenn das Objekt fehlt oder unsichtbar ist, 403 bei fehlendem Recht."""
    if obj is None or not can(user, Action.VIEW, obj):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nicht gefunden.")
    if not can(user, action, obj):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Keine Berechtigung.")


def visible_areas(user: User) -> ColumnElement[bool]:
    """SQL-Bedingung für alle Bereiche, die ``user`` sehen darf: eigene und geteilte."""
    shared = select(AreaMember.area_id).where(AreaMember.user_id == user.id)
    return or_(Area.owner_id == user.id, Area.id.in_(shared))
