"""Tests for the slice registry."""

from __future__ import annotations

import uuid

import pytest

from models.slice_models import SliceConfig
from services.slice_registry import SliceRegistry


def make_slice(**overrides) -> SliceConfig:
    payload = {
        "slice_id": str(uuid.uuid4()),
        "name": "Registry Slice",
        "sst": 1,
        "sd": "0x000101",
        "qos_5qi": 9,
        "arp_priority": 5,
        "guaranteed_bitrate_mbps": 100.0,
        "max_bitrate_mbps": 200.0,
        "latency_ms": 20,
        "security_level": "standard",
        "isolation": "shared",
        "device_count": 100,
        "use_case": "broadband",
        "location": "Mumbai",
        "status": "active",
    }
    payload.update(overrides)
    return SliceConfig(**payload)


@pytest.fixture
def registry() -> SliceRegistry:
    instance = SliceRegistry()
    instance.clear()
    return instance


class TestCrud:
    def test_add_then_read_back(self, registry: SliceRegistry) -> None:
        config = registry.add_slice(make_slice())
        assert registry.get_slice(config.slice_id) is not None
        assert registry.count() == 1

    def test_update_revalidates_and_stamps_updated_at(self, registry: SliceRegistry) -> None:
        config = registry.add_slice(make_slice())
        updated = registry.update_slice(config.slice_id, {"guaranteed_bitrate_mbps": 250.0})
        assert updated is not None
        assert updated.guaranteed_bitrate_mbps == 250.0
        assert updated.updated_at is not None

    def test_update_raises_a_low_max_bitrate_to_the_guaranteed_rate(
        self, registry: SliceRegistry
    ) -> None:
        config = registry.add_slice(make_slice(guaranteed_bitrate_mbps=100.0, max_bitrate_mbps=200.0))
        updated = registry.update_slice(config.slice_id, {"guaranteed_bitrate_mbps": 500.0})
        assert updated.max_bitrate_mbps >= 500.0

    def test_update_of_a_missing_slice_returns_none(self, registry: SliceRegistry) -> None:
        assert registry.update_slice("does-not-exist", {"latency_ms": 5}) is None

    def test_delete_returns_the_removed_slice(self, registry: SliceRegistry) -> None:
        config = registry.add_slice(make_slice())
        assert registry.delete_slice(config.slice_id).slice_id == config.slice_id
        assert registry.delete_slice(config.slice_id) is None

    def test_set_status_transitions_the_slice(self, registry: SliceRegistry) -> None:
        config = registry.add_slice(make_slice())
        assert registry.set_status(config.slice_id, "pending").status == "pending"


class TestCapacityAccounting:
    def test_only_active_slices_consume_bandwidth(self, registry: SliceRegistry) -> None:
        registry.add_slice(make_slice(guaranteed_bitrate_mbps=100.0, status="active"))
        registry.add_slice(make_slice(sd="0x000102", guaranteed_bitrate_mbps=400.0, status="pending"))
        assert registry.get_total_active_bandwidth() == 100.0

    def test_available_bandwidth_never_goes_negative(self, registry: SliceRegistry) -> None:
        registry.add_slice(make_slice(guaranteed_bitrate_mbps=99_000.0))
        assert registry.get_available_bandwidth() == 0.0

    def test_stats_counts_conflicts_separately(self, registry: SliceRegistry) -> None:
        registry.add_slice(make_slice(status="active", guaranteed_bitrate_mbps=120.0))
        registry.add_slice(make_slice(sd="0x000103", status="conflict"))
        stats = registry.get_stats()
        assert stats.total_slices == 2
        assert stats.active_slices == 1
        assert stats.conflict_count == 1
        assert stats.total_bandwidth_used_mbps == 120.0


class TestCollisionChecks:
    def test_detects_an_snssai_collision(self, registry: SliceRegistry) -> None:
        registry.add_slice(make_slice(sst=2, sd="0x00beef"))
        assert registry.check_snssai_exists(2, "0x00beef") is True
        assert registry.check_snssai_exists(2, "0x00BEEF") is True, "match must be case-insensitive"
        assert registry.check_snssai_exists(1, "0x00beef") is False

    def test_excluding_a_slice_ignores_its_own_snssai(self, registry: SliceRegistry) -> None:
        config = registry.add_slice(make_slice(sst=2, sd="0x00cafe"))
        assert registry.check_snssai_exists(2, "0x00cafe", exclude_slice_id=config.slice_id) is False

    def test_arp_one_is_only_reserved_by_critical_slices(self, registry: SliceRegistry) -> None:
        registry.add_slice(make_slice(arp_priority=1, security_level="high"))
        assert registry.has_critical_arp_one() is False
        registry.add_slice(make_slice(sd="0x000104", arp_priority=1, security_level="critical"))
        assert registry.has_critical_arp_one() is True

    def test_next_available_sd_skips_taken_values(self, registry: SliceRegistry) -> None:
        registry.add_slice(make_slice(sst=1, sd="0x000100"))
        registry.add_slice(make_slice(sst=1, sd="0x000101"))
        assert registry.next_available_sd(1) == "0x000102"


class TestQueriesAndBreakdown:
    def test_find_by_use_case_and_location_are_case_insensitive(
        self, registry: SliceRegistry
    ) -> None:
        registry.add_slice(make_slice(use_case="healthcare", location="Chennai"))
        assert len(registry.find_by_use_case("HEALTHCARE")) == 1
        assert len(registry.find_by_location("chennai")) == 1

    def test_breakdown_groups_by_every_dimension(self, registry: SliceRegistry) -> None:
        registry.add_slice(make_slice(sst=1, use_case="broadband", device_count=10))
        registry.add_slice(make_slice(sd="0x000105", sst=3, use_case="iot", device_count=90))
        breakdown = registry.breakdown()
        assert breakdown["by_sst"] == {1: 1, 3: 1}
        assert breakdown["by_use_case"] == {"broadband": 1, "iot": 1}
        assert breakdown["total_devices"] == 100
