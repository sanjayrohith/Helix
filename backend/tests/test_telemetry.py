"""Tests for the telemetry engine and SLA monitor."""

from __future__ import annotations

import uuid

import pytest

from models.slice_models import SliceConfig
from services.sla_monitor import SlaMonitor, derive_target
from services.telemetry import SliceRuntimeState, TelemetryEngine, telemetry_engine


def make_slice(**overrides) -> SliceConfig:
    payload = {
        "slice_id": str(uuid.uuid4()),
        "name": "Monitored Slice",
        "sst": 2,
        "sd": "0x00e000",
        "qos_5qi": 69,
        "arp_priority": 2,
        "guaranteed_bitrate_mbps": 100.0,
        "max_bitrate_mbps": 200.0,
        "latency_ms": 10,
        "security_level": "high",
        "isolation": "dedicated",
        "device_count": 1000,
        "use_case": "healthcare",
        "location": "Chennai",
        "status": "active",
    }
    payload.update(overrides)
    return SliceConfig(**payload)


@pytest.fixture
def engine() -> TelemetryEngine:
    return TelemetryEngine(history_size=50)


class TestSampling:
    def test_a_sample_stays_within_its_declared_bounds(self, engine: TelemetryEngine) -> None:
        sample = engine.sample(make_slice())
        assert sample.throughput_mbps >= 0
        assert sample.latency_ms > 0
        assert 0 <= sample.packet_loss_percent <= 100
        assert 0 <= sample.prb_utilization_percent <= 100
        assert 0 <= sample.availability_percent <= 100

    def test_throughput_never_exceeds_the_maximum_bitrate(self, engine: TelemetryEngine) -> None:
        config = make_slice(guaranteed_bitrate_mbps=100.0, max_bitrate_mbps=120.0)
        for _ in range(80):
            assert engine.sample(config).throughput_mbps <= config.max_bitrate_mbps

    def test_active_devices_never_exceed_the_population(self, engine: TelemetryEngine) -> None:
        config = make_slice(device_count=500)
        for _ in range(40):
            assert engine.sample(config).active_devices <= 500

    def test_history_is_capped_at_the_ring_buffer_size(self, engine: TelemetryEngine) -> None:
        config = make_slice()
        for _ in range(200):
            engine.sample(config)
        assert len(engine.history(config.slice_id)) == 50

    def test_stricter_isolation_yields_lower_jitter(self, engine: TelemetryEngine) -> None:
        shared = make_slice(sd="0x00e001", isolation="shared")
        strict = make_slice(sd="0x00e002", isolation="strict")
        for _ in range(60):
            engine.sample(shared)
            engine.sample(strict)
        assert (
            engine.averages(strict.slice_id, 60)["jitter_ms"]
            < engine.averages(shared.slice_id, 60)["jitter_ms"]
        )

    def test_an_idle_slice_still_delivers_what_was_offered(self, engine: TelemetryEngine) -> None:
        config = make_slice()
        for _ in range(30):
            engine.sample(config)
        assert engine.averages(config.slice_id, 30)["delivery_ratio"] > 0.95


class TestLifecycle:
    def test_forget_drops_all_state_for_a_slice(self, engine: TelemetryEngine) -> None:
        config = make_slice()
        engine.sample(config)
        engine.forget(config.slice_id)
        assert engine.latest(config.slice_id) is None
        assert engine.history(config.slice_id) == []

    def test_sample_all_garbage_collects_removed_slices(self, engine: TelemetryEngine) -> None:
        first, second = make_slice(sd="0x00e003"), make_slice(sd="0x00e004")
        engine.sample_all([first, second])
        engine.sample_all([first])
        assert engine.latest(second.slice_id) is None
        assert engine.stats()["tracked_slices"] == 1

    def test_averages_are_empty_without_samples(self, engine: TelemetryEngine) -> None:
        assert engine.averages("unknown-slice") == {}


class TestNetworkSummary:
    def test_an_empty_network_reports_zeroes(self, engine: TelemetryEngine) -> None:
        summary = engine.network_summary()
        assert summary.total_throughput_mbps == 0.0
        assert summary.slices_meeting_sla == 0

    def test_summary_totals_the_latest_samples(self, engine: TelemetryEngine) -> None:
        configs = [make_slice(sd=f"0x00f0{i:02x}") for i in range(3)]
        engine.sample_all(configs)
        expected = sum(engine.latest(c.slice_id).throughput_mbps for c in configs)
        assert engine.network_summary().total_throughput_mbps == pytest.approx(expected, rel=1e-6)


class TestSlaTargets:
    def test_targets_are_derived_from_the_slice_configuration(self) -> None:
        target = derive_target(make_slice(latency_ms=10, guaranteed_bitrate_mbps=100.0))
        assert target.max_latency_ms > 10
        assert target.min_throughput_mbps == pytest.approx(80.0)

    def test_critical_slices_get_the_strictest_availability_target(self) -> None:
        critical = derive_target(make_slice(security_level="critical"))
        standard = derive_target(make_slice(security_level="standard"))
        assert critical.min_availability_percent > standard.min_availability_percent

    def test_urllc_gets_a_tighter_loss_target_than_mmtc(self) -> None:
        assert (
            derive_target(make_slice(sst=2)).max_packet_loss_percent
            < derive_target(make_slice(sst=3)).max_packet_loss_percent
        )


class TestSlaEvaluation:
    def test_a_slice_without_telemetry_is_unknown(self) -> None:
        evaluation = SlaMonitor().evaluate(make_slice())
        assert evaluation.status == "unknown"
        assert evaluation.breaches == []

    def test_a_healthy_slice_meets_its_sla(self) -> None:
        config = make_slice()
        telemetry_engine.forget(config.slice_id)
        for _ in range(20):
            telemetry_engine.sample(config)
        evaluation = SlaMonitor().evaluate(config)
        assert evaluation.status == "meeting"
        assert evaluation.compliance_score == 100.0
        telemetry_engine.forget(config.slice_id)

    def test_availability_is_not_graded_from_too_few_intervals(self) -> None:
        """A single early outage must not read as an availability breach."""
        config = make_slice(security_level="critical")
        telemetry_engine.forget(config.slice_id)
        state = SliceRuntimeState(slice_id=config.slice_id)
        telemetry_engine._state[config.slice_id] = state
        for index in range(15):
            state.outage_ticks_remaining = 1 if index == 0 else 0
            telemetry_engine.sample(config)

        breached = {b.kpi for b in SlaMonitor().evaluate(config).breaches}
        assert "availability" not in breached
        telemetry_engine.forget(config.slice_id)

    def test_a_congested_slice_is_reported_as_violating(self) -> None:
        config = make_slice(isolation="shared", security_level="critical", latency_ms=5)
        telemetry_engine.forget(config.slice_id)
        state = SliceRuntimeState(slice_id=config.slice_id)
        telemetry_engine._state[config.slice_id] = state
        for _ in range(80):
            state.congestion = 0.95
            state.outage_ticks_remaining = 1
            telemetry_engine.sample(config)

        evaluation = SlaMonitor().evaluate(config)
        assert evaluation.status == "violated"
        assert evaluation.compliance_score < 50
        breached = {breach.kpi for breach in evaluation.breaches}
        assert {"latency", "packet_loss", "availability"} <= breached
        telemetry_engine.forget(config.slice_id)


class TestTransitions:
    def test_only_status_changes_are_reported(self) -> None:
        monitor = SlaMonitor()
        config = make_slice()
        telemetry_engine.forget(config.slice_id)
        for _ in range(15):
            telemetry_engine.sample(config)

        first = monitor.evaluate_all([config])
        assert len(monitor.transitions(first)) == 1, "unknown -> meeting is a transition"
        assert monitor.transitions(monitor.evaluate_all([config])) == [], "steady state is silent"
        telemetry_engine.forget(config.slice_id)

    def test_status_counts_cover_every_status(self) -> None:
        counts = SlaMonitor().status_counts([])
        assert set(counts) == {"meeting", "at_risk", "violated", "unknown"}
