"""Kalender-Abgleich auch per CalDAV (Nextcloud, iCloud & Co.).

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-12 06:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAME = "ck_calendar_connections_provider"


def upgrade() -> None:
    op.drop_constraint(op.f(NAME), "calendar_connections", type_="check")
    op.create_check_constraint(
        op.f(NAME), "calendar_connections", "provider in ('google', 'microsoft', 'caldav')"
    )


def downgrade() -> None:
    op.execute("DELETE FROM calendar_connections WHERE provider = 'caldav'")
    op.drop_constraint(op.f(NAME), "calendar_connections", type_="check")
    op.create_check_constraint(
        op.f(NAME), "calendar_connections", "provider in ('google', 'microsoft')"
    )
