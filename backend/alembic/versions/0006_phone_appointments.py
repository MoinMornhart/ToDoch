"""Telefontermine: Kontakte, Angaben zur Vereinbarung und Aufgaben mit Terminbezug.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-11 14:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("company", sa.String(length=200), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("use_count", sa.Integer(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_contacts_owner_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contacts")),
    )
    op.create_index("ix_contacts_owner_name", "contacts", ["owner_id", "name"])

    op.add_column("events", sa.Column("contact_id", sa.Uuid(), nullable=True))
    op.add_column("events", sa.Column("channel", sa.String(length=12), nullable=True))
    op.add_column("events", sa.Column("agreed_on", sa.Date(), nullable=True))
    op.add_column(
        "events",
        sa.Column("agreed_with", sa.String(length=200), nullable=False, server_default=""),
    )
    op.add_column(
        "events", sa.Column("priority", sa.SmallInteger(), nullable=False, server_default="0")
    )
    op.create_index(op.f("ix_events_contact_id"), "events", ["contact_id"])
    op.create_foreign_key(
        op.f("fk_events_contact_id_contacts"),
        "events",
        "contacts",
        ["contact_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        op.f("ck_events_channel"),
        "events",
        "channel is null or channel in ('phone', 'in_person', 'mail', 'other')",
    )
    op.create_check_constraint(op.f("ck_events_priority"), "events", "priority between 0 and 3")

    op.add_column("tasks", sa.Column("event_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_tasks_event_id"), "tasks", ["event_id"])
    op.create_foreign_key(
        op.f("fk_tasks_event_id_events"),
        "tasks",
        "events",
        ["event_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_tasks_event_id_events"), "tasks", type_="foreignkey")
    op.drop_index(op.f("ix_tasks_event_id"), table_name="tasks")
    op.drop_column("tasks", "event_id")

    op.drop_constraint(op.f("ck_events_priority"), "events", type_="check")
    op.drop_constraint(op.f("ck_events_channel"), "events", type_="check")
    op.drop_constraint(op.f("fk_events_contact_id_contacts"), "events", type_="foreignkey")
    op.drop_index(op.f("ix_events_contact_id"), table_name="events")
    for column in ("priority", "agreed_with", "agreed_on", "channel", "contact_id"):
        op.drop_column("events", column)

    op.drop_index("ix_contacts_owner_name", table_name="contacts")
    op.drop_table("contacts")
