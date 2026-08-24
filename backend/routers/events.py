"""API router for the audit journal."""

from __future__ import annotations

from fastapi import APIRouter, Query

from models.event_models import AuditEvent
from services.audit_log import audit_log

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("", response_model=list[AuditEvent])
async def list_events(
    limit: int = Query(default=100, ge=1, le=1000),
    slice_id: str | None = Query(default=None, description="Only events for this slice"),
    event_type: str | None = Query(default=None, description="Only this kind of event"),
    severity: str | None = Query(default=None, description="info, warning or error"),
) -> list[AuditEvent]:
    """Read the audit journal, newest first."""
    return audit_log.query(
        limit=limit, slice_id=slice_id, event_type=event_type, severity=severity
    )


@router.get("/summary")
async def event_summary() -> dict:
    """Counts by event type and severity, for the activity panel."""
    return audit_log.summary()
