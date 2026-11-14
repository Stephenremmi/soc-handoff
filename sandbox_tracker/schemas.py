"""Public request and response shapes for tracker tickets."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class TicketCreate(BaseModel):
    run_id: UUID
    title: str = Field(min_length=1, max_length=180)
    alert_id: str = Field(pattern=r"^SOC-\d+$")
    evidence: str = Field(min_length=1, max_length=160)


class TicketResponse(TicketCreate):
    id: str
    status: Literal["open", "closed"]
