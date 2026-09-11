"""Kommentare an Aufgaben – lesen darf, wer die Aufgabe sieht; schreiben, wer sie ändern darf."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import DB, CurrentUser
from app.markdown import render_markdown
from app.models import Task, TaskComment, User
from app.policy import Action, authorize
from app.schemas.tasks import CommentIn, CommentOut

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

MAX_COMMENTS = 500


def comment_out(comment: TaskComment, user: User) -> CommentOut:
    return CommentOut(
        id=comment.id,
        author_name=comment.author.display_name if comment.author else "?",
        body=comment.body,
        body_html=render_markdown(comment.body),
        created_at=comment.created_at,
        mine=comment.author_id == user.id,
    )


async def _task(db: DB, user: User, task_id: uuid.UUID, action: Action) -> Task:
    task = await db.get(Task, task_id)
    authorize(user, action, task)
    assert task is not None
    return task


@router.get("/{task_id}/comments", response_model=list[CommentOut])
async def list_comments(task_id: uuid.UUID, db: DB, user: CurrentUser) -> list[CommentOut]:
    task = await _task(db, user, task_id, Action.VIEW)
    rows = await db.scalars(
        select(TaskComment)
        .where(TaskComment.task_id == task.id)
        .order_by(TaskComment.created_at)
        .limit(MAX_COMMENTS)
    )
    return [comment_out(c, user) for c in rows.unique()]


@router.post("/{task_id}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
async def add_comment(
    task_id: uuid.UUID, db: DB, user: CurrentUser, body: CommentIn | None = None
) -> CommentOut:
    task = await _task(db, user, task_id, Action.EDIT)
    if body is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Bitte einen Kommentar eingeben."
        )
    count = await db.scalar(
        select(func.count()).select_from(TaskComment).where(TaskComment.task_id == task.id)
    )
    if (count or 0) >= MAX_COMMENTS:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Höchstens {MAX_COMMENTS} Kommentare möglich."
        )
    comment = TaskComment(task_id=task.id, author_id=user.id, author=user, body=body.body)
    db.add(comment)
    await db.commit()
    return comment_out(comment, user)


@router.delete("/{task_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    task_id: uuid.UUID, comment_id: uuid.UUID, db: DB, user: CurrentUser
) -> None:
    """Eigene Kommentare darf man immer löschen, fremde nur mit Verwaltungsrecht."""
    task = await _task(db, user, task_id, Action.VIEW)
    comment = await db.get(TaskComment, comment_id)
    if comment is None or comment.task_id != task.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nicht gefunden.")
    if comment.author_id != user.id:
        authorize(user, Action.MANAGE, task)
    await db.delete(comment)
    await db.commit()
