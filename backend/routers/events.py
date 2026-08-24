"""API router for the audit journal."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response

from core.auth import Principal, ReadScope
from core.pagination import apply_pagination_headers, paginate
from models.event_models import AuditEvent
from services.audit_log import audit_log

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("", response_model=list[AuditEvent])
async def list_events(
    request: Request,
    response: Response,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    slice_id: str | None = Query(default=None, description="Only events for this slice"),
    event_type: str | None = Query(default=None, description="Only this kind of event"),
    severity: str | None = Query(default=None, description="info, warning or error"),
    principal: Principal = ReadScope,
) -> list[AuditEvent]:
    """Read the audit journal, newest first.

    Paginated the same way as GET /api/slices: a plain array in the body,
    X-Total-Count and Link headers for paging metadata.
    """
    events = audit_log.query(
        limit=limit, offset=offset, slice_id=slice_id, event_type=event_type, severity=severity
    )
    total = audit_log.count(slice_id=slice_id, event_type=event_type, severity=severity)
    page = paginate(range(total), offset, limit)
    apply_pagination_headers(response, request, page)
    return events


@router.get("/summary")
async def event_summary(principal: Principal = ReadScope) -> dict:
    """Counts by event type and severity, for the activity panel."""
    return audit_log.summary()
