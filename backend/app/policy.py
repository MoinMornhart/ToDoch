"""Zentrale Autorisierung: ``can(user, action, obj)``.

Jede Route prüft Objekte ausschließlich über dieses Modul. Listen und Suche filtern
über ``visible_areas()``. Nicht sichtbare Objekte ergeben 404 (keine Existenz-Leaks),
sichtbare, aber nicht erlaubte Aktionen ergeben 403.
"""

from __future__ import annotations

from enum import StrEnum

from fastapi import HTTPException, status
from sqlalchemy import ColumnElement

from app.models import Area, Event, Task, User


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


def role_for(user: User, obj: Protected) -> Role | None:
    area = _area_of(obj)
    if area.owner_id == user.id:
        return Role.OWNER
    return None


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
    """SQL-Bedingung für alle Bereiche, die ``user`` sehen darf."""
    return Area.owner_id == user.id
