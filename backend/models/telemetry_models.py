"""Models for live slice telemetry and SLA compliance."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from models.slice_models import utcnow

SlaStatus = Literal["meeting", "at_risk", "violated", "unknown"]
KpiName = Literal["throughput", "latency", "jitter", "packet_loss", "prb_utilization", "availability"]


class SliceTelemetry(BaseModel):
    """One sampling interval of key performance indicators for a slice."""

    slice_id: str = Field(..., description="Slice the sample belongs to")
    timestamp: datetime = Field(default_factory=utcnow, description="Sample time")
    throughput_mbps: float = Field(..., ge=0, description="Delivered aggregate throughput")
    offered_load_mbps: float = Field(
        default=0.0, ge=0, description="Traffic the attached devices asked the slice to carry"
    )
    latency_ms: float = Field(..., ge=0, description="Observed one-way latency")
    jitter_ms: float = Field(..., ge=0, description="Observed packet delay variation")
    packet_loss_percent: float = Field(..., ge=0, le=100, description="Observed packet loss")
    prb_utilization_percent: float = Field(
        ..., ge=0, le=100, description="Physical resource block utilisation"
    )
    active_devices: int = Field(..., ge=0, description="Devices attached in this interval")
    availability_percent: float = Field(
        ..., ge=0, le=100, description="Rolling availability for the slice"
    )

    @property
    def delivery_ratio(self) -> float:
        """Share of offered traffic the slice actually carried (1.0 when idle)."""
        if self.offered_load_mbps <= 0:
            return 1.0
        return min(1.0, self.throughput_mbps / self.offered_load_mbps)

    @property
    def utilization_ratio(self) -> float:
        """PRB utilisation expressed as a 0-1 ratio."""
        return self.prb_utilization_percent / 100.0


class SlaTarget(BaseModel):
    """The contractual bounds a slice is expected to stay within."""

    slice_id: str
    max_latency_ms: float = Field(..., gt=0)
    min_throughput_mbps: float = Field(..., ge=0)
    max_packet_loss_percent: float = Field(..., ge=0, le=100)
    max_jitter_ms: float = Field(..., ge=0)
    min_availability_percent: float = Field(..., ge=0, le=100)


class SlaBreach(BaseModel):
    """A single KPI that has moved outside its target."""

    kpi: KpiName
    observed: float
    target: float
    severity: Literal["warning", "critical"]
    description: str


class SlaEvaluation(BaseModel):
    """The compliance verdict for a slice at a point in time."""

    slice_id: str
    slice_name: str
    status: SlaStatus
    evaluated_at: datetime = Field(default_factory=utcnow)
    compliance_score: float = Field(
        ..., ge=0, le=100, description="0-100 score across all monitored KPIs"
    )
    breaches: list[SlaBreach] = Field(default_factory=list)

    @property
    def is_healthy(self) -> bool:
        return self.status == "meeting"


class TelemetrySnapshot(BaseModel):
    """Latest telemetry plus SLA verdict for one slice."""

    slice_id: str
    slice_name: str
    latest: SliceTelemetry | None = None
    sla: SlaEvaluation | None = None
    history: list[SliceTelemetry] = Field(default_factory=list)


class NetworkKpiSummary(BaseModel):
    """Network-wide rollup used by the dashboard header."""

    sampled_at: datetime = Field(default_factory=utcnow)
    total_throughput_mbps: float
    mean_latency_ms: float
    mean_packet_loss_percent: float
    mean_prb_utilization_percent: float
    slices_meeting_sla: int
    slices_at_risk: int
    slices_violating_sla: int
