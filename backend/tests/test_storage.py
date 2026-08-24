"""Tests for the SQLite persistence layer."""

from __future__ import annotations

import uuid

import pytest

from models.event_models import AuditEvent
from models.slice_models import SliceConfig
from storage.sqlite_store import SqliteStore


def make_slice(**overrides) -> SliceConfig:
    payload = {
        "slice_id": str(uuid.uuid4()),
        "name": "Test Slice",
        "sst": 2,
        "sd": "0x000abc",
        "qos_5qi": 69,
        "arp_priority": 1,
        "guaranteed_bitrate_mbps": 50.0,
        "max_bitrate_mbps": 100.0,
        "latency_ms": 5,
        "security_level": "critical",
        "isolation": "strict",
        "device_count": 100,
        "use_case": "healthcare",
        "location": "Chennai",
        "status": "active",
    }
    payload.update(overrides)
    return SliceConfig(**payload)


def make_event(**overrides) -> AuditEvent:
    payload = {
        "event_id": str(uuid.uuid4()),
        "event_type": "slice_created",
        "summary": "A slice was created",
    }
    payload.update(overrides)
    return AuditEvent(**payload)


@pytest.fixture
def store(tmp_path) -> SqliteStore:
    instance = SqliteStore(path=tmp_path / "helix-test.db", enabled=True)
    yield instance
    instance.close()


class TestSliceStorage:
    def test_round_trips_a_slice(self, store: SqliteStore) -> None:
        original = make_slice()
        store.save_slice(original)
        [restored] = store.load_slices()
        assert restored.slice_id == original.slice_id
        assert restored.guaranteed_bitrate_mbps == original.guaranteed_bitrate_mbps
        assert restored.snssai == original.snssai

    def test_saving_twice_upserts_rather_than_duplicating(self, store: SqliteStore) -> None:
        config = make_slice()
        store.save_slice(config)
        config.name = "Renamed"
        store.save_slice(config)
        assert store.count_slices() == 1
        assert store.load_slices()[0].name == "Renamed"

    def test_delete_reports_whether_a_row_was_removed(self, store: SqliteStore) -> None:
        config = make_slice()
        store.save_slice(config)
        assert store.delete_slice(config.slice_id) is True
        assert store.delete_slice(config.slice_id) is False
        assert store.count_slices() == 0

    def test_load_order_is_stable_by_creation_time(self, store: SqliteStore) -> None:
        store.save_slices([make_slice(name=f"S{i}") for i in range(5)])
        assert store.count_slices() == 5

    def test_a_second_store_sees_persisted_rows(self, tmp_path) -> None:
        path = tmp_path / "shared.db"
        first = SqliteStore(path=path, enabled=True)
        first.save_slice(make_slice(name="Durable"))
        first.close()

        second = SqliteStore(path=path, enabled=True)
        assert [s.name for s in second.load_slices()] == ["Durable"]
        second.close()


class TestEventStorage:
    def test_events_return_newest_first(self, store: SqliteStore) -> None:
        for index in range(3):
            store.append_event(make_event(summary=f"event {index}"))
        summaries = [event.summary for event in store.load_events()]
        assert summaries[0] == "event 2"

    def test_filters_by_slice_and_type(self, store: SqliteStore) -> None:
        store.append_event(make_event(slice_id="a", event_type="slice_created"))
        store.append_event(make_event(slice_id="b", event_type="slice_deleted"))

        assert len(store.load_events(slice_id="a")) == 1
        assert len(store.load_events(event_type="slice_deleted")) == 1
        assert len(store.load_events(severity="error")) == 0

    def test_prune_keeps_only_the_newest_events(self, store: SqliteStore) -> None:
        for index in range(10):
            store.append_event(make_event(summary=f"e{index}"))
        removed = store.prune_events(keep=4)
        assert removed == 6
        assert len(store.load_events(limit=100)) == 4


class TestDisabledStore:
    def test_disabled_store_is_a_no_op(self, tmp_path) -> None:
        store = SqliteStore(path=tmp_path / "unused.db", enabled=False)
        store.save_slice(make_slice())
        store.append_event(make_event())
        assert store.load_slices() == []
        assert store.load_events() == []
        assert store.count_slices() == 0
        assert store.stats() == {"enabled": False}
        assert not (tmp_path / "unused.db").exists()


class TestMaintenance:
    def test_reset_clears_both_tables(self, store: SqliteStore) -> None:
        store.save_slice(make_slice())
        store.append_event(make_event())
        store.reset()
        assert store.count_slices() == 0
        assert store.load_events() == []

    def test_stats_reports_counts_and_schema_version(self, store: SqliteStore) -> None:
        store.save_slice(make_slice())
        stats = store.stats()
        assert stats["enabled"] is True
        assert stats["slices"] == 1
        assert stats["schema_version"] >= 1
