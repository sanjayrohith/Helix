"""API router for the network topology digital twin."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from models.topology_models import (
    NodeUtilization,
    PlacementCandidate,
    PlacementDecision,
    TopologyView,
)
from services.slice_registry import slice_registry
from services.topology import topology_manager

router = APIRouter(prefix="/api/topology", tags=["topology"])


@router.get("", response_model=TopologyView)
async def get_topology() -> TopologyView:
    """The full twin: nodes with live occupancy, links and slice placements."""
    topology_manager.sync(slice_registry.get_active_slices())
    return topology_manager.view()


@router.get("/nodes", response_model=list[NodeUtilization])
async def list_nodes(
    node_type: str | None = Query(default=None, description="Filter by gnb, edge, upf or core"),
    location: str | None = Query(default=None, description="Filter by site"),
) -> list[NodeUtilization]:
    """Live occupancy for every node, optionally filtered."""
    nodes = topology_manager.utilization()
    if node_type:
        nodes = [node for node in nodes if node.node_type == node_type]
    if location:
        nodes = [node for node in nodes if node.location.lower() == location.lower()]
    return nodes


@router.get("/nodes/{node_id}", response_model=NodeUtilization)
async def get_node(node_id: str) -> NodeUtilization:
    """Live occupancy for one node."""
    for node in topology_manager.utilization():
        if node.node_id == node_id:
            return node
    raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")


@router.post("/nodes/{node_id}/health")
async def set_node_health(
    node_id: str,
    health: str = Query(..., description="healthy, degraded or offline"),
) -> dict:
    """Mark a node healthy, degraded or offline to exercise placement failover."""
    if health not in ("healthy", "degraded", "offline"):
        raise HTTPException(
            status_code=400, detail="health must be healthy, degraded or offline"
        )
    node = topology_manager.set_node_health(node_id, health)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")
    return {"node_id": node_id, "health": health, "name": node.name}


@router.get("/placement/{slice_id}", response_model=PlacementDecision)
async def get_placement(slice_id: str) -> PlacementDecision:
    """Where a slice is placed, and how every node scored for it."""
    config = slice_registry.get_slice(slice_id)
    if not config:
        raise HTTPException(status_code=404, detail=f"Slice '{slice_id}' not found")

    node_id = topology_manager.node_for(slice_id)
    candidates = topology_manager.evaluate(config)
    if node_id is None:
        return PlacementDecision(
            slice_id=slice_id,
            slice_name=config.name,
            placed=False,
            explanation="This slice has not been placed on a node.",
            candidates=candidates,
        )

    node = topology_manager.get_node(node_id)
    return PlacementDecision(
        slice_id=slice_id,
        slice_name=config.name,
        node_id=node_id,
        node_name=node.name if node else node_id,
        placed=True,
        explanation=f"Currently hosted on {node.name if node else node_id}.",
        candidates=candidates,
    )


@router.post("/placement/{slice_id}/rebalance", response_model=PlacementDecision)
async def rebalance_slice(slice_id: str) -> PlacementDecision:
    """Re-run placement for a slice, moving it if a better node is now available."""
    config = slice_registry.get_slice(slice_id)
    if not config:
        raise HTTPException(status_code=404, detail=f"Slice '{slice_id}' not found")
    topology_manager.unplace(slice_id)
    return topology_manager.place(config)


@router.get("/candidates/{slice_id}", response_model=list[PlacementCandidate])
async def placement_candidates(slice_id: str) -> list[PlacementCandidate]:
    """Score every node for a slice without changing its placement."""
    config = slice_registry.get_slice(slice_id)
    if not config:
        raise HTTPException(status_code=404, detail=f"Slice '{slice_id}' not found")
    return topology_manager.evaluate(config)
