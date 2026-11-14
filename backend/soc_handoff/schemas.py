"""Public response shapes for the handoff API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AuditEvent(BaseModel):
    kind: str
    actor: str
    at: datetime
    reason: str
    agent: str | None = None
    action: str | None = None
    destination: str | None = None
    policy_version: int | None = None
    ticket_id: str | None = None


class Approval(BaseModel):
    actor: str
    policy_version: int
    at: datetime


class RunResponse(BaseModel):
    id: str = Field(alias="_id")
    status: Literal["proposed", "approved", "creating", "created", "canceled", "closing", "closed"]
    actor: str
    revision: int
    alert_id: str
    finding_id: str
    finding_title: str
    title: str
    evidence: str
    action: str
    destination: str
    events: list[AuditEvent]
    approval: Approval | None = None
    ticket_id: str | None = None
