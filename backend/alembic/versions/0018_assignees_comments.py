"""Zuständige Person für Aufgaben und Kommentare.

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-12 09:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("assignee_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_tasks_assignee_id"), "tasks", ["assignee_id"])
    op.create_foreign_key(
        op.f("fk_tasks_assignee_id_users"),
        "tasks",
        "users",
        ["assignee_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "task_comments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
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
            ["task_id"],
            ["tasks.id"],
            name=op.f("fk_task_comments_task_id_tasks"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            name=op.f("fk_task_comments_author_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_comments")),
    )
    op.create_index(op.f("ix_task_comments_task_id"), "task_comments", ["task_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_task_comments_task_id"), table_name="task_comments")
    op.drop_table("task_comments")
    op.drop_constraint(op.f("fk_tasks_assignee_id_users"), "tasks", type_="foreignkey")
    op.drop_index(op.f("ix_tasks_assignee_id"), table_name="tasks")
    op.drop_column("tasks", "assignee_id")
