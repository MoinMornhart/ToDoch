"""Geteilte Bereiche: Mitglieder mit Rollen und Einladungslinks.

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-12 08:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLE_CHECK = "role in ('admin', 'member', 'viewer')"


def upgrade() -> None:
    op.create_table(
        "area_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("area_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(ROLE_CHECK, name=op.f("ck_area_members_role")),
        sa.ForeignKeyConstraint(
            ["area_id"],
            ["areas.id"],
            name=op.f("fk_area_members_area_id_areas"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_area_members_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_area_members")),
        sa.UniqueConstraint("area_id", "user_id", name="uq_area_members_area_user"),
    )
    op.create_index(op.f("ix_area_members_area_id"), "area_members", ["area_id"])
    op.create_index(op.f("ix_area_members_user_id"), "area_members", ["user_id"])
    op.create_table(
        "area_invites",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("area_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(ROLE_CHECK, name=op.f("ck_area_invites_role")),
        sa.ForeignKeyConstraint(
            ["area_id"],
            ["areas.id"],
            name=op.f("fk_area_invites_area_id_areas"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_area_invites_created_by_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_area_invites")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_area_invites_token_hash")),
    )
    op.create_index(op.f("ix_area_invites_area_id"), "area_invites", ["area_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_area_invites_area_id"), table_name="area_invites")
    op.drop_table("area_invites")
    op.drop_index(op.f("ix_area_members_user_id"), table_name="area_members")
    op.drop_index(op.f("ix_area_members_area_id"), table_name="area_members")
    op.drop_table("area_members")
