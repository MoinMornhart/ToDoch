"""Bereiche teilen: Mitglieder mit Rollen, Einladungslinks, Verlassen.

Einladungen sind Links mit einem zufälligen Geheimnis hinter ``#`` (landet nie in
Server-Protokollen); gespeichert wird nur der SHA-256. Ein Link gilt einmal und 7 Tage – so muss
niemand E-Mail-Adressen eingeben, und es lässt sich nicht herausfinden, wer ein Konto hat.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import func, select

from app.api.areas import area_out
from app.api.deps import DB, CurrentUser, Res, client_ip, load_member_roles
from app.models import Area, AreaInvite, AreaMember, User
from app.policy import Action, authorize
from app.schemas.area_members import (
    InviteCreatedOut,
    InviteIn,
    InviteOut,
    InvitePreviewOut,
    InviteTokenIn,
    MemberOut,
    MemberPatch,
)
from app.schemas.areas import AreaOut
from app.services import audit

router = APIRouter(prefix="/api", tags=["areas"])

INVITE_DAYS = 7
MAX_MEMBERS = 50
MAX_INVITES = 20
INVALID = "Die Einladung ist ungültig oder abgelaufen."


def _hash(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def _invite_out(invite: AreaInvite) -> InviteOut:
    return InviteOut(
        id=invite.id, role=invite.role, created_at=invite.created_at, expires_at=invite.expires_at
    )


async def _area(db: DB, user: User, area_id: uuid.UUID, action: Action) -> Area:
    area = await db.get(Area, area_id)
    authorize(user, action, area)
    assert area is not None
    return area


async def _member(db: DB, area: Area, member_id: uuid.UUID) -> AreaMember:
    member = await db.get(AreaMember, member_id)
    if member is None or member.area_id != area.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nicht gefunden.")
    return member


async def _valid_invite(db: DB, token: str) -> AreaInvite:
    invite = await db.scalar(select(AreaInvite).where(AreaInvite.token_hash == _hash(token)))
    if invite is None or invite.expires_at <= datetime.now(UTC):
        raise HTTPException(status.HTTP_404_NOT_FOUND, INVALID)
    return invite


# --- Mitglieder ---------------------------------------------------------------------------


@router.get("/areas/{area_id}/members", response_model=list[MemberOut])
async def list_members(area_id: uuid.UUID, db: DB, user: CurrentUser) -> list[MemberOut]:
    area = await _area(db, user, area_id, Action.VIEW)
    owner = await db.get(User, area.owner_id)
    result = [
        MemberOut(
            id=None,
            display_name=owner.display_name if owner else "?",
            role="owner",
            you=area.owner_id == user.id,
        )
    ]
    rows = await db.scalars(
        select(AreaMember).where(AreaMember.area_id == area.id).order_by(AreaMember.created_at)
    )
    for member in rows.unique():
        result.append(
            MemberOut(
                id=member.id,
                display_name=member.user.display_name,
                role=member.role,
                you=member.user_id == user.id,
            )
        )
    return result


@router.patch("/areas/{area_id}/members/{member_id}", response_model=MemberOut)
async def change_role(
    area_id: uuid.UUID,
    member_id: uuid.UUID,
    body: MemberPatch,
    request: Request,
    db: DB,
    user: CurrentUser,
) -> MemberOut:
    area = await _area(db, user, area_id, Action.MANAGE)
    member = await _member(db, area, member_id)
    if body.role is not None and body.role != member.role:
        member.role = body.role
        audit.record(
            db,
            "area.member_role",
            user_id=user.id,
            ip=client_ip(request),
            area=str(area.id),
            member=str(member.user_id),
            role=body.role,
        )
    await db.commit()
    return MemberOut(
        id=member.id,
        display_name=member.user.display_name,
        role=member.role,
        you=member.user_id == user.id,
    )


@router.delete("/areas/{area_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    area_id: uuid.UUID, member_id: uuid.UUID, request: Request, db: DB, user: CurrentUser
) -> None:
    """Andere entfernen nur mit Verwaltungsrecht – sich selbst jederzeit (Verlassen)."""
    area = await _area(db, user, area_id, Action.VIEW)
    member = await _member(db, area, member_id)
    if member.user_id != user.id:
        authorize(user, Action.MANAGE, area)
    await db.delete(member)
    audit.record(
        db,
        "area.member_removed",
        user_id=user.id,
        ip=client_ip(request),
        area=str(area.id),
        member=str(member.user_id),
    )
    await db.commit()


@router.delete("/areas/{area_id}/membership", status_code=status.HTTP_204_NO_CONTENT)
async def leave_area(area_id: uuid.UUID, request: Request, db: DB, user: CurrentUser) -> None:
    """Einen geteilten Bereich verlassen."""
    member = await db.scalar(
        select(AreaMember).where(AreaMember.area_id == area_id, AreaMember.user_id == user.id)
    )
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nicht gefunden.")
    await db.delete(member)
    audit.record(db, "area.left", user_id=user.id, ip=client_ip(request), area=str(area_id))
    await db.commit()


# --- Einladungen --------------------------------------------------------------------------


@router.get("/areas/{area_id}/invites", response_model=list[InviteOut])
async def list_invites(area_id: uuid.UUID, db: DB, user: CurrentUser) -> list[InviteOut]:
    area = await _area(db, user, area_id, Action.MANAGE)
    rows = await db.scalars(
        select(AreaInvite)
        .where(AreaInvite.area_id == area.id, AreaInvite.expires_at > datetime.now(UTC))
        .order_by(AreaInvite.created_at)
    )
    return [_invite_out(invite) for invite in rows.unique()]


@router.post(
    "/areas/{area_id}/invites",
    response_model=InviteCreatedOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_invite(
    area_id: uuid.UUID,
    request: Request,
    db: DB,
    res: Res,
    user: CurrentUser,
    body: InviteIn | None = None,
) -> InviteCreatedOut:
    area = await _area(db, user, area_id, Action.MANAGE)
    await res.limiter.enforce("area-invite", str(user.id), limit=30, window=3600)
    role = body.role if body else "member"
    now = datetime.now(UTC)
    active = await db.scalar(
        select(func.count())
        .select_from(AreaInvite)
        .where(AreaInvite.area_id == area.id, AreaInvite.expires_at > now)
    )
    if (active or 0) >= MAX_INVITES:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Höchstens {MAX_INVITES} Einladungen möglich."
        )
    token = secrets.token_urlsafe(32)
    invite = AreaInvite(
        area_id=area.id,
        area=area,
        created_by=user.id,
        role=role,
        token_hash=_hash(token),
        created_at=now,
        expires_at=now + timedelta(days=INVITE_DAYS),
    )
    db.add(invite)
    audit.record(
        db,
        "area.invite_created",
        user_id=user.id,
        ip=client_ip(request),
        area=str(area.id),
        role=role,
    )
    await db.commit()
    return InviteCreatedOut(invite=_invite_out(invite), url=f"{res.settings.origin}/invite#{token}")


@router.delete("/areas/{area_id}/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invite(
    area_id: uuid.UUID, invite_id: uuid.UUID, db: DB, user: CurrentUser
) -> None:
    area = await _area(db, user, area_id, Action.MANAGE)
    invite = await db.get(AreaInvite, invite_id)
    if invite is None or invite.area_id != area.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nicht gefunden.")
    await db.delete(invite)
    await db.commit()


@router.post("/invites/preview", response_model=InvitePreviewOut)
async def preview_invite(
    body: InviteTokenIn, db: DB, res: Res, user: CurrentUser
) -> InvitePreviewOut:
    """Wohin führt die Einladung? (Geheimnis im Body, nicht in der Adresse.)"""
    await res.limiter.enforce("invite-open", str(user.id), limit=30, window=600)
    invite = await _valid_invite(db, body.token)
    inviter = await db.get(User, invite.created_by)
    already = invite.area.owner_id == user.id or invite.area_id in (
        getattr(user, "area_roles", None) or {}
    )
    return InvitePreviewOut(
        area_name=invite.area.name,
        role=invite.role,
        invited_by=inviter.display_name if inviter else "?",
        already_member=already,
    )


@router.post("/invites/accept", response_model=AreaOut)
async def accept_invite(
    body: InviteTokenIn, request: Request, db: DB, res: Res, user: CurrentUser
) -> AreaOut:
    await res.limiter.enforce("invite-open", str(user.id), limit=30, window=600)
    invite = await _valid_invite(db, body.token)
    area = invite.area
    if area.owner_id == user.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Das ist dein eigener Bereich.")
    existing = await db.scalar(
        select(AreaMember).where(AreaMember.area_id == area.id, AreaMember.user_id == user.id)
    )
    if existing is None:
        count = await db.scalar(
            select(func.count()).select_from(AreaMember).where(AreaMember.area_id == area.id)
        )
        if (count or 0) >= MAX_MEMBERS:
            raise HTTPException(
                status.HTTP_409_CONFLICT, f"Höchstens {MAX_MEMBERS} Mitglieder möglich."
            )
        db.add(AreaMember(area_id=area.id, user_id=user.id, role=invite.role))
    await db.delete(invite)  # jeder Link gilt genau einmal
    audit.record(
        db,
        "area.member_joined",
        user_id=user.id,
        ip=client_ip(request),
        area=str(area.id),
        role=invite.role,
    )
    await db.commit()
    await load_member_roles(db, user)
    return area_out(area, user)
