"""Tests for the admission-control conflict engine."""

from __future__ import annotations

import uuid

import pytest

from core.config import settings
from models.slice_models import SliceConfig
from services.conflict_detector import ConflictDetector
from services.slice_registry import slice_registry


def make_slice(**overrides) -> SliceConfig:
    payload = {
        "slice_id": str(uuid.uuid4()),
        "name": "Candidate",
        "sst": 1,
        "sd": "0x00f000",
        "qos_5qi": 9,
        "arp_priority": 5,
        "guaranteed_bitrate_mbps": 50.0,
        "max_bitrate_mbps": 100.0,
        "latency_ms": 300,
        "security_level": "standard",
        "isolation": "shared",
        "device_count": 100,
        "use_case": "broadband",
        "location": "Mumbai",
        "status": "pending",
    }
    payload.update(overrides)
    return SliceConfig(**payload)


@pytest.fixture
def empty_network() -> ConflictDetector:
    """A network with no active slices, restored afterwards."""
    saved = slice_registry.get_all_slices()
    slice_registry.clear()
    yield ConflictDetector()
    slice_registry.clear()
    for config in saved:
        slice_registry.add_slice(config)


def types_of(report) -> set[str]:
    return {finding.conflict_type for finding in report.findings}


class TestCleanSlice:
    def test_a_valid_slice_produces_no_findings(self, empty_network) -> None:
        report = empty_network.detect_conflicts(make_slice())
        assert report.has_conflict is False
        assert report.findings == []
        assert report.conflict_type is None


class TestBlockingChecks:
    def test_bandwidth_over_capacity_blocks(self, empty_network) -> None:
        report = empty_network.detect_conflicts(
            make_slice(guaranteed_bitrate_mbps=settings.total_bandwidth_mbps + 1)
        )
        assert report.has_conflict is True
        assert "bandwidth" in types_of(report)

    def test_snssai_collision_blocks_and_proposes_a_free_sd(self, empty_network) -> None:
        slice_registry.add_slice(make_slice(sst=2, sd="0x00aaaa", status="active"))
        report = empty_network.detect_conflicts(make_slice(sst=2, sd="0x00aaaa"))
        assert report.has_conflict is True
        assert report.auto_remediation["sd"] != "0x00aaaa"

    def test_arp_one_collision_blocks_and_proposes_arp_two(self, empty_network) -> None:
        slice_registry.add_slice(
            make_slice(sd="0x00bbbb", arp_priority=1, security_level="critical", status="active")
        )
        report = empty_network.detect_conflicts(make_slice(arp_priority=1))
        assert report.has_conflict is True
        assert report.auto_remediation["arp_priority"] == 2

    def test_large_population_needs_strict_isolation(self, empty_network) -> None:
        report = empty_network.detect_conflicts(
            make_slice(device_count=settings.max_devices_shared_isolation + 1, isolation="shared")
        )
        assert report.has_conflict is True
        assert report.auto_remediation["isolation"] == "strict"

    def test_strict_isolation_satisfies_the_population_rule(self, empty_network) -> None:
        report = empty_network.detect_conflicts(
            make_slice(
                device_count=settings.max_devices_shared_isolation + 1,
                isolation="strict",
                sst=3,
                guaranteed_bitrate_mbps=200.0,
            )
        )
        assert "regulatory" not in types_of(report)


class TestNonBlockingChecks:
    def test_latency_tighter_than_the_5qi_budget_only_warns(self, empty_network) -> None:
        report = empty_network.detect_conflicts(make_slice(qos_5qi=9, latency_ms=2))
        assert report.has_conflict is False, "an unrealistic target should not block deployment"
        assert "latency" in types_of(report)
        assert report.auto_remediation, "the engine should propose a better 5QI or budget"

    def test_critical_security_on_shared_isolation_warns(self, empty_network) -> None:
        report = empty_network.detect_conflicts(
            make_slice(security_level="critical", isolation="shared")
        )
        assert report.has_conflict is False
        assert "isolation" in types_of(report)

    def test_implausible_per_device_bandwidth_is_advisory(self, empty_network) -> None:
        report = empty_network.detect_conflicts(
            make_slice(sst=1, device_count=100_000, guaranteed_bitrate_mbps=1.0, isolation="strict")
        )
        assert report.has_conflict is False
        assert "device_density" in types_of(report)

    def test_mmtc_tolerates_a_much_lower_per_device_rate(self, empty_network) -> None:
        report = empty_network.detect_conflicts(
            make_slice(sst=3, device_count=5000, guaranteed_bitrate_mbps=30.0)
        )
        assert "device_density" not in types_of(report)

    def test_dominating_the_network_is_advisory_only(self, empty_network) -> None:
        report = empty_network.detect_conflicts(
            make_slice(guaranteed_bitrate_mbps=settings.total_bandwidth_mbps * 0.6)
        )
        assert report.has_conflict is False
        assert "bandwidth" in types_of(report)


class TestAggregation:
    def test_every_problem_is_reported_not_just_the_first(self, empty_network) -> None:
        slice_registry.add_slice(
            make_slice(sst=2, sd="0x00cccc", arp_priority=1, security_level="critical", status="active")
        )
        report = empty_network.detect_conflicts(
            make_slice(
                sst=2,
                sd="0x00cccc",
                arp_priority=1,
                security_level="critical",
                isolation="shared",
                device_count=50_000,
                qos_5qi=69,
                latency_ms=1,
            )
        )
        assert len(report.blocking_findings) >= 3
        assert {"snssai", "arp", "regulatory"} <= types_of(report)

    def test_findings_are_ordered_most_severe_first(self, empty_network) -> None:
        report = empty_network.detect_conflicts(
            make_slice(device_count=50_000, isolation="shared", qos_5qi=9, latency_ms=1)
        )
        severities = [finding.severity for finding in report.findings]
        assert severities == sorted(severities, key=lambda s: {"blocking": 0, "warning": 1, "advisory": 2}[s])

    def test_applying_the_remediation_clears_the_blocking_conflicts(self, empty_network) -> None:
        slice_registry.add_slice(
            make_slice(sst=2, sd="0x00dddd", arp_priority=1, security_level="critical", status="active")
        )
        candidate = make_slice(
            sst=2,
            sd="0x00dddd",
            arp_priority=1,
            security_level="critical",
            isolation="shared",
            device_count=50_000,
        )
        report = empty_network.detect_conflicts(candidate)
        assert report.has_conflict is True

        fixed = empty_network.apply_remediation(candidate, report)
        assert empty_network.detect_conflicts(fixed).has_conflict is False

    def test_suggestions_are_deduplicated(self, empty_network) -> None:
        report = empty_network.detect_conflicts(
            make_slice(security_level="critical", isolation="shared", device_count=50_000)
        )
        assert len(report.suggestions) == len(set(report.suggestions))

    def test_apply_remediation_is_a_no_op_without_proposals(self, empty_network) -> None:
        candidate = make_slice()
        report = empty_network.detect_conflicts(candidate)
        assert empty_network.apply_remediation(candidate, report) is candidate
