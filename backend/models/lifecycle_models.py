"""Models for slice lifecycle operations beyond create and delete."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SliceUpdateRequest(BaseModel):
    """A partial update to a live slice. Omitted fields are left untouched."""

    name: str | None = None
    guaranteed_bitrate_mbps: float | None = Field(default=None, ge=0)
    max_bitrate_mbps: float | None = Field(default=None, ge=0)
    latency_ms: int | None = Field(default=None, ge=1)
    arp_priority: int | None = Field(default=None, ge=1, le=15)
    device_count: int | None = Field(default=None, ge=1)
    isolation: Literal["shared", "dedicated", "strict"] | None = None
    security_level: Literal["standard", "high", "critical"] | None = None

    def changes(self) -> dict:
        """Return only the fields the caller actually set."""
        return {key: value for key, value in self.model_dump().items() if value is not None}


class SliceScaleRequest(BaseModel):
    """Scale a slice's guaranteed bandwidth by a multiplier or absolute value."""

    factor: float | None = Field(
        default=None, gt=0, le=10, description="Multiply the current guaranteed bitrate"
    )
    target_gbr_mbps: float | None = Field(
        default=None, ge=0, description="Set an absolute guaranteed bitrate"
    )

    def resolve(self, current_gbr: float) -> float:
        """Compute the requested guaranteed bitrate for a slice at ``current_gbr``."""
        if self.target_gbr_mbps is not None:
            return self.target_gbr_mbps
        if self.factor is not None:
            return round(current_gbr * self.factor, 2)
        raise ValueError("Provide either 'factor' or 'target_gbr_mbps'")


class SliceStatusChange(BaseModel):
    """Result of a lifecycle transition."""

    slice_id: str
    previous_status: str
    new_status: str
    message: str
