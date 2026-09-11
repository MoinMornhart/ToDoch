"""E-Mail-Postfächer (IMAP) und abgeholte Mails.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-11 22:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamp(name: str) -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(
        name, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "mail_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("imap_host", sa.String(length=255), nullable=False),
        sa.Column("imap_port", sa.Integer(), nullable=False),
        sa.Column("security", sa.String(length=10), nullable=False),
        sa.Column("username", sa.String(length=320), nullable=False),
        sa.Column("password_encrypted", sa.Text(), nullable=False),
        sa.Column("folder", sa.String(length=200), nullable=False),
        sa.Column("refresh_minutes", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("uidvalidity", sa.BigInteger(), nullable=True),
        sa.Column("last_uid", sa.BigInteger(), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=300), nullable=True),
        sa.Column("message_count", sa.Integer(), nullable=False),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        sa.CheckConstraint(
            "refresh_minutes between 5 and 1440", name=op.f("ck_mail_accounts_refresh_minutes")
        ),
        sa.CheckConstraint(
            "security in ('ssl', 'starttls')", name=op.f("ck_mail_accounts_security")
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_mail_accounts_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mail_accounts")),
    )
    op.create_index(op.f("ix_mail_accounts_owner_id"), "mail_accounts", ["owner_id"])
    op.create_table(
        "mail_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("uid", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.String(length=500), nullable=False),
        sa.Column("from_name", sa.String(length=200), nullable=False),
        sa.Column("from_address", sa.String(length=320), nullable=False),
        sa.Column("recipients", sa.String(length=1000), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        _timestamp("received_at"),
        sa.Column("snippet", sa.String(length=300), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("has_html", sa.Boolean(), nullable=False),
        sa.Column("attachment_count", sa.Integer(), nullable=False),
        sa.Column("truncated", sa.Boolean(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["mail_accounts.id"],
            name=op.f("fk_mail_messages_account_id_mail_accounts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            name=op.f("fk_mail_messages_task_id_tasks"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mail_messages")),
        sa.UniqueConstraint("account_id", "uid", name="uq_mail_messages_account_uid"),
    )
    op.create_index("ix_mail_messages_account_sent", "mail_messages", ["account_id", "sent_at"])


def downgrade() -> None:
    op.drop_index("ix_mail_messages_account_sent", table_name="mail_messages")
    op.drop_table("mail_messages")
    op.drop_index(op.f("ix_mail_accounts_owner_id"), table_name="mail_accounts")
    op.drop_table("mail_accounts")
