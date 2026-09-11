"""Postfächer per OAuth (Google, Microsoft).

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-12 01:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "mail_accounts",
        sa.Column("auth", sa.String(length=10), server_default="password", nullable=False),
    )
    op.add_column("mail_accounts", sa.Column("oauth_provider", sa.String(length=20), nullable=True))
    op.create_check_constraint(
        op.f("ck_mail_accounts_auth"), "mail_accounts", "auth in ('password', 'oauth2')"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_mail_accounts_auth"), "mail_accounts", type_="check")
    op.drop_column("mail_accounts", "oauth_provider")
    op.drop_column("mail_accounts", "auth")
