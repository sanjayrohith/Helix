"""Admission control: validate a proposed slice against the live network.

The original detector returned on the first problem it found, so an operator
whose slice had three issues had to resubmit three times to learn about them
all. This engine runs every check, ranks the findings by severity and merges
their remediations into a single set of changes that would make the slice
admissible.

Only ``blocking`` findings stop a deployment. Warnings and advisories are
reported so the operator can act on them without being forced to.
"""

from __future__ import annotations

from core.config import settings
from core.logging_config import get_logger
from core.telecom import SST_NAMES, get_qos, packet_delay_budget
from models.slice_models import ConflictFinding, ConflictReport, SliceConfig
from services.slice_registry import slice_registry

logger = get_logger("conflicts")

# Isolation levels ordered from weakest to strongest.
ISOLATION_RANK = {"shared": 0, "dedicated": 1, "strict": 2}

# Security levels that a regulator would expect to see isolated.
SENSITIVE_SECURITY_LEVELS = frozenset({"critical"})

# A slice asking for more than this share of total capacity is worth flagging.
LARGE_SLICE_CAPACITY_SHARE = 0.5


class ConflictDetector:
    """Runs every admission check and aggregates the results."""

    def detect_conflicts(self, new_slice: SliceConfig) -> ConflictReport:
        """Validate ``new_slice`` and return every finding, most severe first."""
        findings: list[ConflictFinding] = []

        for check in (
            self._check_bandwidth,
            self._check_snssai,
            self._check_arp,
            self._check_regulatory,
            self._check_latency_feasibility,
            self._check_isolation_consistency,
            self._check_device_density,
            self._check_capacity_share,
        ):
            finding = check(new_slice)
            if finding is not None:
                findings.append(finding)

        return self._build_report(findings)

    # --- individual checks -----------------------------------------------------

    def _check_bandwidth(self, new_slice: SliceConfig) -> ConflictFinding | None:
        """Total guaranteed bitrate must fit within the configured capacity."""
        capacity = settings.total_bandwidth_mbps
        in_use = slice_registry.get_total_active_bandwidth()
        available = max(0.0, capacity - in_use)
        requested = new_slice.guaranteed_bitrate_mbps

        if in_use + requested <= capacity:
            return None

        # Slices that could be preempted to make room, lowest priority first.
        preemptable = sorted(
            (
                s
                for s in slice_registry.get_active_slices()
                if s.arp_priority > new_slice.arp_priority
            ),
            key=lambda s: (-s.arp_priority, -s.guaranteed_bitrate_mbps),
        )
        reclaimable = sum(s.guaranteed_bitrate_mbps for s in preemptable)

        suggestions = [
            f"Reduce the guaranteed bitrate to {available:.1f} Mbps or less",
            "Use burst mode: a lower guaranteed rate with a higher maximum rate",
        ]
        if reclaimable >= requested - available:
            names = ", ".join(f"'{s.name}' (ARP {s.arp_priority})" for s in preemptable[:3])
            suggestions.insert(
                0,
                f"Preempt {reclaimable:.1f} Mbps from lower-priority slices: {names}",
            )
        else:
            suggestions.append("Release unused bandwidth from an existing slice first")

        return ConflictFinding(
            conflict_type="bandwidth",
            severity="blocking",
            details=(
                f"Insufficient capacity: {requested:.1f} Mbps GBR requested but only "
                f"{available:.1f} Mbps available (using {in_use:.1f} of {capacity:.0f} Mbps)."
            ),
            suggestions=suggestions,
            remediation=(
                {"guaranteed_bitrate_mbps": round(available, 2)} if available > 0 else {}
            ),
            conflicting_slice_ids=[s.slice_id for s in preemptable[:5]],
        )

    def _check_snssai(self, new_slice: SliceConfig) -> ConflictFinding | None:
        """Each active slice must own a unique SST+SD pair."""
        if not slice_registry.check_snssai_exists(new_slice.sst, new_slice.sd):
            return None

        clashing = [
            s.slice_id
            for s in slice_registry.get_active_slices()
            if s.sst == new_slice.sst and s.sd.lower() == new_slice.sd.lower()
        ]
        suggested_sd = slice_registry.next_available_sd(new_slice.sst)

        return ConflictFinding(
            conflict_type="snssai",
            severity="blocking",
            details=(
                f"S-NSSAI collision: SST={new_slice.sst} ({SST_NAMES.get(new_slice.sst, '?')}) "
                f"with SD={new_slice.sd} is already assigned to an active slice."
            ),
            suggestions=[
                f"Use the next free Slice Differentiator: {suggested_sd}",
                "Modify the existing slice instead of provisioning a second one",
                "Deactivate the conflicting slice before provisioning this one",
            ],
            remediation={"sd": suggested_sd},
            conflicting_slice_ids=clashing,
        )

    def _check_arp(self, new_slice: SliceConfig) -> ConflictFinding | None:
        """ARP=1 is reserved so exactly one critical slice can preempt everything."""
        if new_slice.arp_priority != 1 or not slice_registry.has_critical_arp_one():
            return None

        holders = slice_registry.slices_holding_arp_one()
        names = ", ".join(f"'{s.name}'" for s in holders) or "an existing slice"

        return ConflictFinding(
            conflict_type="arp",
            severity="blocking",
            details=(
                f"ARP priority collision: ARP=1 is already held by {names}. Only one slice "
                "may hold the highest priority so preemption stays deterministic."
            ),
            suggestions=[
                "Use ARP priority 2, which still preempts all business services",
                "Confirm this service genuinely outranks the current ARP=1 slice",
                "Coordinate a priority reassignment with the current holder",
            ],
            remediation={"arp_priority": 2},
            conflicting_slice_ids=[s.slice_id for s in holders],
        )

    def _check_regulatory(self, new_slice: SliceConfig) -> ConflictFinding | None:
        """Large device populations must be strictly isolated by policy."""
        limit = settings.max_devices_shared_isolation
        if new_slice.device_count <= limit or new_slice.isolation == "strict":
            return None

        return ConflictFinding(
            conflict_type="regulatory",
            severity="blocking",
            details=(
                f"Regulatory policy violation: {new_slice.device_count:,} devices exceeds the "
                f"{limit:,} device limit for '{new_slice.isolation}' isolation. Populations "
                "above the limit require strict isolation."
            ),
            suggestions=[
                "Change the isolation type to 'strict'",
                f"Reduce the device population to {limit:,} or fewer",
                "Split the deployment into several smaller slices",
            ],
            remediation={"isolation": "strict"},
        )

    def _check_latency_feasibility(self, new_slice: SliceConfig) -> ConflictFinding | None:
        """The requested latency must be achievable under the chosen 5QI."""
        budget = packet_delay_budget(new_slice.qos_5qi)
        if new_slice.latency_ms >= budget:
            return None

        qos = get_qos(new_slice.qos_5qi)
        # Find a standard 5QI that can actually meet the requested latency.
        from core.telecom import QOS_TABLE

        candidates = [
            characteristics
            for characteristics in QOS_TABLE.values()
            if characteristics.packet_delay_budget_ms <= new_slice.latency_ms
        ]
        best = min(candidates, key=lambda c: c.priority_level) if candidates else None

        suggestions = [
            f"Relax the latency target to {budget} ms, the packet delay budget for this 5QI",
        ]
        remediation: dict = {"latency_ms": budget}
        if best is not None:
            suggestions.insert(
                0,
                f"Switch to 5QI={best.qi} ({best.example_services}), whose "
                f"{best.packet_delay_budget_ms} ms budget meets the target",
            )
            remediation = {"qos_5qi": best.qi}

        label = qos.example_services if qos else "a non-standard 5QI"
        return ConflictFinding(
            conflict_type="latency",
            severity="warning",
            details=(
                f"Latency target of {new_slice.latency_ms} ms is tighter than the {budget} ms "
                f"packet delay budget of 5QI={new_slice.qos_5qi} ({label}). The slice will "
                "deploy but the target is unlikely to be met."
            ),
            suggestions=suggestions,
            remediation=remediation,
        )

    def _check_isolation_consistency(self, new_slice: SliceConfig) -> ConflictFinding | None:
        """Critical security classification should not run on shared resources."""
        if new_slice.security_level not in SENSITIVE_SECURITY_LEVELS:
            return None
        if ISOLATION_RANK[new_slice.isolation] >= ISOLATION_RANK["dedicated"]:
            return None

        return ConflictFinding(
            conflict_type="isolation",
            severity="warning",
            details=(
                f"Security level '{new_slice.security_level}' on '{new_slice.isolation}' "
                "isolation: critical traffic would share resources with other tenants."
            ),
            suggestions=[
                "Raise the isolation type to 'strict' for critical services",
                "Lower the security classification if shared resources are acceptable",
            ],
            remediation={"isolation": "strict"},
        )

    def _check_device_density(self, new_slice: SliceConfig) -> ConflictFinding | None:
        """Flag populations whose per-device share of bandwidth is implausible."""
        if new_slice.device_count <= 0 or new_slice.guaranteed_bitrate_mbps <= 0:
            return None

        per_device_kbps = (new_slice.guaranteed_bitrate_mbps * 1000) / new_slice.device_count
        # mMTC devices legitimately run on a trickle; other slice types do not.
        floor_kbps = 0.5 if new_slice.sst == 3 else 16.0
        if per_device_kbps >= floor_kbps:
            return None

        needed = round((floor_kbps * new_slice.device_count) / 1000, 2)
        return ConflictFinding(
            conflict_type="device_density",
            severity="advisory",
            details=(
                f"Each of the {new_slice.device_count:,} devices would receive only "
                f"{per_device_kbps:.2f} kbps of guaranteed bandwidth, below the "
                f"{floor_kbps:.1f} kbps floor for {SST_NAMES.get(new_slice.sst, 'this')} traffic."
            ),
            suggestions=[
                f"Raise the guaranteed bitrate to about {needed} Mbps",
                "Reduce the device population for this slice",
                "Split the population across several slices",
            ],
            remediation={"guaranteed_bitrate_mbps": needed},
        )

    def _check_capacity_share(self, new_slice: SliceConfig) -> ConflictFinding | None:
        """Warn when one slice would dominate the whole network."""
        capacity = settings.total_bandwidth_mbps
        if capacity <= 0:
            return None
        share = new_slice.guaranteed_bitrate_mbps / capacity
        if share < LARGE_SLICE_CAPACITY_SHARE:
            return None

        return ConflictFinding(
            conflict_type="bandwidth",
            severity="advisory",
            details=(
                f"This slice would reserve {share:.0%} of total network capacity "
                f"({new_slice.guaranteed_bitrate_mbps:.0f} of {capacity:.0f} Mbps), leaving "
                "little headroom for future provisioning."
            ),
            suggestions=[
                "Confirm the guaranteed rate reflects sustained rather than peak demand",
                "Move burst capacity into the maximum bitrate instead",
            ],
        )

    # --- aggregation -------------------------------------------------------------

    def _build_report(self, findings: list[ConflictFinding]) -> ConflictReport:
        """Rank findings, merge remediations and produce the report."""
        if not findings:
            return ConflictReport(
                has_conflict=False,
                conflict_type=None,
                details="No conflicts detected. The slice is valid and ready for deployment.",
                suggestions=[],
                findings=[],
            )

        order = {"blocking": 0, "warning": 1, "advisory": 2}
        findings.sort(key=lambda f: order[f.severity])

        blocking = [f for f in findings if f.severity == "blocking"]
        primary = findings[0]

        # Merge remediations; blocking fixes win over advisory ones for the same field.
        auto_remediation: dict = {}
        for finding in reversed(findings):
            auto_remediation.update(finding.remediation)

        if blocking:
            summary = (
                f"{len(blocking)} blocking conflict(s) prevent deployment"
                + (f", plus {len(findings) - len(blocking)} advisory finding(s)"
                   if len(findings) > len(blocking) else "")
                + ": "
                + " ".join(f.details for f in blocking)
            )
        else:
            summary = (
                f"Deployment permitted with {len(findings)} advisory finding(s): "
                + " ".join(f.details for f in findings)
            )

        suggestions: list[str] = []
        for finding in findings:
            for suggestion in finding.suggestions:
                if suggestion not in suggestions:
                    suggestions.append(suggestion)

        logger.info(
            "Conflict check produced %d finding(s) (%d blocking)", len(findings), len(blocking)
        )

        return ConflictReport(
            has_conflict=bool(blocking),
            conflict_type=primary.conflict_type,
            details=summary,
            suggestions=suggestions,
            findings=findings,
            auto_remediation=auto_remediation,
        )

    def apply_remediation(self, config: SliceConfig, report: ConflictReport) -> SliceConfig:
        """Return a copy of ``config`` with the report's suggested changes applied."""
        if not report.auto_remediation:
            return config
        payload = config.model_dump()
        payload.update(report.auto_remediation)
        return SliceConfig(**payload)


conflict_detector = ConflictDetector()
