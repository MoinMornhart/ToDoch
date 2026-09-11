from __future__ import annotations

import uuid
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, StringConstraints, model_validator

AreaName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
Color = Annotated[str, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$"), AfterValidator(str.lower)]
Icon = Literal[
    "circle", "briefcase", "home", "heart", "star", "book", "users", "cart", "car",
    "dumbbell", "music", "leaf", "code", "wallet", "plane", "school",
]  # fmt: skip


WeekDays = Annotated[int, Field(ge=1, le=127)]
DayStart = Annotated[int, Field(ge=0, le=23)]
DayEnd = Annotated[int, Field(ge=1, le=24)]


class AreaIn(BaseModel):
    name: AreaName
    color: Color = "#6b7280"
    icon: Icon = "circle"
    sort_order: int = Field(default=0, ge=0, le=10_000)
    week_days: WeekDays = 127
    day_start: DayStart = 0
    day_end: DayEnd = 24

    @model_validator(mode="after")
    def _hours(self) -> AreaIn:
        if self.day_start >= self.day_end:
            raise ValueError("Der Kalender muss vor dem Ende beginnen.")
        return self


class AreaPatch(BaseModel):
    name: AreaName | None = None
    color: Color | None = None
    icon: Icon | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10_000)
    week_days: WeekDays | None = None
    day_start: DayStart | None = None
    day_end: DayEnd | None = None


class AreaOut(BaseModel):
    id: uuid.UUID
    name: str
    color: str
    icon: str
    sort_order: int
    open_count: int
    role: str
    week_days: int
    day_start: int
    day_end: int
