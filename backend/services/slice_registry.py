"""In-memory slice registry with pre-populated demo slices."""

import uuid
from datetime import datetime

from core.config import settings
from models.slice_models import SliceConfig, SliceStats

# Total network bandwidth capacity in Mbps (configurable via HELIX_TOTAL_BANDWIDTH_MBPS)
TOTAL_BANDWIDTH_CAPACITY = settings.total_bandwidth_mbps


class SliceRegistry:
    """In-memory storage for network slice configurations."""

    def __init__(self):
        self._slices: dict[str, SliceConfig] = {}
        self._initialize_demo_slices()

    def _initialize_demo_slices(self) -> None:
        """Pre-populate registry with demo slices for demonstration."""
        demo_slices = [
            SliceConfig(
                slice_id=str(uuid.uuid4()),
                name="Enterprise Broadband - Metro",
                sst=1,  # eMBB
                sd="0x000001",
                qos_5qi=9,  # Default for video streaming / broadband
                arp_priority=5,
                guaranteed_bitrate_mbps=200.0,
                max_bitrate_mbps=500.0,
                latency_ms=20,
                security_level="standard",
                isolation="shared",
                device_count=1000,
                use_case="broadband",
                location="Mumbai",
                status="active",
                created_at=datetime.utcnow(),
            ),
            SliceConfig(
                slice_id=str(uuid.uuid4()),
                name="Apollo Hospitals Critical Care",
                sst=2,  # URLLC
                sd="0x000002",
                qos_5qi=69,  # Mission-critical
                arp_priority=1,  # Highest priority
                guaranteed_bitrate_mbps=50.0,
                max_bitrate_mbps=100.0,
                latency_ms=5,
                security_level="critical",
                isolation="strict",
                device_count=500,
                use_case="healthcare",
                location="Chennai",
                status="active",
                created_at=datetime.utcnow(),
            ),
            SliceConfig(
                slice_id=str(uuid.uuid4()),
                name="Smart City IoT - Sensors",
                sst=3,  # mMTC
                sd="0x000003",
                qos_5qi=80,  # Low-latency IoT
                arp_priority=8,
                guaranteed_bitrate_mbps=30.0,
                max_bitrate_mbps=50.0,
                latency_ms=100,
                security_level="standard",
                isolation="shared",
                device_count=5000,
                use_case="iot",
                location="Bangalore",
                status="active",
                created_at=datetime.utcnow(),
            ),
        ]

        for slice_config in demo_slices:
            self._slices[slice_config.slice_id] = slice_config

    def add_slice(self, slice_config: SliceConfig) -> SliceConfig:
        """Add a new slice to the registry."""
        self._slices[slice_config.slice_id] = slice_config
        return slice_config

    def get_slice(self, slice_id: str) -> SliceConfig | None:
        """Retrieve a slice by ID."""
        return self._slices.get(slice_id)

    def get_all_slices(self) -> list[SliceConfig]:
        """Get all slices in the registry."""
        return list(self._slices.values())

    def delete_slice(self, slice_id: str) -> SliceConfig | None:
        """Remove a slice from the registry."""
        return self._slices.pop(slice_id, None)

    def get_stats(self) -> SliceStats:
        """Calculate summary statistics for the registry."""
        slices = list(self._slices.values())
        active_slices = [s for s in slices if s.status == "active"]
        conflict_slices = [s for s in slices if s.status == "conflict"]

        total_bandwidth_used = sum(s.guaranteed_bitrate_mbps for s in active_slices)

        return SliceStats(
            total_slices=len(slices),
            active_slices=len(active_slices),
            total_bandwidth_used_mbps=total_bandwidth_used,
            bandwidth_remaining_mbps=TOTAL_BANDWIDTH_CAPACITY - total_bandwidth_used,
            conflict_count=len(conflict_slices),
        )

    def get_total_active_bandwidth(self) -> float:
        """Get sum of guaranteed bitrates for all active slices."""
        return sum(
            s.guaranteed_bitrate_mbps
            for s in self._slices.values()
            if s.status == "active"
        )

    def check_snssai_exists(
        self, sst: int, sd: str, exclude_slice_id: str | None = None
    ) -> bool:
        """Check if SST+SD combination already exists."""
        for slice_id, slice_config in self._slices.items():
            if exclude_slice_id and slice_id == exclude_slice_id:
                continue
            if (
                slice_config.sst == sst
                and slice_config.sd == sd
                and slice_config.status == "active"
            ):
                return True
        return False

    def has_critical_arp_one(self, exclude_slice_id: str | None = None) -> bool:
        """Check if ARP priority 1 is already used by a critical slice."""
        for slice_id, slice_config in self._slices.items():
            if exclude_slice_id and slice_id == exclude_slice_id:
                continue
            if (
                slice_config.arp_priority == 1
                and slice_config.security_level == "critical"
                and slice_config.status == "active"
            ):
                return True
        return False


# Global singleton instance
slice_registry = SliceRegistry()
