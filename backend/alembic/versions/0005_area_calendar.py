"""Kalenderansicht je Bereich: Wochentage und sichtbare Stunden.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-11 13:40:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "areas", sa.Column("week_days", sa.SmallInteger(), nullable=False, server_default="127")
    )
    op.add_column(
        "areas", sa.Column("day_start", sa.SmallInteger(), nullable=False, server_default="0")
    )
    op.add_column(
        "areas", sa.Column("day_end", sa.SmallInteger(), nullable=False, server_default="24")
    )
    op.create_check_constraint(op.f("ck_areas_week_days"), "areas", "week_days between 1 and 127")
    op.create_check_constraint(
        op.f("ck_areas_day_hours"),
        "areas",
        "day_start >= 0 and day_end <= 24 and day_start < day_end",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_areas_day_hours"), "areas", type_="check")
    op.drop_constraint(op.f("ck_areas_week_days"), "areas", type_="check")
    op.drop_column("areas", "day_end")
    op.drop_column("areas", "day_start")
    op.drop_column("areas", "week_days")
