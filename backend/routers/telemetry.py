"""API router for live telemetry and SLA compliance."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from models.telemetry_models import (
    NetworkKpiSummary,
    SlaEvaluation,
    SlaTarget,
    SliceTelemetry,
    TelemetrySnapshot,
)
from services.monitor_loop import monitor_loop
from services.sla_monitor import derive_target, sla_monitor
from services.slice_registry import slice_registry
from services.telemetry import telemetry_engine

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])


@router.get("/summary", response_model=NetworkKpiSummary)
async def network_summary() -> NetworkKpiSummary:
    """Network-wide KPI rollup with SLA status counts."""
    evaluations = sla_monitor.evaluate_all(slice_registry.get_active_slices())
    return telemetry_engine.network_summary(sla_monitor.status_counts(evaluations))


@router.get("/latest", response_model=list[SliceTelemetry])
async def latest_all() -> list[SliceTelemetry]:
    """The most recent sample for every slice being monitored."""
    return list(telemetry_engine.latest_all().values())


@router.get("/sla", response_model=list[SlaEvaluation])
async def sla_all(
    status: str | None = Query(default=None, description="Filter by SLA status"),
) -> list[SlaEvaluation]:
    """SLA verdicts for every active slice."""
    evaluations = sla_monitor.evaluate_all(slice_registry.get_active_slices())
    if status:
        evaluations = [e for e in evaluations if e.status == status]
    return evaluations


@router.get("/violations", response_model=list[SlaEvaluation])
async def sla_violations() -> list[SlaEvaluation]:
    """Only the slices that are at risk or already violating their SLA."""
    evaluations = sla_monitor.evaluate_all(slice_registry.get_active_slices())
    return [e for e in evaluations if e.status in ("at_risk", "violated")]


@router.post("/tick")
async def force_tick() -> dict:
    """Run one sampling interval immediately.

    Useful for demos and tests that should not wait for the next scheduled
    interval to populate the dashboard.
    """
    evaluations = await monitor_loop.tick()
    return {
        "sampled_slices": len(evaluations),
        "ticks": monitor_loop.ticks,
        "sla": sla_monitor.status_counts(evaluations),
    }


@router.get("/{slice_id}", response_model=TelemetrySnapshot)
async def slice_telemetry(
    slice_id: str,
    history: int = Query(default=60, ge=1, le=1000, description="Samples to return"),
) -> TelemetrySnapshot:
    """Latest sample, SLA verdict and recent history for one slice."""
    config = slice_registry.get_slice(slice_id)
    if not config:
        raise HTTPException(status_code=404, detail=f"Slice '{slice_id}' not found")

    return TelemetrySnapshot(
        slice_id=slice_id,
        slice_name=config.name,
        latest=telemetry_engine.latest(slice_id),
        sla=sla_monitor.evaluate(config),
        history=telemetry_engine.history(slice_id, limit=history),
    )


@router.get("/{slice_id}/sla-target", response_model=SlaTarget)
async def slice_sla_target(slice_id: str) -> SlaTarget:
    """The SLA a slice is held to, derived from its configuration."""
    config = slice_registry.get_slice(slice_id)
    if not config:
        raise HTTPException(status_code=404, detail=f"Slice '{slice_id}' not found")
    return derive_target(config)


@router.get("/{slice_id}/averages")
async def slice_averages(
    slice_id: str,
    window: int = Query(default=10, ge=1, le=200, description="Samples to average over"),
) -> dict:
    """Rolling KPI averages for one slice."""
    if not slice_registry.get_slice(slice_id):
        raise HTTPException(status_code=404, detail=f"Slice '{slice_id}' not found")
    return telemetry_engine.averages(slice_id, window=window)
