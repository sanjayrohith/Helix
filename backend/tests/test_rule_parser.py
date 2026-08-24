"""Tests for the deterministic intent parser."""

from __future__ import annotations

import pytest

from services.rule_parser import (
    RuleBasedIntentParser,
    extract_bitrate_mbps,
    extract_device_count,
    extract_latency_ms,
    extract_location,
    select_profile,
)


@pytest.fixture
def parser() -> RuleBasedIntentParser:
    return RuleBasedIntentParser()


class TestBitrateExtraction:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("give me 500 Mbps", 500.0),
            ("we need 2 Gbps of throughput", 2000.0),
            ("800 kbps is enough", 0.8),
            ("1.5 gbps sustained", 1500.0),
            ("throughput of 250 mb/s", 250.0),
        ],
    )
    def test_units_normalise_to_mbps(self, text: str, expected: float) -> None:
        assert extract_bitrate_mbps(text) == pytest.approx(expected)

    def test_picks_the_largest_mentioned_rate(self) -> None:
        assert extract_bitrate_mbps("between 100 Mbps and 1 Gbps") == pytest.approx(1000.0)

    def test_returns_none_without_a_rate(self) -> None:
        assert extract_bitrate_mbps("a slice for the hospital") is None


class TestLatencyExtraction:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("under 5ms latency", 5.0),
            ("1 millisecond budget", 1.0),
            ("500 microseconds", 0.5),
            ("2 seconds is fine", 2000.0),
        ],
    )
    def test_units_normalise_to_ms(self, text: str, expected: float) -> None:
        assert extract_latency_ms(text) == pytest.approx(expected)

    def test_picks_the_tightest_requirement(self) -> None:
        assert extract_latency_ms("under 20 ms, ideally 4 ms") == pytest.approx(4.0)


class TestDeviceExtraction:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("5000 employees", 5000),
            ("50k sensors", 50_000),
            ("2 million meters", 2_000_000),
            ("1,200 vehicles", 1200),
        ],
    )
    def test_scale_suffixes(self, text: str, expected: int) -> None:
        assert extract_device_count(text) == expected


class TestLocationExtraction:
    def test_finds_place_after_preposition(self) -> None:
        assert extract_location("broadband in Mumbai for the office") == "Mumbai"

    def test_handles_multi_word_places(self) -> None:
        assert extract_location("coverage at New York City downtown") == "New York City"

    def test_returns_none_when_absent(self) -> None:
        assert extract_location("a slice for sensors") is None


class TestProfileSelection:
    @pytest.mark.parametrize(
        ("text", "expected_key"),
        [
            ("remote surgery for the hospital", "healthcare"),
            ("smart meters and iot sensors", "iot"),
            ("autonomous vehicle platooning", "autonomous-vehicles"),
            ("factory robots on the assembly line", "industrial-automation"),
            ("cloud gaming and vr", "gaming-xr"),
            ("live broadcast from the stadium", "broadcast"),
            ("first responder emergency comms", "emergency"),
        ],
    )
    def test_keyword_routing(self, text: str, expected_key: str) -> None:
        profile, score, _ = select_profile(text)
        assert profile.key == expected_key
        assert score > 0

    def test_unmatched_text_falls_back_to_broadband(self) -> None:
        profile, score, hits = select_profile("qwertyuiop zxcvbnm")
        assert profile.key == "broadband"
        assert score == 0
        assert hits == []


class TestParse:
    def test_healthcare_intent_produces_urllc_critical_slice(self, parser) -> None:
        config, trace = parser.parse(
            "Ultra reliable slice for remote surgery at Apollo Hospital Chennai with 3ms latency"
        )
        assert config["sst"] == 2
        assert config["qos_5qi"] == 69
        assert config["arp_priority"] == 1
        assert config["security_level"] == "critical"
        assert config["isolation"] == "strict"
        assert config["latency_ms"] == 3
        assert config["location"].startswith("Apollo")
        assert trace.matched_profile == "healthcare"

    def test_explicit_bitrate_overrides_the_profile_default(self, parser) -> None:
        config, _ = parser.parse("Broadband slice with 750 Mbps for the campus")
        assert config["guaranteed_bitrate_mbps"] == 750.0
        assert config["max_bitrate_mbps"] >= config["guaranteed_bitrate_mbps"]

    def test_isolation_phrase_is_honoured(self, parser) -> None:
        config, _ = parser.parse("Shared best-effort slice for browsing")
        assert config["isolation"] == "shared"

    def test_security_phrase_raises_the_level(self, parser) -> None:
        config, _ = parser.parse("Encrypted slice for iot sensors")
        assert config["security_level"] == "high"

    def test_allocates_distinct_slice_differentiators(self, parser) -> None:
        first, _ = parser.parse("iot sensors")
        second, _ = parser.parse("iot sensors")
        assert first["sd"] != second["sd"]
        assert first["sd"].startswith("0x") and len(first["sd"]) == 8

    def test_every_sample_intent_parses(self, parser, intent_samples) -> None:
        for intent in intent_samples.values():
            config, trace = parser.parse(intent)
            assert config["slice_id"]
            assert config["status"] == "pending"
            assert trace.derived, "the trace should explain at least one field"

    def test_trace_explains_each_derived_field(self, parser) -> None:
        _, trace = parser.parse("hospital slice with 4ms latency in Chennai")
        assert "latency_ms" in trace.derived
        assert "location" in trace.derived
        assert "use_case" in trace.derived
