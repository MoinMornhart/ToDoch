"""Zwei-Wege-Abgleich mit Online-Kalendern (Google Kalender).

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-12 03:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamp(name: str) -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(
        name, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "calendar_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("area_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("account_email", sa.String(length=320), nullable=False),
        sa.Column("remote_calendar_id", sa.String(length=255), nullable=False),
        sa.Column("token_encrypted", sa.Text(), nullable=False),
        sa.Column("sync_token", sa.String(length=1000), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=300), nullable=True),
        sa.Column("event_count", sa.Integer(), nullable=False),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        sa.CheckConstraint("provider in ('google')", name=op.f("ck_calendar_connections_provider")),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_calendar_connections_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["area_id"],
            ["areas.id"],
            name=op.f("fk_calendar_connections_area_id_areas"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_calendar_connections")),
    )
    op.create_index(op.f("ix_calendar_connections_owner_id"), "calendar_connections", ["owner_id"])
    op.create_table(
        "calendar_tombstones",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("remote_id", sa.String(length=1024), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["calendar_connections.id"],
            name=op.f("fk_calendar_tombstones_connection_id_calendar_connections"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_calendar_tombstones")),
    )
    op.create_index(
        op.f("ix_calendar_tombstones_connection_id"), "calendar_tombstones", ["connection_id"]
    )
    op.add_column("events", sa.Column("connection_id", sa.Uuid(), nullable=True))
    op.add_column("events", sa.Column("remote_id", sa.String(length=1024), nullable=True))
    op.add_column("events", sa.Column("remote_hash", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_events_connection_id"), "events", ["connection_id"])
    op.create_foreign_key(
        op.f("fk_events_connection_id_calendar_connections"),
        "events",
        "calendar_connections",
        ["connection_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_events_connection_remote", "events", ["connection_id", "remote_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_events_connection_remote", "events", type_="unique")
    op.drop_constraint(
        op.f("fk_events_connection_id_calendar_connections"), "events", type_="foreignkey"
    )
    op.drop_index(op.f("ix_events_connection_id"), table_name="events")
    op.drop_column("events", "remote_hash")
    op.drop_column("events", "remote_id")
    op.drop_column("events", "connection_id")
    op.drop_index(op.f("ix_calendar_tombstones_connection_id"), table_name="calendar_tombstones")
    op.drop_table("calendar_tombstones")
    op.drop_index(op.f("ix_calendar_connections_owner_id"), table_name="calendar_connections")
    op.drop_table("calendar_connections")
