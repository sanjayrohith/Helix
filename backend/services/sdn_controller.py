"""Simulated SDN controller.

Stands in for a Ryu controller programming OpenFlow switches. The simulation
now produces the artefacts a real deployment would - concrete flow rules, a
QoS queue definition and a per-slice deployment record - so the rest of HELIX
(and the UI) can work against a realistic shape rather than a boolean.

Timing is configurable: HELIX_SDN_STEP_SCALE=0 makes deployments instant,
which is what the test suite and CI use.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from datetime import datetime

from core.config import settings
from core.logging_config import get_logger
from core.telecom import SST_NAMES, packet_delay_budget
from models.slice_models import SliceConfig, utcnow

logger = get_logger("sdn")

# Datapath identifiers for the simulated switches in the transport fabric.
DATAPATHS = ("0x0000000000000001", "0x0000000000000002", "0x0000000000000003")


class SdnDeploymentError(RuntimeError):
    """Raised when the controller refuses or fails a deployment."""


@dataclass
class FlowRule:
    """One OpenFlow rule as it would be installed on a datapath."""

    datapath_id: str
    table_id: int
    priority: int
    match: dict
    actions: list[str]
    idle_timeout: int = 0

    def as_dict(self) -> dict:
        return {
            "datapath_id": self.datapath_id,
            "table_id": self.table_id,
            "priority": self.priority,
            "match": self.match,
            "actions": self.actions,
            "idle_timeout": self.idle_timeout,
        }


@dataclass
class DeploymentRecord:
    """What the controller did for one slice."""

    slice_id: str
    slice_name: str
    deployed_at: datetime = field(default_factory=utcnow)
    flow_rules: list[FlowRule] = field(default_factory=list)
    queue_id: int = 0
    steps: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "slice_id": self.slice_id,
            "slice_name": self.slice_name,
            "deployed_at": self.deployed_at.isoformat(),
            "queue_id": self.queue_id,
            "flow_rules": [rule.as_dict() for rule in self.flow_rules],
            "steps": self.steps,
        }


def build_flow_rules(config: SliceConfig) -> list[FlowRule]:
    """Derive the OpenFlow rules that would carry a slice's traffic.

    ARP maps onto flow priority (ARP=1 is the highest, so it gets the highest
    priority number) and the S-NSSAI becomes the match, which is how a real
    deployment keeps slices from stealing each other's traffic.
    """
    priority = 40_000 + (16 - config.arp_priority) * 1_000
    queue_id = config.qos_5qi
    match = {
        "eth_type": "0x0800",
        "s_nssai": config.snssai,
        "sst": config.sst,
        "sd": config.sd,
    }

    rules: list[FlowRule] = []
    for index, datapath in enumerate(DATAPATHS):
        actions = [f"set_queue:{queue_id}", f"meter:{config.sst}"]
        # The last hop in the chain forwards out of the fabric; the rest chain on.
        actions.append("output:NORMAL" if index == len(DATAPATHS) - 1 else f"goto_table:{index + 1}")
        rules.append(
            FlowRule(
                datapath_id=datapath,
                table_id=index,
                priority=priority,
                match=match,
                actions=actions,
                # Dedicated and strict slices hold their rules; shared ones age out.
                idle_timeout=0 if config.isolation != "shared" else 600,
            )
        )
    return rules


class MockSDNController:
    """Simulates a Ryu controller programming the transport fabric."""

    def __init__(self) -> None:
        self.controller_name = settings.sdn_controller_name
        self.controller_version = "4.34"
        self._is_connected = True
        self._deployments: dict[str, DeploymentRecord] = {}
        self.deploy_count = 0
        self.failure_count = 0

    def _steps(self, config: SliceConfig) -> list[tuple[str, float]]:
        """The deployment sequence with its nominal per-step duration."""
        return [
            ("Validating slice parameters", 0.10),
            ("Reserving transport resources", 0.20),
            (
                f"Installing QoS policy (5QI={config.qos_5qi}, "
                f"GBR={config.guaranteed_bitrate_mbps:.0f} Mbps, "
                f"PDB={packet_delay_budget(config.qos_5qi)} ms)",
                0.30,
            ),
            (f"Programming S-NSSAI match {config.snssai}", 0.20),
            (f"Setting ARP priority {config.arp_priority}", 0.10),
            (f"Applying {config.isolation} isolation", 0.30),
            (f"Activating on {len(DATAPATHS)} edge datapaths", 0.30),
        ]

    async def deploy_slice(self, config: SliceConfig) -> bool:
        """Program a slice onto the fabric, returning True on success."""
        record = await self.deploy(config)
        return record is not None

    async def deploy(self, config: SliceConfig) -> DeploymentRecord | None:
        """Program a slice and return the resulting deployment record."""
        if not self._is_connected:
            raise SdnDeploymentError(f"{self.controller_name} is not connected")

        logger.info(
            "Deploying '%s' (%s) to %s",
            config.name,
            SST_NAMES.get(config.sst, "?"),
            self.controller_name,
        )

        completed: list[str] = []
        for description, duration in self._steps(config):
            await self._pause(duration)
            completed.append(description)
            logger.debug("  [%s] %s", config.slice_id[:8], description)

        if settings.sdn_failure_rate > 0 and random.random() < settings.sdn_failure_rate:
            self.failure_count += 1
            logger.warning("Controller rejected '%s' (simulated failure)", config.name)
            return None

        record = DeploymentRecord(
            slice_id=config.slice_id,
            slice_name=config.name,
            flow_rules=build_flow_rules(config),
            queue_id=config.qos_5qi,
            steps=completed,
        )
        self._deployments[config.slice_id] = record
        self.deploy_count += 1

        logger.info(
            "Activated '%s': %d flow rule(s) across %d datapath(s), queue %d",
            config.name,
            len(record.flow_rules),
            len(DATAPATHS),
            record.queue_id,
        )
        return record

    async def remove_slice(self, slice_id: str) -> bool:
        """Withdraw a slice's flow rules from the fabric."""
        await self._pause(0.4)
        removed = self._deployments.pop(slice_id, None)
        if removed is not None:
            logger.info("Withdrew %d flow rule(s) for %s", len(removed.flow_rules), slice_id[:8])
        return True

    async def _pause(self, seconds: float) -> None:
        """Sleep for a scaled, slightly jittered interval."""
        scale = settings.sdn_step_scale
        if scale <= 0:
            return
        await asyncio.sleep((seconds + random.uniform(0.0, seconds * 0.4)) * scale)

    def get_deployment(self, slice_id: str) -> DeploymentRecord | None:
        return self._deployments.get(slice_id)

    def get_flow_rules(self, slice_id: str) -> list[dict]:
        """The flow rules currently installed for a slice."""
        record = self._deployments.get(slice_id)
        return [rule.as_dict() for rule in record.flow_rules] if record else []

    def get_controller_status(self) -> dict:
        """Controller health for the system-status endpoint."""
        return {
            "name": self.controller_name,
            "version": self.controller_version,
            "connected": self._is_connected,
            "status": "operational" if self._is_connected else "disconnected",
            "datapaths": len(DATAPATHS),
            "active_deployments": len(self._deployments),
            "total_deployments": self.deploy_count,
            "failed_deployments": self.failure_count,
        }

    def set_connected(self, connected: bool) -> None:
        """Simulate the controller going up or down."""
        self._is_connected = connected
        logger.warning("Controller connection set to %s", connected)


sdn_controller = MockSDNController()
