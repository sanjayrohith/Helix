"""Conflict detection engine for validating slice configurations."""

from models.slice_models import ConflictReport, SliceConfig
from services.slice_registry import TOTAL_BANDWIDTH_CAPACITY, slice_registry


class ConflictDetector:
    """Validates slice configurations against existing slices and policies."""

    def detect_conflicts(self, new_slice: SliceConfig) -> ConflictReport:
        """
        Check for conflicts with existing slices and regulatory requirements.

        Checks performed in order:
        1. Bandwidth conflict - total GBR exceeds capacity
        2. S-NSSAI conflict - SST+SD combination already exists
        3. ARP conflict - ARP=1 already used by critical slice
        4. Regulatory conflict - device_count > 10000 requires strict isolation

        Args:
            new_slice: The proposed slice configuration

        Returns:
            ConflictReport with conflict details and suggestions
        """
        # Check 1: Bandwidth conflict
        current_bandwidth = slice_registry.get_total_active_bandwidth()
        total_after_deployment = current_bandwidth + new_slice.guaranteed_bitrate_mbps

        if total_after_deployment > TOTAL_BANDWIDTH_CAPACITY:
            bandwidth_available = TOTAL_BANDWIDTH_CAPACITY - current_bandwidth
            return ConflictReport(
                has_conflict=True,
                conflict_type="bandwidth",
                details=(
                    f"Insufficient bandwidth capacity. Requested {new_slice.guaranteed_bitrate_mbps} Mbps GBR, "
                    f"but only {bandwidth_available:.1f} Mbps available. "
                    f"Current usage: {current_bandwidth:.1f} / {TOTAL_BANDWIDTH_CAPACITY} Mbps."
                ),
                suggestions=[
                    f"Reduce guaranteed bitrate to {bandwidth_available:.1f} Mbps or less",
                    "Enable burst mode with lower guaranteed rate and higher max rate",
                    "Schedule deployment during off-peak hours when other slices may be deactivated",
                    "Consider releasing unused bandwidth from existing slices",
                ],
            )

        # Check 2: S-NSSAI conflict (SST + SD combination)
        if slice_registry.check_snssai_exists(new_slice.sst, new_slice.sd):
            # Suggest a new SD value
            suggested_sd = self._generate_unique_sd(new_slice.sst)
            return ConflictReport(
                has_conflict=True,
                conflict_type="snssai",
                details=(
                    f"S-NSSAI conflict: SST={new_slice.sst} with SD={new_slice.sd} "
                    f"is already assigned to an active slice. Each slice must have a unique S-NSSAI."
                ),
                suggestions=[
                    f"Use a different Slice Differentiator: {suggested_sd}",
                    "Modify the existing slice instead of creating a new one",
                    "Deactivate the conflicting slice before provisioning this one",
                ],
            )

        # Check 3: ARP conflict (ARP=1 reserved for critical)
        if new_slice.arp_priority == 1 and slice_registry.has_critical_arp_one():
            return ConflictReport(
                has_conflict=True,
                conflict_type="arp",
                details=(
                    "ARP priority conflict: ARP=1 is already assigned to another critical slice. "
                    "Only one slice with highest priority (ARP=1) can be active for critical services "
                    "to ensure preemption capabilities."
                ),
                suggestions=[
                    "Use ARP priority 2 for this slice",
                    "Review if this service truly requires highest priority",
                    "Coordinate with the existing ARP=1 slice owner for priority reassignment",
                ],
            )

        # Check 4: Regulatory compliance (large device count requires strict isolation)
        if new_slice.device_count > 10000 and new_slice.isolation != "strict":
            return ConflictReport(
                has_conflict=True,
                conflict_type="regulatory",
                details=(
                    f"Regulatory compliance violation: Slices with more than 10,000 devices "
                    f"({new_slice.device_count:,} requested) require strict isolation per network policy. "
                    f"Current isolation level: {new_slice.isolation}."
                ),
                suggestions=[
                    "Change isolation type to 'strict' for regulatory compliance",
                    "Reduce device count to 10,000 or fewer to use shared/dedicated isolation",
                    "Split into multiple smaller slices with fewer devices each",
                ],
            )

        # No conflicts detected
        return ConflictReport(
            has_conflict=False,
            conflict_type=None,
            details="No conflicts detected. Slice configuration is valid and ready for deployment.",
            suggestions=[],
        )

    def _generate_unique_sd(self, sst: int) -> str:
        """Generate a unique SD value that doesn't conflict with existing slices."""
        base = 0x000100
        while True:
            sd = f"0x{base:06x}"
            if not slice_registry.check_snssai_exists(sst, sd):
                return sd
            base += 1
            if base > 0xFFFFFF:
                # Wrap around (unlikely to happen in practice)
                base = 0x000001


# Global singleton instance
conflict_detector = ConflictDetector()
