"""Tests for the configuration exporters."""

from __future__ import annotations

import json
import uuid

import pytest
import yaml

from models.slice_models import SliceConfig
from services.exporters import EXPORT_FORMATS, export_all, export_slice, to_yaml


def make_slice(**overrides) -> SliceConfig:
    payload = {
        "slice_id": str(uuid.uuid4()),
        "name": "Apollo Critical Care",
        "sst": 2,
        "sd": "0x0000a1",
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
        "status": "active",
    }
    payload.update(overrides)
    return SliceConfig(**payload)


class TestYamlWriter:
    def test_nested_structures_round_trip(self) -> None:
        data = {"a": 1, "b": {"c": "text", "d": [1, 2, 3]}, "e": [{"f": True}]}
        assert yaml.safe_load(to_yaml(data)) == data

    def test_ambiguous_strings_are_quoted(self) -> None:
        data = {"a": "true", "b": "null", "c": "123", "d": "yes"}
        loaded = yaml.safe_load(to_yaml(data))
        assert all(isinstance(value, str) for value in loaded.values())

    def test_strings_with_colons_survive(self) -> None:
        data = {"note": "priority: high", "path": "/api/slices"}
        assert yaml.safe_load(to_yaml(data)) == data

    def test_empty_collections_render_as_empty(self) -> None:
        assert yaml.safe_load(to_yaml({"a": [], "b": {}})) == {"a": [], "b": {}}


class TestExportFormats:
    @pytest.mark.parametrize("fmt", EXPORT_FORMATS)
    def test_every_format_produces_parseable_output(self, fmt: str) -> None:
        content, media_type = export_slice(make_slice(), fmt)
        assert content.strip()
        if media_type == "application/json":
            assert json.loads(content)
        else:
            assert yaml.safe_load(content)

    def test_an_unknown_format_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unknown export format"):
            export_slice(make_slice(), "not-a-format")


class TestKubernetesExport:
    def test_resource_shape_and_labels(self) -> None:
        config = make_slice()
        document = yaml.safe_load(export_slice(config, "kubernetes")[0])
        assert document["kind"] == "NetworkSlice"
        assert document["metadata"]["labels"]["helix.io/slice-id"] == config.slice_id
        assert document["spec"]["snssai"]["sst"] == 2
        assert document["spec"]["qos"]["fiveQi"] == 69

    def test_resource_names_are_kubernetes_safe(self) -> None:
        document = yaml.safe_load(
            export_slice(make_slice(name="Apollo // Critical CARE (Chennai)!"), "kubernetes")[0]
        )
        name = document["metadata"]["name"]
        assert name == name.lower()
        assert all(char.isalnum() or char == "-" for char in name)
        assert not name.startswith("-") and not name.endswith("-")
        assert len(name) <= 63


class TestSnssaiExport:
    def test_carries_the_full_qos_profile(self) -> None:
        document = yaml.safe_load(export_slice(make_slice(), "snssai")[0])
        assert document["sNssai"]["sd"] == "0000a1", "the 0x prefix is not part of the SD field"
        assert document["qosProfile"]["packetDelayBudgetMs"] > 0
        assert document["qosProfile"]["arp"]["priorityLevel"] == 1

    def test_high_priority_slices_are_not_preemptable(self) -> None:
        arp = yaml.safe_load(export_slice(make_slice(arp_priority=1), "snssai")[0])["qosProfile"]["arp"]
        assert arp["preemptionVulnerability"] == "NOT_PREEMPTABLE"

    def test_low_priority_slices_are_preemptable(self) -> None:
        arp = yaml.safe_load(export_slice(make_slice(arp_priority=12), "snssai")[0])["qosProfile"]["arp"]
        assert arp["preemptionVulnerability"] == "PREEMPTABLE"
        assert arp["preemptionCapability"] == "NOT_PREEMPT"


class TestOpen5gsExport:
    def test_session_profile_shape(self) -> None:
        document = yaml.safe_load(export_slice(make_slice(), "open5gs")[0])
        session = document["slice"][0]["session"][0]
        assert document["slice"][0]["sst"] == 2
        assert session["qos"]["index"] == 69
        assert session["ambr"]["downlink"]["value"] == 100


class TestFlowRuleExport:
    def test_falls_back_to_derived_rules_when_nothing_is_installed(self) -> None:
        document = json.loads(export_slice(make_slice(), "flow-rules")[0])
        assert document["ruleCount"] > 0
        assert document["installed"] is False
        assert document["rules"][0]["match"]["sd"] == "0x0000a1"


class TestBulkExport:
    def test_yaml_bulk_export_is_a_multi_document_stream(self) -> None:
        configs = [make_slice(sd=f"0x0000{i:02x}") for i in range(3)]
        content, _ = export_all(configs, "kubernetes")
        assert len(list(yaml.safe_load_all(content))) == 3

    def test_json_bulk_export_is_an_array(self) -> None:
        configs = [make_slice(sd=f"0x0001{i:02x}") for i in range(2)]
        payload = json.loads(export_all(configs, "json")[0])
        assert isinstance(payload, list)
        assert len(payload) == 2
