"""Terminvorschläge aus Mails.

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-11 23:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "mail_messages",
        sa.Column("suggestion", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "mail_messages", sa.Column("suggestion_status", sa.String(length=12), nullable=True)
    )
    op.add_column("mail_messages", sa.Column("event_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_mail_messages_event_id_events"),
        "mail_messages",
        "events",
        ["event_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        op.f("ck_mail_messages_suggestion_status"),
        "mail_messages",
        "suggestion_status is null or suggestion_status in ('pending', 'accepted', 'dismissed')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_mail_messages_suggestion_status"), "mail_messages", type_="check")
    op.drop_constraint(
        op.f("fk_mail_messages_event_id_events"), "mail_messages", type_="foreignkey"
    )
    op.drop_column("mail_messages", "event_id")
    op.drop_column("mail_messages", "suggestion_status")
    op.drop_column("mail_messages", "suggestion")
