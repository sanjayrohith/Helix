"""Models for the HELIX audit journal."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from models.slice_models import utcnow

EventType = Literal[
    "slice_provision_requested",
    "slice_created",
    "slice_updated",
    "slice_deleted",
    "slice_suspended",
    "slice_resumed",
    "conflict_detected",
    "sla_violated",
    "sla_recovered",
    "controller_error",
]

EventSeverity = Literal["info", "warning", "error"]


class AuditEvent(BaseModel):
    """An immutable record of something that happened to the network."""

    event_id: str = Field(..., description="Unique event identifier")
    event_type: EventType
    severity: EventSeverity = "info"
    timestamp: datetime = Field(default_factory=utcnow)
    slice_id: str | None = None
    slice_name: str | None = None
    actor: str = Field(default="system", description="Who or what triggered the event")
    summary: str = Field(..., description="One-line human-readable description")
    detail: dict = Field(default_factory=dict, description="Structured event payload")


class AuditQuery(BaseModel):
    """Filter parameters for reading the audit journal."""

    slice_id: str | None = None
    event_type: EventType | None = None
    severity: EventSeverity | None = None
    limit: int = Field(default=100, ge=1, le=1000)
