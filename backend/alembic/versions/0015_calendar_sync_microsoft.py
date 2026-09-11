"""Kalender-Abgleich auch mit Outlook (Microsoft Graph).

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-12 04:30:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAME = "ck_calendar_connections_provider"


def upgrade() -> None:
    op.drop_constraint(op.f(NAME), "calendar_connections", type_="check")
    op.create_check_constraint(
        op.f(NAME), "calendar_connections", "provider in ('google', 'microsoft')"
    )


def downgrade() -> None:
    op.execute("DELETE FROM calendar_connections WHERE provider = 'microsoft'")
    op.drop_constraint(op.f(NAME), "calendar_connections", type_="check")
    op.create_check_constraint(op.f(NAME), "calendar_connections", "provider in ('google')")
