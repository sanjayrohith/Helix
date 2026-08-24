"""Models for the network topology digital twin."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

NodeType = Literal["gnb", "edge", "upf", "core"]
NodeHealth = Literal["healthy", "degraded", "offline"]


class NetworkNode(BaseModel):
    """A physical or virtual element that slices can be placed on."""

    node_id: str = Field(..., description="Stable identifier, e.g. 'gnb-mumbai-01'")
    name: str = Field(..., description="Human-readable node name")
    node_type: NodeType = Field(..., description="Role in the 5G architecture")
    location: str = Field(..., description="Geographic site")
    capacity_mbps: float = Field(..., gt=0, description="Transport capacity of this node")
    max_slices: int = Field(..., gt=0, description="Slices this node can host")
    max_devices: int = Field(..., gt=0, description="Devices this node can attach")
    supports_isolation: list[str] = Field(
        default_factory=list, description="Isolation levels this node can honour"
    )
    min_latency_ms: float = Field(
        ..., ge=0, description="Floor latency contributed by this node's position"
    )
    health: NodeHealth = Field(default="healthy")


class NodeUtilization(BaseModel):
    """Live occupancy of one node."""

    node_id: str
    name: str
    node_type: NodeType
    location: str
    health: NodeHealth
    capacity_mbps: float
    allocated_mbps: float
    utilization_percent: float
    hosted_slices: int
    max_slices: int
    attached_devices: int
    max_devices: int
    slice_ids: list[str] = Field(default_factory=list)

    @property
    def is_saturated(self) -> bool:
        return self.utilization_percent >= 95.0 or self.hosted_slices >= self.max_slices


class NetworkLink(BaseModel):
    """A transport link between two nodes."""

    link_id: str
    source: str
    target: str
    capacity_mbps: float
    latency_ms: float


class PlacementCandidate(BaseModel):
    """A node considered for hosting a slice, with its score and reasoning."""

    node_id: str
    node_name: str
    score: float = Field(..., description="Higher is a better fit")
    feasible: bool
    reasons: list[str] = Field(default_factory=list)


class PlacementDecision(BaseModel):
    """Where a slice was placed and why."""

    slice_id: str
    slice_name: str
    node_id: str | None = None
    node_name: str | None = None
    placed: bool
    explanation: str
    candidates: list[PlacementCandidate] = Field(default_factory=list)


class TopologyView(BaseModel):
    """The full twin: nodes, links, occupancy and placements."""

    nodes: list[NodeUtilization]
    links: list[NetworkLink]
    placements: dict[str, str] = Field(
        default_factory=dict, description="slice_id -> node_id"
    )
    total_capacity_mbps: float
    total_allocated_mbps: float
    saturated_nodes: list[str] = Field(default_factory=list)
