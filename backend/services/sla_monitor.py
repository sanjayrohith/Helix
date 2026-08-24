"""SLA evaluation: does a slice actually deliver what it was provisioned for?

Targets are derived from the slice's own configuration rather than configured
separately, so every slice is held to the contract its intent implied. The
monitor grades against rolling averages, not single samples, so one noisy
interval does not flip a slice into violation.
"""

from __future__ import annotations

from threading import RLock

from core.logging_config import get_logger
from core.telecom import packet_delay_budget
from models.slice_models import SliceConfig
from models.telemetry_models import SlaBreach, SlaEvaluation, SlaStatus, SlaTarget
from services.telemetry import telemetry_engine

logger = get_logger("sla")

# Tolerance applied to the configured target before a KPI counts as breaching.
LATENCY_TOLERANCE = 1.25
THROUGHPUT_FLOOR_RATIO = 0.80

# Availability expectations by security classification.
AVAILABILITY_TARGETS = {"critical": 99.99, "high": 99.9, "standard": 99.0}

# Acceptable steady-state packet loss by slice type.
PACKET_LOSS_TARGETS = {1: 1.0, 2: 0.1, 3: 2.0}

# Number of samples the verdict is averaged over.
EVALUATION_WINDOW = 10

# Weight each KPI contributes to the 0-100 compliance score.
KPI_WEIGHTS = {
    "latency": 30.0,
    "throughput": 25.0,
    "packet_loss": 20.0,
    "jitter": 10.0,
    "availability": 15.0,
}


def derive_target(config: SliceConfig) -> SlaTarget:
    """Build the SLA a slice is held to from its own configuration."""
    return SlaTarget(
        slice_id=config.slice_id,
        max_latency_ms=max(1.0, config.latency_ms * LATENCY_TOLERANCE),
        min_throughput_mbps=round(config.guaranteed_bitrate_mbps * THROUGHPUT_FLOOR_RATIO, 2),
        max_packet_loss_percent=PACKET_LOSS_TARGETS.get(config.sst, 1.0),
        max_jitter_ms=max(0.5, config.latency_ms * 0.25),
        min_availability_percent=AVAILABILITY_TARGETS.get(config.security_level, 99.0),
    )


class SlaMonitor:
    """Grades slices against their derived SLA and tracks status transitions."""

    def __init__(self) -> None:
        self._last_status: dict[str, SlaStatus] = {}
        self._lock = RLock()

    def evaluate(self, config: SliceConfig) -> SlaEvaluation:
        """Grade one slice over its recent telemetry window."""
        target = derive_target(config)
        averages = telemetry_engine.averages(config.slice_id, window=EVALUATION_WINDOW)

        if not averages:
            return SlaEvaluation(
                slice_id=config.slice_id,
                slice_name=config.name,
                status="unknown",
                compliance_score=100.0,
                breaches=[],
            )

        breaches: list[SlaBreach] = []
        penalty = 0.0

        latency = averages["latency_ms"]
        if latency > target.max_latency_ms:
            overshoot = _overshoot(latency, target.max_latency_ms)
            penalty += KPI_WEIGHTS["latency"] * overshoot
            breaches.append(
                SlaBreach(
                    kpi="latency",
                    observed=latency,
                    target=target.max_latency_ms,
                    severity="critical" if overshoot > 0.5 else "warning",
                    description=(
                        f"Mean latency {latency:.1f} ms exceeds the "
                        f"{target.max_latency_ms:.1f} ms target "
                        f"(5QI={config.qos_5qi} budget is {packet_delay_budget(config.qos_5qi)} ms)."
                    ),
                )
            )

        # A slice carrying less than its guaranteed rate may simply be idle. The
        # SLA question is whether it delivered the traffic that was offered, capped
        # at the rate it was guaranteed - so grade against demand, not capacity.
        throughput = averages["throughput_mbps"]
        offered = averages.get("offered_load_mbps", 0.0)
        expected = min(offered, target.min_throughput_mbps) if offered > 0 else 0.0
        if expected > 0 and throughput < expected:
            shortfall = _shortfall(throughput, expected)
            penalty += KPI_WEIGHTS["throughput"] * shortfall
            breaches.append(
                SlaBreach(
                    kpi="throughput",
                    observed=throughput,
                    target=round(expected, 2),
                    severity="critical" if shortfall > 0.4 else "warning",
                    description=(
                        f"Delivered {throughput:.1f} Mbps of the {expected:.1f} Mbps offered "
                        f"within the {target.min_throughput_mbps:.1f} Mbps guarantee."
                    ),
                )
            )

        loss = averages["packet_loss_percent"]
        if loss > target.max_packet_loss_percent:
            overshoot = _overshoot(loss, target.max_packet_loss_percent)
            penalty += KPI_WEIGHTS["packet_loss"] * overshoot
            breaches.append(
                SlaBreach(
                    kpi="packet_loss",
                    observed=loss,
                    target=target.max_packet_loss_percent,
                    severity="critical" if overshoot > 1.0 else "warning",
                    description=(
                        f"Packet loss {loss:.2f}% exceeds the "
                        f"{target.max_packet_loss_percent:.2f}% target."
                    ),
                )
            )

        jitter = averages["jitter_ms"]
        if jitter > target.max_jitter_ms:
            overshoot = _overshoot(jitter, target.max_jitter_ms)
            penalty += KPI_WEIGHTS["jitter"] * overshoot
            breaches.append(
                SlaBreach(
                    kpi="jitter",
                    observed=jitter,
                    target=target.max_jitter_ms,
                    severity="warning",
                    description=(
                        f"Jitter {jitter:.2f} ms exceeds the {target.max_jitter_ms:.2f} ms target."
                    ),
                )
            )

        availability = averages["availability_percent"]
        if availability < target.min_availability_percent:
            shortfall = _shortfall(availability, target.min_availability_percent)
            penalty += KPI_WEIGHTS["availability"] * min(1.0, shortfall * 20)
            breaches.append(
                SlaBreach(
                    kpi="availability",
                    observed=availability,
                    target=target.min_availability_percent,
                    severity="critical" if availability < 99.0 else "warning",
                    description=(
                        f"Availability {availability:.3f}% is below the "
                        f"{target.min_availability_percent:.2f}% commitment."
                    ),
                )
            )

        score = round(max(0.0, 100.0 - penalty), 2)
        status = self._grade(breaches, score)

        return SlaEvaluation(
            slice_id=config.slice_id,
            slice_name=config.name,
            status=status,
            compliance_score=score,
            breaches=breaches,
        )

    def _grade(self, breaches: list[SlaBreach], score: float) -> SlaStatus:
        """Turn breaches and a score into a single status."""
        if any(breach.severity == "critical" for breach in breaches):
            return "violated"
        if breaches or score < 95.0:
            return "at_risk"
        return "meeting"

    def evaluate_all(self, configs: list[SliceConfig]) -> list[SlaEvaluation]:
        """Grade every slice in one pass."""
        return [self.evaluate(config) for config in configs]

    def transitions(self, evaluations: list[SlaEvaluation]) -> list[tuple[SlaEvaluation, SlaStatus]]:
        """Return evaluations whose status changed, with their previous status.

        Alerting on transitions rather than on every evaluation is what keeps
        the operator from being buried while a slice sits in violation.
        """
        changed: list[tuple[SlaEvaluation, SlaStatus]] = []
        with self._lock:
            for evaluation in evaluations:
                previous = self._last_status.get(evaluation.slice_id, "unknown")
                if previous != evaluation.status:
                    changed.append((evaluation, previous))
                    self._last_status[evaluation.slice_id] = evaluation.status
        return changed

    def status_counts(self, evaluations: list[SlaEvaluation]) -> dict[str, int]:
        """Tally statuses for the network summary."""
        counts = {"meeting": 0, "at_risk": 0, "violated": 0, "unknown": 0}
        for evaluation in evaluations:
            counts[evaluation.status] = counts.get(evaluation.status, 0) + 1
        return counts

    def forget(self, slice_id: str) -> None:
        with self._lock:
            self._last_status.pop(slice_id, None)

    def reset(self) -> None:
        with self._lock:
            self._last_status.clear()


def _overshoot(observed: float, target: float) -> float:
    """How far past the target a KPI is, as a ratio of the target."""
    if target <= 0:
        return 1.0
    return min(2.0, (observed - target) / target)


def _shortfall(observed: float, target: float) -> float:
    """How far below the target a KPI is, as a ratio of the target."""
    if target <= 0:
        return 0.0
    return min(1.0, max(0.0, (target - observed) / target))


sla_monitor = SlaMonitor()
