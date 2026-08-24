"""Pydantic models for the HELIX 5G network slicing system."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

SD_PATTERN = re.compile(r"^0x[0-9a-fA-F]{6}$")


def utcnow() -> datetime:
    """Timezone-aware UTC timestamp (datetime.utcnow is deprecated in 3.12)."""
    return datetime.now(UTC)


class SliceIntent(BaseModel):
    """Raw natural language intent from network operator."""

    intent: str = Field(
        ..., description="Plain English description of slice requirement"
    )


class SliceConfig(BaseModel):
    """Complete 5G network slice configuration."""

    slice_id: str = Field(..., description="Unique identifier (UUID)")
    name: str = Field(..., description="Human-readable slice name")
    sst: int = Field(
        ...,
        ge=1,
        le=3,
        description="S-NSSAI Slice/Service Type (1=eMBB, 2=URLLC, 3=mMTC)",
    )
    sd: str = Field(
        ..., description="Slice Differentiator in hex format, e.g., '0x000100'"
    )
    qos_5qi: int = Field(..., ge=1, le=255, description="5QI QoS Identifier value")
    arp_priority: int = Field(
        ..., ge=1, le=15, description="ARP Priority (1=highest, 15=lowest)"
    )
    guaranteed_bitrate_mbps: float = Field(
        ..., ge=0, description="Guaranteed Bit Rate in Mbps"
    )
    max_bitrate_mbps: float = Field(..., ge=0, description="Maximum Bit Rate in Mbps")
    latency_ms: int = Field(..., ge=1, description="Target latency in milliseconds")
    security_level: Literal["standard", "high", "critical"] = Field(
        ..., description="Security classification"
    )
    isolation: Literal["shared", "dedicated", "strict"] = Field(
        ..., description="Resource isolation type"
    )
    device_count: int = Field(..., ge=1, description="Number of devices in the slice")
    use_case: str = Field(
        ...,
        description="Use case category (e.g., 'healthcare', 'autonomous-vehicles', 'iot')",
    )
    location: str = Field(..., description="Geographic location or zone")
    status: Literal["pending", "active", "conflict", "rejected"] = Field(
        default="pending", description="Current slice status"
    )
    created_at: datetime = Field(default_factory=utcnow, description="Creation timestamp")
    updated_at: datetime | None = Field(
        default=None, description="Timestamp of the last configuration change"
    )

    @field_validator("sd", mode="before")
    @classmethod
    def normalise_sd(cls, value: object) -> str:
        """Accept '0x1', '000100' or 'ABC123' and normalise to '0xabc123'."""
        if isinstance(value, int):
            return f"0x{value:06x}"
        text = str(value).strip().lower()
        if text.startswith("0x"):
            text = text[2:]
        if not text or not all(char in "0123456789abcdef" for char in text):
            raise ValueError(f"Slice Differentiator must be hexadecimal, got '{value}'")
        if len(text) > 6:
            raise ValueError(f"Slice Differentiator exceeds 24 bits: '{value}'")
        return f"0x{text.zfill(6)}"

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Slice name must not be blank")
        return cleaned[:120]

    @model_validator(mode="after")
    def bitrates_must_be_ordered(self) -> SliceConfig:
        """MBR below GBR is not a representable QoS flow, so raise it instead."""
        if self.max_bitrate_mbps < self.guaranteed_bitrate_mbps:
            self.max_bitrate_mbps = self.guaranteed_bitrate_mbps
        return self

    @property
    def snssai(self) -> str:
        """The S-NSSAI in the conventional 'SST-SD' notation."""
        return f"{self.sst:02x}-{self.sd[2:]}"


ConflictType = Literal[
    "bandwidth",
    "snssai",
    "arp",
    "regulatory",
    "latency",
    "isolation",
    "device_density",
]

ConflictSeverity = Literal["blocking", "warning", "advisory"]


class ConflictFinding(BaseModel):
    """One specific problem found while validating a proposed slice."""

    conflict_type: ConflictType = Field(..., description="Category of the problem")
    severity: ConflictSeverity = Field(
        ..., description="blocking prevents deployment; warning and advisory do not"
    )
    details: str = Field(..., description="Human-readable explanation")
    suggestions: list[str] = Field(
        default_factory=list, description="Recommended actions to resolve it"
    )
    remediation: dict = Field(
        default_factory=dict,
        description="Field changes that would resolve this finding automatically",
    )
    conflicting_slice_ids: list[str] = Field(
        default_factory=list, description="Existing slices involved in the clash"
    )


class ConflictReport(BaseModel):
    """Aggregate conflict detection result for a proposed slice."""

    has_conflict: bool = Field(..., description="Whether a blocking conflict was detected")
    conflict_type: ConflictType | None = Field(
        None, description="Category of the most severe finding, for backwards compatibility"
    )
    details: str = Field(..., description="Human-readable summary of the findings")
    suggestions: list[str] = Field(
        default_factory=list, description="Recommended actions to resolve the conflicts"
    )
    findings: list[ConflictFinding] = Field(
        default_factory=list, description="Every problem found, not just the first"
    )
    auto_remediation: dict = Field(
        default_factory=dict,
        description="A merged set of field changes that would make the slice admissible",
    )

    @property
    def blocking_findings(self) -> list[ConflictFinding]:
        return [f for f in self.findings if f.severity == "blocking"]

    @property
    def warnings(self) -> list[ConflictFinding]:
        return [f for f in self.findings if f.severity != "blocking"]


class SliceDeploymentResult(BaseModel):
    """Result of a slice provisioning attempt."""

    success: bool = Field(..., description="Whether deployment succeeded")
    slice_config: SliceConfig = Field(
        ..., description="The generated slice configuration"
    )
    conflict_report: ConflictReport = Field(
        ..., description="Conflict detection results"
    )
    deploy_time_seconds: float = Field(
        ..., description="Time taken to deploy in seconds"
    )
    message: str = Field(..., description="Human-readable result message")
    parser_used: str = Field(
        default="unknown", description="Which intent parser produced the configuration"
    )
    parse_fallback_reason: str | None = Field(
        default=None, description="Why the LLM parser was bypassed, when it was"
    )
    parse_trace: dict | None = Field(
        default=None, description="How each field was derived, for the deterministic parser"
    )
    auto_remediated: bool = Field(
        default=False, description="Whether the conflict engine's fixes were applied"
    )


class SliceSimulationRequest(BaseModel):
    """A what-if admission check that never touches the network."""

    intent: str = Field(..., description="Plain English slice requirement")
    apply_remediation: bool = Field(
        default=False, description="Re-check after applying the engine's proposed fixes"
    )


class SliceSimulationResult(BaseModel):
    """Outcome of a dry-run admission check."""

    would_deploy: bool = Field(..., description="Whether provisioning would succeed")
    slice_config: SliceConfig = Field(..., description="The configuration that was evaluated")
    conflict_report: ConflictReport = Field(..., description="Findings for the configuration")
    remediated_config: SliceConfig | None = Field(
        default=None, description="The configuration after applying proposed fixes"
    )
    remediated_report: ConflictReport | None = Field(
        default=None, description="Findings after applying proposed fixes"
    )
    parser_used: str = Field(default="unknown")
    capacity_before_mbps: float = Field(..., description="Guaranteed bandwidth in use now")
    capacity_after_mbps: float = Field(
        ..., description="Guaranteed bandwidth in use if this slice were admitted"
    )


class SliceStats(BaseModel):
    """Summary statistics for slice registry."""

    total_slices: int = Field(..., description="Total number of slices in registry")
    active_slices: int = Field(..., description="Number of active slices")
    total_bandwidth_used_mbps: float = Field(
        ..., description="Sum of guaranteed bitrates"
    )
    bandwidth_remaining_mbps: float = Field(
        ..., description="Available bandwidth (1000 - used)"
    )
    conflict_count: int = Field(
        ..., description="Number of slices with conflict status"
    )


class WebSocketMessage(BaseModel):
    """WebSocket message format for real-time updates."""

    event: Literal[
        "slice_created",
        "slice_updated",
        "slice_deleted",
        "conflict_detected",
        "telemetry",
        "sla_alert",
    ] = Field(..., description="Event type")
    data: dict = Field(..., description="Event payload")
