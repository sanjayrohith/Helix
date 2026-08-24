"""API router for slice provisioning and lifecycle management."""

from __future__ import annotations

import time

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response

from core.auth import Principal, ReadScope, WriteScope
from core.config import settings
from core.logging_config import get_logger
from core.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, apply_pagination_headers, paginate
from models.lifecycle_models import (
    SliceScaleRequest,
    SliceStatusChange,
    SliceUpdateRequest,
)
from models.slice_models import (
    SliceConfig,
    SliceDeploymentResult,
    SliceIntent,
    SliceSimulationRequest,
    SliceSimulationResult,
    SliceStats,
)
from routers.websocket import manager
from services.audit_log import audit_log
from services.conflict_detector import conflict_detector
from services.idempotency import provision_idempotency_cache
from services.intent_parser import intent_parser
from services.sdn_controller import sdn_controller
from services.slice_registry import slice_registry
from services.topology import topology_manager

logger = get_logger("api.slices")

router = APIRouter(prefix="/api/slices", tags=["slices"])


@router.post("/provision", response_model=SliceDeploymentResult)
async def provision_slice(
    intent: SliceIntent,
    principal: Principal = WriteScope,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        description=(
            "Optional. Retrying the same key returns the original result "
            "instead of provisioning a second slice."
        ),
    ),
) -> SliceDeploymentResult:
    """Provision a network slice from a natural-language intent.

    Parses the intent, runs admission control, and deploys to the SDN
    controller when no blocking conflict is found. Advisory findings are
    reported but do not prevent deployment.

    A client-supplied Idempotency-Key makes a retried request (a timeout, a
    double-click, a proxy retry) safe: the first request with a given key
    provisions normally, and every subsequent request with that same key -
    scoped to the calling principal, so one caller's key cannot return
    another caller's result - returns the cached result instead of
    provisioning a second slice.
    """
    # Scope the cache key to the principal: two different callers who happen
    # to choose the same idempotency key must not see each other's slices.
    cache_key = f"{principal.actor}:{idempotency_key}" if idempotency_key else None
    if cache_key:
        cached = provision_idempotency_cache.get(cache_key)
        if cached is not None:
            logger.info("Idempotent replay for key '%s'", idempotency_key)
            return cached

    start_time = time.time()

    try:
        outcome = intent_parser.parse(intent.intent)
    except Exception as exc:
        logger.warning("Intent parsing failed: %s", exc)
        raise HTTPException(status_code=400, detail=f"Failed to parse intent: {exc}") from exc

    config = outcome.config
    audit_log.record_slice_event(
        "slice_provision_requested",
        config,
        f"Provisioning requested for '{config.name}'",
        actor=principal.actor,
        detail={"parser": outcome.parser_used, "intent": intent.intent[:500]},
    )

    report = conflict_detector.detect_conflicts(config)

    if report.has_conflict:
        config.status = "conflict"
        audit_log.record_slice_event(
            "conflict_detected",
            config,
            f"'{config.name}' rejected: {report.conflict_type} conflict",
            severity="warning",
            actor=principal.actor,
            detail={
                "conflict_types": [f.conflict_type for f in report.blocking_findings],
                "auto_remediation": report.auto_remediation,
            },
        )
        await manager.broadcast_conflict_detected(
            {
                "slice_name": config.name,
                "conflict_type": report.conflict_type,
                "details": report.details,
                "auto_remediation": report.auto_remediation,
            }
        )
        result = SliceDeploymentResult(
            success=False,
            slice_config=config,
            conflict_report=report,
            deploy_time_seconds=round(time.time() - start_time, 2),
            message=(
                f"Provisioning blocked by {len(report.blocking_findings)} conflict(s). "
                "See conflict_report.auto_remediation for a configuration that would deploy."
            ),
            parser_used=outcome.parser_used,
            parse_fallback_reason=outcome.fallback_reason,
            parse_trace=outcome.trace,
        )
        if cache_key:
            provision_idempotency_cache.set(cache_key, result)
        return result

    try:
        deployed = await sdn_controller.deploy_slice(config)
    except Exception as exc:
        audit_log.record_slice_event(
            "controller_error", config, f"SDN deployment failed: {exc}", severity="error"
        )
        raise HTTPException(
            status_code=502, detail=f"SDN controller deployment failed: {exc}"
        ) from exc

    if deployed:
        config.status = "active"
        slice_registry.add_slice(config)
        placement = topology_manager.place(config)
        if not placement.placed:
            logger.warning("Slice '%s' deployed but unplaced: %s", config.name, placement.explanation)
        audit_log.record_slice_event(
            "slice_created",
            config,
            f"'{config.name}' activated ({config.guaranteed_bitrate_mbps:.0f} Mbps GBR)",
            actor=principal.actor,
            detail={
                "warnings": [f.conflict_type for f in report.warnings],
                "node_id": placement.node_id,
                "placement": placement.explanation,
            },
        )
        await manager.broadcast_slice_created(config.model_dump(mode="json"))
    else:
        config.status = "rejected"

    result = SliceDeploymentResult(
        success=deployed,
        slice_config=config,
        conflict_report=report,
        deploy_time_seconds=round(time.time() - start_time, 2),
        message=(
            f"Slice '{config.name}' deployed and activated."
            if deployed
            else "The SDN controller rejected the slice."
        ),
        parser_used=outcome.parser_used,
        parse_fallback_reason=outcome.fallback_reason,
        parse_trace=outcome.trace,
    )
    if cache_key:
        provision_idempotency_cache.set(cache_key, result)
    return result


@router.post("/simulate", response_model=SliceSimulationResult)
async def simulate_slice(
    request: SliceSimulationRequest, principal: Principal = ReadScope
) -> SliceSimulationResult:
    """Dry-run admission control without touching the network.

    Answers 'would this intent deploy, and if not what would it take?' so an
    operator can iterate on wording before committing to a change window.
    """
    try:
        outcome = intent_parser.parse(request.intent)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse intent: {exc}") from exc

    config = outcome.config
    report = conflict_detector.detect_conflicts(config)
    in_use = slice_registry.get_total_active_bandwidth()

    remediated_config = None
    remediated_report = None
    if request.apply_remediation and report.auto_remediation:
        remediated_config = conflict_detector.apply_remediation(config, report)
        remediated_report = conflict_detector.detect_conflicts(remediated_config)

    return SliceSimulationResult(
        would_deploy=not report.has_conflict,
        slice_config=config,
        conflict_report=report,
        remediated_config=remediated_config,
        remediated_report=remediated_report,
        parser_used=outcome.parser_used,
        capacity_before_mbps=round(in_use, 2),
        capacity_after_mbps=round(in_use + config.guaranteed_bitrate_mbps, 2),
    )


@router.get("", response_model=list[SliceConfig])
async def get_all_slices(
    request: Request,
    response: Response,
    use_case: str | None = Query(default=None, description="Filter by use-case category"),
    location: str | None = Query(default=None, description="Filter by location"),
    status: str | None = Query(default=None, description="Filter by lifecycle status"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    principal: Principal = ReadScope,
) -> list[SliceConfig]:
    """List provisioned slices, optionally filtered.

    Paginated: the body stays a plain array so no existing caller breaks,
    and pagination metadata rides in X-Total-Count and a Link header
    (rel="next"/"prev"/"first"/"last"), the same convention GitHub's API
    uses. A caller that ignores the headers just gets the first
    `limit` (default 100, capped at 500) matches.
    """
    slices = slice_registry.get_all_slices()
    if use_case:
        slices = [s for s in slices if s.use_case.lower() == use_case.lower()]
    if location:
        slices = [s for s in slices if s.location.lower() == location.lower()]
    if status:
        slices = [s for s in slices if s.status == status]

    page = paginate(slices, offset, limit)
    apply_pagination_headers(response, request, page)
    return slices[offset : offset + limit]


@router.get("/stats/summary", response_model=SliceStats)
async def get_slice_stats(principal: Principal = ReadScope) -> SliceStats:
    """Summary counters for the dashboard header."""
    return slice_registry.get_stats()


@router.get("/stats/breakdown")
async def get_slice_breakdown(principal: Principal = ReadScope) -> dict:
    """Group slices by SST, status, use case, location and isolation."""
    return {
        "capacity_mbps": settings.total_bandwidth_mbps,
        "used_mbps": round(slice_registry.get_total_active_bandwidth(), 2),
        "available_mbps": round(slice_registry.get_available_bandwidth(), 2),
        **slice_registry.breakdown(),
    }


@router.get("/{slice_id}", response_model=SliceConfig)
async def get_slice(slice_id: str, principal: Principal = ReadScope) -> SliceConfig:
    """Retrieve a single slice by id."""
    config = slice_registry.get_slice(slice_id)
    if not config:
        raise HTTPException(status_code=404, detail=f"Slice '{slice_id}' not found")
    return config


@router.patch("/{slice_id}", response_model=SliceConfig)
async def update_slice(
    slice_id: str,
    request: SliceUpdateRequest,
    principal: Principal = WriteScope,
) -> SliceConfig:
    """Apply a partial update to a live slice, re-running admission control."""
    existing = slice_registry.get_slice(slice_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Slice '{slice_id}' not found")

    changes = request.changes()
    if not changes:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Validate the post-update shape before committing it.
    candidate_payload = existing.model_dump()
    candidate_payload.update(changes)
    candidate = SliceConfig(**candidate_payload)

    # Exclude the slice's own current reservation from the capacity check.
    freed = existing.guaranteed_bitrate_mbps if existing.status == "active" else 0.0
    in_use = slice_registry.get_total_active_bandwidth() - freed
    if in_use + candidate.guaranteed_bitrate_mbps > settings.total_bandwidth_mbps:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Update rejected: {candidate.guaranteed_bitrate_mbps:.1f} Mbps would exceed "
                f"the {settings.total_bandwidth_mbps:.0f} Mbps capacity "
                f"({in_use:.1f} Mbps used by other slices)."
            ),
        )

    updated = slice_registry.update_slice(slice_id, changes)
    audit_log.record_slice_event(
        "slice_updated",
        updated,
        f"'{updated.name}' updated",
        actor=principal.actor,
        detail={"changes": changes},
    )
    await manager.broadcast_slice_updated(updated.model_dump(mode="json"))
    return updated


@router.post("/{slice_id}/scale", response_model=SliceConfig)
async def scale_slice(
    slice_id: str,
    request: SliceScaleRequest,
    principal: Principal = WriteScope,
) -> SliceConfig:
    """Scale a slice's guaranteed bandwidth by a factor or to an absolute value."""
    existing = slice_registry.get_slice(slice_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Slice '{slice_id}' not found")

    try:
        target = request.resolve(existing.guaranteed_bitrate_mbps)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return await update_slice(
        slice_id,
        SliceUpdateRequest(
            guaranteed_bitrate_mbps=target,
            max_bitrate_mbps=max(target, existing.max_bitrate_mbps),
        ),
        principal=principal,
    )


@router.post("/{slice_id}/suspend", response_model=SliceStatusChange)
async def suspend_slice(
    slice_id: str, principal: Principal = WriteScope
) -> SliceStatusChange:
    """Suspend a slice, releasing its guaranteed bandwidth back to the pool."""
    existing = slice_registry.get_slice(slice_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Slice '{slice_id}' not found")
    if existing.status != "active":
        raise HTTPException(
            status_code=409, detail=f"Only active slices can be suspended (status: {existing.status})"
        )

    updated = slice_registry.set_status(slice_id, "pending")
    audit_log.record_slice_event(
        "slice_suspended",
        updated,
        f"'{updated.name}' suspended",
        severity="warning",
        actor=principal.actor,
    )
    await manager.broadcast_slice_updated(updated.model_dump(mode="json"))
    return SliceStatusChange(
        slice_id=slice_id,
        previous_status="active",
        new_status="pending",
        message=(
            f"'{updated.name}' suspended; "
            f"{updated.guaranteed_bitrate_mbps:.0f} Mbps returned to the pool."
        ),
    )


@router.post("/{slice_id}/resume", response_model=SliceStatusChange)
async def resume_slice(
    slice_id: str, principal: Principal = WriteScope
) -> SliceStatusChange:
    """Reactivate a suspended slice, subject to current capacity."""
    existing = slice_registry.get_slice(slice_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Slice '{slice_id}' not found")
    if existing.status == "active":
        raise HTTPException(status_code=409, detail="Slice is already active")

    report = conflict_detector.detect_conflicts(existing)
    if report.has_conflict:
        raise HTTPException(
            status_code=409, detail=f"Cannot resume: {report.details}"
        )

    previous = existing.status
    updated = slice_registry.set_status(slice_id, "active")
    audit_log.record_slice_event(
        "slice_resumed", updated, f"'{updated.name}' resumed", actor=principal.actor
    )
    await manager.broadcast_slice_updated(updated.model_dump(mode="json"))
    return SliceStatusChange(
        slice_id=slice_id,
        previous_status=previous,
        new_status="active",
        message=f"'{updated.name}' is active again.",
    )


@router.delete("/{slice_id}")
async def delete_slice(slice_id: str, principal: Principal = WriteScope) -> dict:
    """Tear a slice down on the controller and remove it from the registry."""
    existing = slice_registry.get_slice(slice_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Slice '{slice_id}' not found")

    await sdn_controller.remove_slice(slice_id)
    removed = slice_registry.delete_slice(slice_id)
    topology_manager.unplace(slice_id)
    audit_log.record_slice_event(
        "slice_deleted", removed, f"'{removed.name}' deleted", actor=principal.actor
    )
    await manager.broadcast_slice_deleted(slice_id)

    return {
        "message": f"Slice '{removed.name}' deleted",
        "slice_id": slice_id,
        "released_mbps": removed.guaranteed_bitrate_mbps,
    }
