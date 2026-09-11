"""Regeln für Mails.

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-12 00:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mail_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=True),
        sa.Column("from_contains", sa.String(length=200), nullable=False),
        sa.Column("subject_contains", sa.String(length=200), nullable=False),
        sa.Column("body_contains", sa.String(length=200), nullable=False),
        sa.Column("create_task", sa.Boolean(), nullable=False),
        sa.Column("mark_read", sa.Boolean(), nullable=False),
        sa.Column("area_id", sa.Uuid(), nullable=True),
        sa.Column("priority", sa.SmallInteger(), nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.String(length=40)), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("match_count", sa.Integer(), nullable=False),
        sa.Column("last_matched_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint("priority between 0 and 3", name=op.f("ck_mail_rules_priority")),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_mail_rules_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["mail_accounts.id"],
            name=op.f("fk_mail_rules_account_id_mail_accounts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["area_id"], ["areas.id"], name=op.f("fk_mail_rules_area_id_areas"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mail_rules")),
    )
    op.create_index(op.f("ix_mail_rules_owner_id"), "mail_rules", ["owner_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_mail_rules_owner_id"), table_name="mail_rules")
    op.drop_table("mail_rules")
