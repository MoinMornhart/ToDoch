from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.area import Area
from app.models.base import Base, Timestamps, UUIDPk, utcnow
from app.models.user import User

ROLES = ("admin", "member", "viewer")


class AreaMember(UUIDPk, Timestamps, Base):
    """Jemand, mit dem ein Bereich geteilt ist. Der Besitzer steht nicht hier (areas.owner_id)."""

    __tablename__ = "area_members"
    __table_args__ = (
        UniqueConstraint("area_id", "user_id", name="uq_area_members_area_user"),
        CheckConstraint("role in ('admin', 'member', 'viewer')", name="role"),
    )

    area_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("areas.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(10), default="member")

    user: Mapped[User] = relationship(lazy="joined", innerjoin=True)


class AreaInvite(UUIDPk, Base):
    """Einladungslink – gespeichert wird nur der SHA-256 des Geheimnisses; gilt einmal, 7 Tage."""

    __tablename__ = "area_invites"
    __table_args__ = (CheckConstraint("role in ('admin', 'member', 'viewer')", name="role"),)

    area_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("areas.id", ondelete="CASCADE"), index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(10), default="member")
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    expires_at: Mapped[datetime]

    area: Mapped[Area] = relationship(lazy="joined", innerjoin=True)
