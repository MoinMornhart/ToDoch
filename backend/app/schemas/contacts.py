from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, StringConstraints

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Company = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
Phone = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=50, pattern=r"^[0-9+()/.\- ]*$")
]
Address = Annotated[str, Field(max_length=1000)]


class ContactIn(BaseModel):
    name: Name
    company: Company = ""
    phone: Phone = ""
    email: EmailStr | None = None
    address: Address = ""


class ContactPatch(BaseModel):
    name: Name | None = None
    company: Company | None = None
    phone: Phone | None = None
    email: EmailStr | None = None
    address: Address | None = None


class ContactOut(BaseModel):
    id: uuid.UUID
    name: str
    company: str
    phone: str
    email: str
    address: str
    use_count: int
    last_used_at: datetime | None
