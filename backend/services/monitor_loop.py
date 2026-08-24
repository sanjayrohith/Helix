"""Background monitoring loop.

Drives telemetry sampling and SLA evaluation on a fixed cadence, streams the
results to connected dashboards, and writes SLA transitions to the audit
journal. This is what turns HELIX from a provisioning form into a running
control plane.
"""

from __future__ import annotations

import asyncio

from core.config import settings
from core.logging_config import get_logger
from models.telemetry_models import SlaEvaluation
from services.audit_log import audit_log
from services.sla_monitor import sla_monitor
from services.slice_registry import slice_registry
from services.telemetry import telemetry_engine

logger = get_logger("monitor")


class MonitorLoop:
    """Periodically samples every active slice and publishes the results."""

    def __init__(self, broadcaster=None) -> None:
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()
        self._broadcaster = broadcaster
        self.ticks = 0
        self.last_error: str | None = None

    def set_broadcaster(self, broadcaster) -> None:
        """Attach the WebSocket connection manager used to publish updates."""
        self._broadcaster = broadcaster

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        """Begin sampling, unless telemetry is disabled or already running."""
        if not settings.telemetry_enabled:
            logger.info("Telemetry disabled; monitor loop not started")
            return
        if self.running:
            return
        self._stopping.clear()
        self._task = asyncio.create_task(self._run(), name="helix-monitor")
        logger.info(
            "Monitor loop started (interval=%.1fs)", settings.telemetry_interval_seconds
        )

    async def stop(self) -> None:
        """Signal the loop to finish and wait for it briefly."""
        self._stopping.set()
        if self._task is None:
            return
        self._task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(self._task), timeout=2.0)
        except (TimeoutError, asyncio.CancelledError):
            pass
        self._task = None
        logger.info("Monitor loop stopped after %d tick(s)", self.ticks)

    async def _run(self) -> None:
        """The sampling loop itself. Never lets one bad tick kill the task."""
        while not self._stopping.is_set():
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
                logger.exception("Monitor tick failed; continuing")
            try:
                await asyncio.wait_for(
                    self._stopping.wait(), timeout=settings.telemetry_interval_seconds
                )
            except TimeoutError:
                continue

    async def tick(self) -> list[SlaEvaluation]:
        """Run one sampling interval. Exposed separately so tests can drive it."""
        self.ticks += 1
        active = slice_registry.get_active_slices()
        if not active:
            telemetry_engine.forget_all_except(set())
            return []

        samples = telemetry_engine.sample_all(active)
        evaluations = sla_monitor.evaluate_all(active)
        counts = sla_monitor.status_counts(evaluations)

        await self._publish(samples, evaluations, counts)
        self._journal_transitions(evaluations)
        return evaluations

    async def _publish(self, samples, evaluations, counts) -> None:
        """Push telemetry and SLA state to connected dashboards."""
        if self._broadcaster is None:
            return
        summary = telemetry_engine.network_summary(counts)
        await self._broadcaster.broadcast_telemetry(
            {
                "samples": [sample.model_dump(mode="json") for sample in samples],
                "sla": [evaluation.model_dump(mode="json") for evaluation in evaluations],
                "summary": summary.model_dump(mode="json"),
            }
        )

    def _journal_transitions(self, evaluations: list[SlaEvaluation]) -> None:
        """Record SLA status changes, and only the changes, in the audit journal."""
        for evaluation, previous in sla_monitor.transitions(evaluations):
            if evaluation.status == "violated":
                audit_log.record(
                    "sla_violated",
                    (
                        f"'{evaluation.slice_name}' is violating its SLA "
                        f"(score {evaluation.compliance_score:.0f}): "
                        + ", ".join(breach.kpi for breach in evaluation.breaches)
                    ),
                    severity="error",
                    slice_id=evaluation.slice_id,
                    slice_name=evaluation.slice_name,
                    detail={
                        "previous_status": previous,
                        "compliance_score": evaluation.compliance_score,
                        "breaches": [b.model_dump(mode="json") for b in evaluation.breaches],
                    },
                )
            elif previous in ("violated", "at_risk") and evaluation.status == "meeting":
                audit_log.record(
                    "sla_recovered",
                    f"'{evaluation.slice_name}' recovered and is meeting its SLA again",
                    slice_id=evaluation.slice_id,
                    slice_name=evaluation.slice_name,
                    detail={"previous_status": previous},
                )

    def status(self) -> dict:
        """Report loop health for the system-status endpoint."""
        return {
            "running": self.running,
            "enabled": settings.telemetry_enabled,
            "interval_seconds": settings.telemetry_interval_seconds,
            "ticks": self.ticks,
            "last_error": self.last_error,
            **telemetry_engine.stats(),
        }


monitor_loop = MonitorLoop()
