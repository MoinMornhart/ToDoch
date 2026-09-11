"""Abonnierte Kalender (ICS), z. B. aus Streamo.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-11 17:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "external_calendars",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("area_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("url_encrypted", sa.Text(), nullable=False),
        sa.Column("url_host", sa.String(length=255), nullable=False),
        sa.Column("refresh_minutes", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("etag", sa.String(length=200), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=300), nullable=True),
        sa.Column("event_count", sa.Integer(), nullable=False),
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
        sa.CheckConstraint(
            "refresh_minutes between 15 and 1440",
            name=op.f("ck_external_calendars_refresh_minutes"),
        ),
        sa.ForeignKeyConstraint(
            ["area_id"],
            ["areas.id"],
            name=op.f("fk_external_calendars_area_id_areas"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_external_calendars_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_external_calendars")),
    )
    op.create_index(op.f("ix_external_calendars_owner_id"), "external_calendars", ["owner_id"])
    op.add_column("events", sa.Column("calendar_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_events_calendar_id"), "events", ["calendar_id"])
    op.create_foreign_key(
        op.f("fk_events_calendar_id_external_calendars"),
        "events",
        "external_calendars",
        ["calendar_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_events_calendar_id_external_calendars"), "events", type_="foreignkey"
    )
    op.drop_index(op.f("ix_events_calendar_id"), table_name="events")
    op.drop_column("events", "calendar_id")
    op.drop_index(op.f("ix_external_calendars_owner_id"), table_name="external_calendars")
    op.drop_table("external_calendars")
