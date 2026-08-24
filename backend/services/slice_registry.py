"""Slice registry: the authoritative in-memory view of provisioned slices.

The registry keeps every slice in a dict for O(1) lookup and mirrors writes to
the SQLite store, so a restart restores the operator's network instead of
silently resetting it. All mutations take a reentrant lock because the
telemetry loop and the HTTP handlers touch the same structures.
"""

from __future__ import annotations

import uuid
from threading import RLock

from core.config import settings
from core.logging_config import get_logger
from models.slice_models import SliceConfig, SliceStats, utcnow
from storage.sqlite_store import get_store

logger = get_logger("registry")

# Kept as a module constant for backwards compatibility with existing imports.
TOTAL_BANDWIDTH_CAPACITY = settings.total_bandwidth_mbps

DEMO_SLICES: tuple[dict, ...] = (
    {
        "name": "Enterprise Broadband - Metro",
        "sst": 1,
        "sd": "0x000001",
        "qos_5qi": 9,
        "arp_priority": 5,
        "guaranteed_bitrate_mbps": 200.0,
        "max_bitrate_mbps": 500.0,
        "latency_ms": 20,
        "security_level": "standard",
        "isolation": "shared",
        "device_count": 1000,
        "use_case": "broadband",
        "location": "Mumbai",
    },
    {
        "name": "Apollo Hospitals Critical Care",
        "sst": 2,
        "sd": "0x000002",
        "qos_5qi": 69,
        "arp_priority": 1,
        "guaranteed_bitrate_mbps": 50.0,
        "max_bitrate_mbps": 100.0,
        "latency_ms": 5,
        "security_level": "critical",
        "isolation": "strict",
        "device_count": 500,
        "use_case": "healthcare",
        "location": "Chennai",
    },
    {
        "name": "Smart City IoT - Sensors",
        "sst": 3,
        "sd": "0x000003",
        "qos_5qi": 80,
        "arp_priority": 8,
        "guaranteed_bitrate_mbps": 30.0,
        "max_bitrate_mbps": 50.0,
        "latency_ms": 100,
        "security_level": "standard",
        "isolation": "shared",
        "device_count": 5000,
        "use_case": "iot",
        "location": "Bangalore",
    },
)

# Statuses that consume radio and transport resources.
CONSUMING_STATUSES = frozenset({"active"})


class SliceRegistry:
    """Storage and queries for network slice configurations."""

    def __init__(self) -> None:
        self._slices: dict[str, SliceConfig] = {}
        self._lock = RLock()
        self._restore()

    # --- bootstrap -------------------------------------------------------------

    def _restore(self) -> None:
        """Load persisted slices, seeding demo data only on a first run."""
        persisted = get_store().load_slices()
        if persisted:
            with self._lock:
                self._slices = {config.slice_id: config for config in persisted}
            logger.info("Restored %d slice(s) from persistent storage", len(persisted))
            return

        if settings.seed_demo_slices:
            self._seed_demo_slices()

    def _seed_demo_slices(self) -> None:
        """Populate a fresh instance with three representative slices."""
        for template in DEMO_SLICES:
            config = SliceConfig(
                slice_id=str(uuid.uuid4()),
                status="active",
                created_at=utcnow(),
                **template,
            )
            self._slices[config.slice_id] = config
            get_store().save_slice(config)
        logger.info("Seeded %d demo slice(s)", len(DEMO_SLICES))

    # --- mutations ---------------------------------------------------------------

    def add_slice(self, config: SliceConfig) -> SliceConfig:
        """Insert a slice and persist it."""
        with self._lock:
            self._slices[config.slice_id] = config
        get_store().save_slice(config)
        return config

    def update_slice(self, slice_id: str, changes: dict) -> SliceConfig | None:
        """Apply a partial update, revalidating the whole configuration."""
        with self._lock:
            existing = self._slices.get(slice_id)
            if existing is None:
                return None
            payload = existing.model_dump()
            payload.update(changes)
            payload["updated_at"] = utcnow()
            updated = SliceConfig(**payload)
            self._slices[slice_id] = updated
        get_store().save_slice(updated)
        return updated

    def set_status(self, slice_id: str, status: str) -> SliceConfig | None:
        """Transition a slice to a new lifecycle status."""
        return self.update_slice(slice_id, {"status": status})

    def delete_slice(self, slice_id: str) -> SliceConfig | None:
        """Remove a slice from the registry and storage."""
        with self._lock:
            removed = self._slices.pop(slice_id, None)
        if removed is not None:
            get_store().delete_slice(slice_id)
        return removed

    def clear(self, reseed: bool = False) -> None:
        """Drop every slice. Used by the demo reset endpoint and tests."""
        with self._lock:
            self._slices.clear()
        get_store().reset()
        if reseed:
            self._seed_demo_slices()

    # --- queries -----------------------------------------------------------------

    def get_slice(self, slice_id: str) -> SliceConfig | None:
        with self._lock:
            return self._slices.get(slice_id)

    def get_all_slices(self) -> list[SliceConfig]:
        with self._lock:
            return list(self._slices.values())

    def get_active_slices(self) -> list[SliceConfig]:
        with self._lock:
            return [s for s in self._slices.values() if s.status in CONSUMING_STATUSES]

    def find_by_use_case(self, use_case: str) -> list[SliceConfig]:
        target = use_case.strip().lower()
        with self._lock:
            return [s for s in self._slices.values() if s.use_case.lower() == target]

    def find_by_location(self, location: str) -> list[SliceConfig]:
        target = location.strip().lower()
        with self._lock:
            return [s for s in self._slices.values() if s.location.lower() == target]

    def count(self) -> int:
        with self._lock:
            return len(self._slices)

    # --- capacity accounting -------------------------------------------------------

    def get_total_active_bandwidth(self) -> float:
        """Sum of guaranteed bitrates across resource-consuming slices."""
        return sum(s.guaranteed_bitrate_mbps for s in self.get_active_slices())

    def get_available_bandwidth(self) -> float:
        """Guaranteed bandwidth still available for admission."""
        return max(0.0, settings.total_bandwidth_mbps - self.get_total_active_bandwidth())

    def get_stats(self) -> SliceStats:
        """Summary counters for the dashboard header."""
        slices = self.get_all_slices()
        active = [s for s in slices if s.status in CONSUMING_STATUSES]
        conflicts = [s for s in slices if s.status == "conflict"]
        used = sum(s.guaranteed_bitrate_mbps for s in active)
        return SliceStats(
            total_slices=len(slices),
            active_slices=len(active),
            total_bandwidth_used_mbps=round(used, 2),
            bandwidth_remaining_mbps=round(settings.total_bandwidth_mbps - used, 2),
            conflict_count=len(conflicts),
        )

    def breakdown(self) -> dict:
        """Group slices by SST, status, use case and location for analytics."""
        slices = self.get_all_slices()

        def tally(key) -> dict:
            counts: dict = {}
            for item in slices:
                value = key(item)
                counts[value] = counts.get(value, 0) + 1
            return counts

        return {
            "by_sst": tally(lambda s: s.sst),
            "by_status": tally(lambda s: s.status),
            "by_use_case": tally(lambda s: s.use_case),
            "by_location": tally(lambda s: s.location),
            "by_isolation": tally(lambda s: s.isolation),
            "total_devices": sum(s.device_count for s in slices),
        }

    # --- collision checks -------------------------------------------------------------

    def check_snssai_exists(
        self, sst: int, sd: str, exclude_slice_id: str | None = None
    ) -> bool:
        """True when an active slice already owns this SST+SD pair."""
        normalised = sd.strip().lower()
        for config in self.get_active_slices():
            if exclude_slice_id and config.slice_id == exclude_slice_id:
                continue
            if config.sst == sst and config.sd.lower() == normalised:
                return True
        return False

    def has_critical_arp_one(self, exclude_slice_id: str | None = None) -> bool:
        """True when a critical slice already holds the highest ARP priority."""
        for config in self.get_active_slices():
            if exclude_slice_id and config.slice_id == exclude_slice_id:
                continue
            if config.arp_priority == 1 and config.security_level == "critical":
                return True
        return False

    def slices_holding_arp_one(self) -> list[SliceConfig]:
        """The active slices currently occupying ARP=1."""
        return [s for s in self.get_active_slices() if s.arp_priority == 1]

    def next_available_sd(self, sst: int, start: int = 0x000100) -> str:
        """Allocate the lowest free Slice Differentiator for an SST."""
        candidate = start
        for _ in range(0xFFFFFF):
            sd = f"0x{candidate:06x}"
            if not self.check_snssai_exists(sst, sd):
                return sd
            candidate = (candidate + 1) & 0xFFFFFF
        raise RuntimeError("Slice Differentiator space exhausted")


slice_registry = SliceRegistry()
