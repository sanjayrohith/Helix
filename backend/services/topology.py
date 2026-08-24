"""Network topology digital twin and slice placement.

HELIX previously treated the network as a single pool of bandwidth, which
meant admission control could accept a slice that no individual site could
actually host. This module models the network as concrete gNB, edge, UPF and
core nodes, tracks what each one is carrying, and places every slice on the
node that best fits its requirements.

Placement is explainable: each candidate node carries a score and the reasons
it was preferred or ruled out, so an operator can see why a slice landed
where it did.
"""

from __future__ import annotations

from threading import RLock

from core.logging_config import get_logger
from models.slice_models import SliceConfig
from models.topology_models import (
    NetworkLink,
    NetworkNode,
    NodeUtilization,
    PlacementCandidate,
    PlacementDecision,
    TopologyView,
)

logger = get_logger("topology")

# A small but realistic reference topology across four Indian metros.
DEFAULT_NODES: tuple[NetworkNode, ...] = (
    NetworkNode(
        node_id="gnb-mumbai-01",
        name="Mumbai Metro gNB",
        node_type="gnb",
        location="Mumbai",
        capacity_mbps=600.0,
        max_slices=8,
        max_devices=50_000,
        supports_isolation=["shared", "dedicated"],
        min_latency_ms=4.0,
    ),
    NetworkNode(
        node_id="edge-mumbai-01",
        name="Mumbai Edge Cloud",
        node_type="edge",
        location="Mumbai",
        capacity_mbps=400.0,
        max_slices=6,
        max_devices=20_000,
        supports_isolation=["shared", "dedicated", "strict"],
        min_latency_ms=1.0,
    ),
    NetworkNode(
        node_id="gnb-chennai-01",
        name="Chennai Metro gNB",
        node_type="gnb",
        location="Chennai",
        capacity_mbps=500.0,
        max_slices=8,
        max_devices=40_000,
        supports_isolation=["shared", "dedicated"],
        min_latency_ms=4.0,
    ),
    NetworkNode(
        node_id="edge-chennai-01",
        name="Chennai Edge Cloud",
        node_type="edge",
        location="Chennai",
        capacity_mbps=350.0,
        max_slices=6,
        max_devices=15_000,
        supports_isolation=["shared", "dedicated", "strict"],
        min_latency_ms=1.0,
    ),
    NetworkNode(
        node_id="gnb-bangalore-01",
        name="Bangalore Metro gNB",
        node_type="gnb",
        location="Bangalore",
        capacity_mbps=550.0,
        max_slices=10,
        max_devices=80_000,
        supports_isolation=["shared", "dedicated"],
        min_latency_ms=4.0,
    ),
    NetworkNode(
        node_id="upf-west-01",
        name="Western Region UPF",
        node_type="upf",
        location="Mumbai",
        capacity_mbps=800.0,
        max_slices=12,
        max_devices=120_000,
        supports_isolation=["shared", "dedicated", "strict"],
        min_latency_ms=8.0,
    ),
    NetworkNode(
        node_id="core-national-01",
        name="National Core",
        node_type="core",
        location="Delhi",
        capacity_mbps=1200.0,
        max_slices=20,
        max_devices=500_000,
        supports_isolation=["shared", "dedicated", "strict"],
        min_latency_ms=15.0,
    ),
)

DEFAULT_LINKS: tuple[NetworkLink, ...] = (
    NetworkLink(link_id="l1", source="gnb-mumbai-01", target="edge-mumbai-01", capacity_mbps=600, latency_ms=1.0),
    NetworkLink(link_id="l2", source="edge-mumbai-01", target="upf-west-01", capacity_mbps=800, latency_ms=3.0),
    NetworkLink(link_id="l3", source="gnb-chennai-01", target="edge-chennai-01", capacity_mbps=500, latency_ms=1.0),
    NetworkLink(link_id="l4", source="edge-chennai-01", target="upf-west-01", capacity_mbps=600, latency_ms=6.0),
    NetworkLink(link_id="l5", source="gnb-bangalore-01", target="upf-west-01", capacity_mbps=550, latency_ms=5.0),
    NetworkLink(link_id="l6", source="upf-west-01", target="core-national-01", capacity_mbps=1200, latency_ms=7.0),
)

# Scoring weights for placement.
LOCATION_MATCH_BONUS = 40.0
LATENCY_HEADROOM_WEIGHT = 25.0
CAPACITY_HEADROOM_WEIGHT = 20.0
ISOLATION_FIT_BONUS = 15.0

# Shared immutable default for a node with no placements at all - avoids
# allocating a fresh empty dict per lookup for the (common) unoccupied node.
_EMPTY_USAGE: dict = {
    "allocated_mbps": 0.0,
    "attached_devices": 0,
    "hosted_slices": 0,
    "slice_ids": [],
}


class TopologyManager:
    """Tracks node occupancy and decides where each slice runs."""

    def __init__(
        self,
        nodes: tuple[NetworkNode, ...] = DEFAULT_NODES,
        links: tuple[NetworkLink, ...] = DEFAULT_LINKS,
    ) -> None:
        self._nodes: dict[str, NetworkNode] = {node.node_id: node for node in nodes}
        self._links: list[NetworkLink] = list(links)
        self._placements: dict[str, str] = {}  # slice_id -> node_id
        self._lock = RLock()

    # --- placement -------------------------------------------------------------

    def evaluate(self, config: SliceConfig, exclude_slice: bool = True) -> list[PlacementCandidate]:
        """Score every node for hosting ``config``, best first."""
        exclude = config.slice_id if exclude_slice else None
        # Computed once for every node in this call, rather than each node
        # independently re-scanning every placement to find its own share -
        # O(nodes + placements) instead of O(nodes x placements).
        usage_by_node = self._usage_by_node(exclude_slice_id=exclude)

        candidates = [
            self._score_node(node, config, usage_by_node.get(node.node_id, _EMPTY_USAGE))
            for node in self._nodes.values()
        ]
        candidates.sort(key=lambda c: (not c.feasible, -c.score))
        return candidates

    def _score_node(
        self, node: NetworkNode, config: SliceConfig, usage: dict
    ) -> PlacementCandidate:
        """Judge one node's fit for a slice, recording the reasoning."""
        reasons: list[str] = []
        feasible = True
        score = 0.0

        if node.health == "offline":
            return PlacementCandidate(
                node_id=node.node_id,
                node_name=node.name,
                score=0.0,
                feasible=False,
                reasons=["node is offline"],
            )
        if node.health == "degraded":
            score -= 20.0
            reasons.append("node is degraded")

        # Hard constraint: transport capacity.
        free_mbps = node.capacity_mbps - usage["allocated_mbps"]
        if config.guaranteed_bitrate_mbps > free_mbps:
            feasible = False
            reasons.append(
                f"needs {config.guaranteed_bitrate_mbps:.0f} Mbps, only {free_mbps:.0f} Mbps free"
            )
        else:
            headroom = free_mbps / node.capacity_mbps
            score += CAPACITY_HEADROOM_WEIGHT * headroom
            reasons.append(f"{free_mbps:.0f} Mbps free of {node.capacity_mbps:.0f}")

        # Hard constraint: slice slots.
        if usage["hosted_slices"] >= node.max_slices:
            feasible = False
            reasons.append(f"already hosting {usage['hosted_slices']} of {node.max_slices} slices")

        # Hard constraint: device population.
        free_devices = node.max_devices - usage["attached_devices"]
        if config.device_count > free_devices:
            feasible = False
            reasons.append(
                f"needs {config.device_count:,} device slots, only {free_devices:,} free"
            )

        # Hard constraint: isolation the node can actually honour.
        if config.isolation not in node.supports_isolation:
            feasible = False
            reasons.append(f"cannot provide '{config.isolation}' isolation")
        else:
            score += ISOLATION_FIT_BONUS
            reasons.append(f"supports '{config.isolation}' isolation")

        # Hard constraint: the node's own latency floor.
        if node.min_latency_ms > config.latency_ms:
            feasible = False
            reasons.append(
                f"{node.min_latency_ms:.0f} ms floor exceeds the {config.latency_ms} ms target"
            )
        else:
            slack = (config.latency_ms - node.min_latency_ms) / max(config.latency_ms, 1)
            # Prefer nodes with just enough latency headroom, keeping the tightest
            # sites free for slices that genuinely need them.
            score += LATENCY_HEADROOM_WEIGHT * (1.0 - slack)
            reasons.append(f"{node.min_latency_ms:.0f} ms floor fits the {config.latency_ms} ms target")

        # Soft preference: co-locate with the requested site.
        if config.location.strip().lower() in node.location.lower():
            score += LOCATION_MATCH_BONUS
            reasons.append(f"located in {node.location}, matching the intent")

        return PlacementCandidate(
            node_id=node.node_id,
            node_name=node.name,
            score=round(max(0.0, score), 2),
            feasible=feasible,
            reasons=reasons,
        )

    def place(self, config: SliceConfig) -> PlacementDecision:
        """Choose a node for ``config`` and record the placement."""
        candidates = self.evaluate(config)
        feasible = [candidate for candidate in candidates if candidate.feasible]

        if not feasible:
            blocking = candidates[0].reasons if candidates else ["no nodes configured"]
            logger.warning("No feasible node for '%s': %s", config.name, "; ".join(blocking))
            return PlacementDecision(
                slice_id=config.slice_id,
                slice_name=config.name,
                placed=False,
                explanation=(
                    "No node can host this slice. Closest candidate "
                    f"'{candidates[0].node_name}': {'; '.join(blocking)}."
                    if candidates
                    else "The topology has no nodes."
                ),
                candidates=candidates,
            )

        chosen = feasible[0]
        with self._lock:
            self._placements[config.slice_id] = chosen.node_id

        logger.info("Placed '%s' on %s (score %.1f)", config.name, chosen.node_name, chosen.score)
        return PlacementDecision(
            slice_id=config.slice_id,
            slice_name=config.name,
            node_id=chosen.node_id,
            node_name=chosen.node_name,
            placed=True,
            explanation=f"Placed on {chosen.node_name}: {'; '.join(chosen.reasons)}.",
            candidates=candidates,
        )

    def unplace(self, slice_id: str) -> str | None:
        """Release a slice's node assignment."""
        with self._lock:
            return self._placements.pop(slice_id, None)

    def node_for(self, slice_id: str) -> str | None:
        with self._lock:
            return self._placements.get(slice_id)

    def sync(self, configs: list[SliceConfig]) -> None:
        """Drop placements for slices that no longer exist, place any that are new."""
        live = {config.slice_id for config in configs}
        with self._lock:
            for slice_id in list(self._placements):
                if slice_id not in live:
                    self._placements.pop(slice_id)
            unplaced = [c for c in configs if c.slice_id not in self._placements]
        for config in unplaced:
            self.place(config)

    # --- occupancy ---------------------------------------------------------------

    def _usage_by_node(self, exclude_slice_id: str | None = None) -> dict[str, dict]:
        """Compute occupancy for every node in a single pass over placements.

        Grouping placements by node first, then resolving each slice's
        contribution once, replaces what used to be an independent full
        scan of every placement per node (O(nodes x placements)) with one
        pass over placements plus one registry lookup per placed slice
        (O(nodes + placements)) - the difference that actually matters once
        an instance has accumulated hundreds of slices across a handful of
        nodes, rather than the three demo slices this started with.
        """
        from services.slice_registry import slice_registry

        grouped: dict[str, list[str]] = {}
        with self._lock:
            for slice_id, node_id in self._placements.items():
                if slice_id == exclude_slice_id:
                    continue
                grouped.setdefault(node_id, []).append(slice_id)

        usage_by_node: dict[str, dict] = {}
        for node_id, slice_ids in grouped.items():
            allocated = 0.0
            devices = 0
            active_ids: list[str] = []
            for slice_id in slice_ids:
                config = slice_registry.get_slice(slice_id)
                if config is None or config.status != "active":
                    continue
                allocated += config.guaranteed_bitrate_mbps
                devices += config.device_count
                active_ids.append(slice_id)
            usage_by_node[node_id] = {
                "allocated_mbps": allocated,
                "attached_devices": devices,
                "hosted_slices": len(active_ids),
                "slice_ids": active_ids,
            }
        return usage_by_node

    def _usage(self, node_id: str, exclude_slice_id: str | None = None) -> dict:
        """Occupancy for a single node.

        Kept for callers (tests, and anything scoring exactly one node) that
        do not need every node's usage at once; prefer `_usage_by_node` when
        iterating over several nodes in the same call.
        """
        return self._usage_by_node(exclude_slice_id=exclude_slice_id).get(node_id, _EMPTY_USAGE)

    def utilization(self) -> list[NodeUtilization]:
        """Live occupancy for every node."""
        usage_by_node = self._usage_by_node()
        result: list[NodeUtilization] = []
        for node in self._nodes.values():
            usage = usage_by_node.get(node.node_id, _EMPTY_USAGE)
            result.append(
                NodeUtilization(
                    node_id=node.node_id,
                    name=node.name,
                    node_type=node.node_type,
                    location=node.location,
                    health=node.health,
                    capacity_mbps=node.capacity_mbps,
                    allocated_mbps=round(usage["allocated_mbps"], 2),
                    utilization_percent=round(
                        100.0 * usage["allocated_mbps"] / node.capacity_mbps, 2
                    ),
                    hosted_slices=usage["hosted_slices"],
                    max_slices=node.max_slices,
                    attached_devices=usage["attached_devices"],
                    max_devices=node.max_devices,
                    slice_ids=usage["slice_ids"],
                )
            )
        return result

    def view(self) -> TopologyView:
        """The complete twin for the dashboard's topology panel."""
        nodes = self.utilization()
        with self._lock:
            placements = dict(self._placements)
        return TopologyView(
            nodes=nodes,
            links=self._links,
            placements=placements,
            total_capacity_mbps=round(sum(n.capacity_mbps for n in nodes), 2),
            total_allocated_mbps=round(sum(n.allocated_mbps for n in nodes), 2),
            saturated_nodes=[n.node_id for n in nodes if n.is_saturated],
        )

    def get_node(self, node_id: str) -> NetworkNode | None:
        return self._nodes.get(node_id)

    def set_node_health(self, node_id: str, health: str) -> NetworkNode | None:
        """Mark a node healthy, degraded or offline to exercise failover."""
        node = self._nodes.get(node_id)
        if node is None:
            return None
        node.health = health  # type: ignore[assignment]
        logger.warning("Node %s health set to %s", node_id, health)
        return node

    def reset(self) -> None:
        with self._lock:
            self._placements.clear()


topology_manager = TopologyManager()
