"""Live KPI simulation for provisioned slices.

A slice that is merely 'active' tells an operator very little. This engine
gives every slice a running set of key performance indicators, so the
dashboard shows a network that behaves rather than a static list of records.

The model is deliberately simple but not random noise: each slice carries
persistent state (a load phase, a congestion level) that evolves between
samples, and the KPIs are derived from that state and the slice's own
configuration. A slice provisioned with a tight latency budget and strict
isolation genuinely performs better than an oversubscribed shared one.
"""

from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass, field
from threading import RLock

from core.config import settings
from core.logging_config import get_logger
from core.telecom import packet_delay_budget
from models.slice_models import SliceConfig
from models.telemetry_models import NetworkKpiSummary, SliceTelemetry

logger = get_logger("telemetry")

# How much of the guaranteed rate a slice typically carries, by use case.
BASE_LOAD_BY_SST = {1: 0.72, 2: 0.55, 3: 0.38}

# Isolation buys predictability: stronger isolation means less jitter and loss.
ISOLATION_QUALITY = {"shared": 1.0, "dedicated": 0.55, "strict": 0.3}


@dataclass
class SliceRuntimeState:
    """Per-slice simulation state that persists between sampling intervals."""

    slice_id: str
    phase: float = field(default_factory=lambda: random.uniform(0, math.tau))
    load_factor: float = 0.7
    congestion: float = 0.0
    ticks: int = 0
    outage_ticks_remaining: int = 0
    total_ticks: int = 0
    available_ticks: int = 0

    def advance(self, base_load: float) -> None:
        """Move the simulation forward one interval."""
        self.ticks += 1
        self.total_ticks += 1
        # A slow sinusoid gives a believable daily-load shape, plus random walk.
        self.phase = (self.phase + 0.09) % math.tau
        cyclical = 0.18 * math.sin(self.phase)
        drift = random.gauss(0, 0.04)
        self.load_factor = _clamp(base_load + cyclical + drift, 0.05, 1.35)

        # Congestion builds while demand exceeds the guaranteed rate and decays otherwise.
        if self.load_factor > 1.0:
            self.congestion = min(1.0, self.congestion + 0.12)
        else:
            self.congestion = max(0.0, self.congestion - 0.08)

        if self.outage_ticks_remaining > 0:
            self.outage_ticks_remaining -= 1
        else:
            self.available_ticks += 1
            # Rare, short degradations keep the availability figure meaningful.
            if random.random() < 0.004:
                self.outage_ticks_remaining = random.randint(1, 3)

    @property
    def in_outage(self) -> bool:
        return self.outage_ticks_remaining > 0

    @property
    def availability_percent(self) -> float:
        if self.total_ticks == 0:
            return 100.0
        return round(100.0 * self.available_ticks / self.total_ticks, 3)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class TelemetryEngine:
    """Generates and retains KPI samples for every slice."""

    def __init__(self, history_size: int | None = None) -> None:
        self.history_size = history_size or settings.telemetry_history_size
        self._history: dict[str, deque[SliceTelemetry]] = {}
        self._state: dict[str, SliceRuntimeState] = {}
        self._lock = RLock()

    # --- sampling ---------------------------------------------------------------

    def sample(self, config: SliceConfig) -> SliceTelemetry:
        """Produce and retain one KPI sample for ``config``."""
        with self._lock:
            state = self._state.setdefault(
                config.slice_id, SliceRuntimeState(slice_id=config.slice_id)
            )

        base_load = BASE_LOAD_BY_SST.get(config.sst, 0.6)
        state.advance(base_load)
        telemetry = self._derive(config, state)

        with self._lock:
            history = self._history.setdefault(config.slice_id, deque(maxlen=self.history_size))
            history.append(telemetry)
        return telemetry

    def _derive(self, config: SliceConfig, state: SliceRuntimeState) -> SliceTelemetry:
        """Turn simulation state plus slice configuration into observable KPIs."""
        quality = ISOLATION_QUALITY.get(config.isolation, 1.0)
        congestion = state.congestion

        # Offered load is what the attached devices ask for; throughput is what the
        # slice manages to carry. Separating them is what makes the SLA meaningful:
        # a slice carrying little traffic is idle, not failing.
        offered = config.guaranteed_bitrate_mbps * state.load_factor
        if state.in_outage:
            throughput = offered * random.uniform(0.0, 0.15)
        else:
            # Demand above the guaranteed rate can use headroom up to the max rate,
            # minus whatever congestion is currently costing the slice.
            deliverable = min(offered, config.max_bitrate_mbps)
            throughput = deliverable * (1.0 - congestion * 0.35)

        # Latency sits near the configured target and inflates under congestion.
        budget = packet_delay_budget(config.qos_5qi)
        floor = max(0.4, config.latency_ms * 0.55)
        latency = floor + (config.latency_ms - floor) * random.uniform(0.6, 1.05)
        latency += congestion * budget * 0.6 * quality
        if state.in_outage:
            latency *= random.uniform(2.5, 5.0)

        jitter = max(0.05, latency * 0.08 * quality * (1 + congestion))
        loss = _clamp(
            (0.02 + congestion * 1.8) * quality + (4.0 if state.in_outage else 0.0),
            0.0,
            100.0,
        )

        # PRB utilisation tracks the share of network capacity the slice is using.
        capacity_share = throughput / max(settings.total_bandwidth_mbps, 1.0)
        prb = _clamp(capacity_share * 100 * 3.2 + congestion * 22, 0.0, 100.0)

        attach_rate = 0.55 + 0.35 * min(state.load_factor, 1.0)
        active_devices = int(config.device_count * _clamp(attach_rate, 0.0, 1.0))

        return SliceTelemetry(
            slice_id=config.slice_id,
            throughput_mbps=round(max(0.0, throughput), 2),
            offered_load_mbps=round(max(0.0, offered), 2),
            latency_ms=round(max(0.1, latency), 2),
            jitter_ms=round(jitter, 2),
            packet_loss_percent=round(loss, 3),
            prb_utilization_percent=round(prb, 2),
            active_devices=active_devices,
            availability_percent=state.availability_percent,
        )

    def sample_all(self, configs: list[SliceConfig]) -> list[SliceTelemetry]:
        """Sample every supplied slice and drop state for slices that are gone."""
        samples = [self.sample(config) for config in configs]
        self.forget_all_except({config.slice_id for config in configs})
        return samples

    # --- reads --------------------------------------------------------------------

    def latest(self, slice_id: str) -> SliceTelemetry | None:
        with self._lock:
            history = self._history.get(slice_id)
            return history[-1] if history else None

    def history(self, slice_id: str, limit: int | None = None) -> list[SliceTelemetry]:
        with self._lock:
            history = list(self._history.get(slice_id, ()))
        return history[-limit:] if limit else history

    def latest_all(self) -> dict[str, SliceTelemetry]:
        with self._lock:
            return {
                slice_id: history[-1]
                for slice_id, history in self._history.items()
                if history
            }

    def averages(self, slice_id: str, window: int = 10) -> dict[str, float]:
        """Rolling means over the last ``window`` samples, for SLA evaluation."""
        samples = self.history(slice_id, limit=window)
        if not samples:
            return {}
        count = len(samples)
        return {
            "throughput_mbps": round(sum(s.throughput_mbps for s in samples) / count, 2),
            "offered_load_mbps": round(sum(s.offered_load_mbps for s in samples) / count, 2),
            "delivery_ratio": round(sum(s.delivery_ratio for s in samples) / count, 4),
            "latency_ms": round(sum(s.latency_ms for s in samples) / count, 2),
            "jitter_ms": round(sum(s.jitter_ms for s in samples) / count, 2),
            "packet_loss_percent": round(
                sum(s.packet_loss_percent for s in samples) / count, 3
            ),
            "prb_utilization_percent": round(
                sum(s.prb_utilization_percent for s in samples) / count, 2
            ),
            "availability_percent": samples[-1].availability_percent,
            "samples": count,
            "availability_samples": self.observed_intervals(slice_id),
        }

    def observed_intervals(self, slice_id: str) -> int:
        """Total intervals this slice has been observed for, across all history.

        Availability is a long-run figure: it is reported from the first
        interval but only becomes statistically meaningful after many of them.
        """
        with self._lock:
            state = self._state.get(slice_id)
        return state.total_ticks if state else 0

    def network_summary(self, sla_counts: dict[str, int] | None = None) -> NetworkKpiSummary:
        """Roll the per-slice KPIs up into the dashboard header figures."""
        latest = list(self.latest_all().values())
        counts = sla_counts or {}
        if not latest:
            return NetworkKpiSummary(
                total_throughput_mbps=0.0,
                mean_latency_ms=0.0,
                mean_packet_loss_percent=0.0,
                mean_prb_utilization_percent=0.0,
                slices_meeting_sla=counts.get("meeting", 0),
                slices_at_risk=counts.get("at_risk", 0),
                slices_violating_sla=counts.get("violated", 0),
            )
        count = len(latest)
        return NetworkKpiSummary(
            total_throughput_mbps=round(sum(s.throughput_mbps for s in latest), 2),
            mean_latency_ms=round(sum(s.latency_ms for s in latest) / count, 2),
            mean_packet_loss_percent=round(
                sum(s.packet_loss_percent for s in latest) / count, 3
            ),
            mean_prb_utilization_percent=round(
                sum(s.prb_utilization_percent for s in latest) / count, 2
            ),
            slices_meeting_sla=counts.get("meeting", 0),
            slices_at_risk=counts.get("at_risk", 0),
            slices_violating_sla=counts.get("violated", 0),
        )

    # --- lifecycle ------------------------------------------------------------------

    def forget(self, slice_id: str) -> None:
        """Drop all state for a deleted slice."""
        with self._lock:
            self._history.pop(slice_id, None)
            self._state.pop(slice_id, None)

    def forget_all_except(self, keep: set[str]) -> None:
        """Garbage-collect telemetry for slices that no longer exist."""
        with self._lock:
            for slice_id in list(self._history):
                if slice_id not in keep:
                    self._history.pop(slice_id, None)
                    self._state.pop(slice_id, None)

    def reset(self) -> None:
        with self._lock:
            self._history.clear()
            self._state.clear()

    def stats(self) -> dict:
        with self._lock:
            return {
                "tracked_slices": len(self._history),
                "history_size": self.history_size,
                "samples_retained": sum(len(h) for h in self._history.values()),
            }


telemetry_engine = TelemetryEngine()
