from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints, model_validator

from app.schemas.tasks import Priority, Tags

RuleName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Condition = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]

NEEDS_CONDITION = "Mindestens eine Bedingung angeben."
NEEDS_ACTION = "Mindestens eine Aktion wählen."


class MailRuleIn(BaseModel):
    name: RuleName
    account_id: uuid.UUID | None = None
    from_contains: Condition = ""
    subject_contains: Condition = ""
    body_contains: Condition = ""
    create_task: bool = True
    mark_read: bool = False
    area_id: uuid.UUID | None = None
    priority: Priority = 0
    tags: Tags = []
    enabled: bool = True

    @model_validator(mode="after")
    def _complete(self) -> MailRuleIn:
        if not (self.from_contains or self.subject_contains or self.body_contains):
            raise ValueError("Mindestens eine Bedingung angeben.")
        if not (self.create_task or self.mark_read):
            raise ValueError("Mindestens eine Aktion wählen.")
        return self


class MailRulePatch(BaseModel):
    name: RuleName | None = None
    account_id: uuid.UUID | None = None
    from_contains: Condition | None = None
    subject_contains: Condition | None = None
    body_contains: Condition | None = None
    create_task: bool | None = None
    mark_read: bool | None = None
    area_id: uuid.UUID | None = None
    priority: Priority | None = None
    tags: Tags | None = None
    enabled: bool | None = None


class MailRuleOut(BaseModel):
    id: uuid.UUID
    name: str
    account_id: uuid.UUID | None
    account_name: str | None
    from_contains: str
    subject_contains: str
    body_contains: str
    create_task: bool
    mark_read: bool
    area_id: uuid.UUID | None
    area_name: str | None
    priority: int
    tags: list[str]
    enabled: bool
    match_count: int
    last_matched_at: datetime | None
    created_at: datetime


class RuleApplyOut(BaseModel):
    matched: int
