"""Pydantic models for STRIX 5G Network Slicing system."""

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


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
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation timestamp"
    )


class ConflictReport(BaseModel):
    """Conflict detection report for slice provisioning."""

    has_conflict: bool = Field(..., description="Whether a conflict was detected")
    conflict_type: Optional[Literal["bandwidth", "snssai", "arp", "regulatory"]] = (
        Field(None, description="Type of conflict detected")
    )
    details: str = Field(..., description="Human-readable conflict description")
    suggestions: list[str] = Field(
        default_factory=list, description="Recommended actions to resolve conflict"
    )


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

    event: Literal["slice_created", "slice_deleted", "conflict_detected"] = Field(
        ..., description="Event type"
    )
    data: dict = Field(..., description="Event payload")
