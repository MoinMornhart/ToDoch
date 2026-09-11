from __future__ import annotations

import uuid
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, StringConstraints

AreaName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
Color = Annotated[str, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$"), AfterValidator(str.lower)]
Icon = Literal[
    "circle", "briefcase", "home", "heart", "star", "book", "users", "cart", "car",
    "dumbbell", "music", "leaf", "code", "wallet", "plane", "school",
]  # fmt: skip


class AreaIn(BaseModel):
    name: AreaName
    color: Color = "#6b7280"
    icon: Icon = "circle"
    sort_order: int = Field(default=0, ge=0, le=10_000)


class AreaPatch(BaseModel):
    name: AreaName | None = None
    color: Color | None = None
    icon: Icon | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10_000)


class AreaOut(BaseModel):
    id: uuid.UUID
    name: str
    color: str
    icon: str
    sort_order: int
    open_count: int
    role: str
