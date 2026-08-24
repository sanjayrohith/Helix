"""Export slice configurations into formats other systems can consume.

A slice that exists only inside HELIX is a demo. These exporters turn a
validated configuration into artefacts an operator can actually apply: an
Open5GS-style subscriber/session profile, a Kubernetes NetworkSlice custom
resource for GitOps pipelines, a 3GPP-shaped S-NSSAI descriptor, and the
OpenFlow rules the controller installed.

YAML is emitted by a small local writer rather than a PyYAML dependency; the
documents are shallow, fully known and never round-tripped back in.
"""

from __future__ import annotations

import json
from typing import Any

from core.telecom import SST_NAMES, get_qos, packet_delay_budget
from models.slice_models import SliceConfig
from services.sdn_controller import sdn_controller

EXPORT_FORMATS = ("open5gs", "kubernetes", "snssai", "flow-rules", "json")


# --- minimal YAML writer ------------------------------------------------------


def _looks_numeric(text: str) -> bool:
    """True when a parser would read this string back as a number.

    This matters for fields like the Slice Differentiator: an SD of '000002'
    emitted bare comes back as the integer 2, silently corrupting the export.
    """
    candidate = text.strip()
    if not candidate:
        return False
    try:
        float(candidate)
        return True
    except ValueError:
        pass
    # YAML 1.1 also reads a leading 0 as octal and 0x as hexadecimal.
    stripped = candidate.lstrip("+-")
    return stripped.startswith(("0x", "0o", "0b")) and len(stripped) > 2


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    # Quote anything a parser could read back as a different type.
    if text == "" or text[0] in "&*?|-<>=!%@`{[\"'#" or ":" in text or text.strip() != text:
        return json.dumps(text)
    if text.lower() in {"true", "false", "null", "yes", "no", "on", "off", "~"}:
        return json.dumps(text)
    if _looks_numeric(text):
        return json.dumps(text)
    return text


def to_yaml(data: Any, indent: int = 0) -> str:
    """Serialise nested dicts and lists of scalars into YAML."""
    pad = "  " * indent
    lines: list[str] = []

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict) and value:
                lines.append(f"{pad}{key}:")
                lines.append(to_yaml(value, indent + 1))
            elif isinstance(value, list) and value:
                lines.append(f"{pad}{key}:")
                for item in value:
                    if isinstance(item, dict):
                        rendered = to_yaml(item, indent + 2).lstrip()
                        lines.append(f"{pad}  - {rendered}")
                    else:
                        lines.append(f"{pad}  - {_yaml_scalar(item)}")
            elif isinstance(value, (dict, list)):
                lines.append(f"{pad}{key}: {'{}' if isinstance(value, dict) else '[]'}")
            else:
                lines.append(f"{pad}{key}: {_yaml_scalar(value)}")
        return "\n".join(lines)

    return f"{pad}{_yaml_scalar(data)}"


# --- exporters -----------------------------------------------------------------


def to_snssai(config: SliceConfig) -> dict:
    """A 3GPP-shaped S-NSSAI descriptor with its QoS profile."""
    qos = get_qos(config.qos_5qi)
    return {
        "sNssai": {
            "sst": config.sst,
            "sstName": SST_NAMES.get(config.sst, "unknown"),
            "sd": config.sd[2:],
        },
        "qosProfile": {
            "5qi": config.qos_5qi,
            "resourceType": qos.resource_type if qos else "Non-GBR",
            "priorityLevel": qos.priority_level if qos else 90,
            "packetDelayBudgetMs": packet_delay_budget(config.qos_5qi),
            "packetErrorRate": qos.packet_error_rate if qos else 1e-6,
            "arp": {
                "priorityLevel": config.arp_priority,
                "preemptionCapability": (
                    "MAY_PREEMPT" if config.arp_priority <= 5 else "NOT_PREEMPT"
                ),
                "preemptionVulnerability": (
                    "NOT_PREEMPTABLE" if config.arp_priority <= 2 else "PREEMPTABLE"
                ),
            },
            "gbrMbps": {"uplink": config.guaranteed_bitrate_mbps, "downlink": config.guaranteed_bitrate_mbps},
            "mbrMbps": {"uplink": config.max_bitrate_mbps, "downlink": config.max_bitrate_mbps},
        },
    }


def to_open5gs(config: SliceConfig) -> dict:
    """An Open5GS-style subscriber session profile for this slice."""
    return {
        "slice": [
            {
                "sst": config.sst,
                "sd": config.sd[2:],
                "default_indicator": config.arp_priority <= 2,
                "session": [
                    {
                        "name": _dnn(config),
                        "type": 3,  # IPv4v6
                        "qos": {
                            "index": config.qos_5qi,
                            "arp": {
                                "priority_level": config.arp_priority,
                                "pre_emption_capability": 1 if config.arp_priority <= 5 else 2,
                                "pre_emption_vulnerability": 2 if config.arp_priority <= 2 else 1,
                            },
                        },
                        "ambr": {
                            "uplink": {"value": int(config.max_bitrate_mbps), "unit": 3},
                            "downlink": {"value": int(config.max_bitrate_mbps), "unit": 3},
                        },
                    }
                ],
            }
        ],
        "ambr": {
            "uplink": {"value": int(config.max_bitrate_mbps), "unit": 3},
            "downlink": {"value": int(config.max_bitrate_mbps), "unit": 3},
        },
    }


def to_kubernetes(config: SliceConfig) -> dict:
    """A NetworkSlice custom resource for a GitOps pipeline."""
    return {
        "apiVersion": "networking.helix.io/v1alpha1",
        "kind": "NetworkSlice",
        "metadata": {
            "name": _k8s_name(config),
            "labels": {
                "helix.io/slice-id": config.slice_id,
                "helix.io/use-case": _k8s_label(config.use_case),
                "helix.io/sst": SST_NAMES.get(config.sst, "unknown"),
                "helix.io/location": _k8s_label(config.location),
            },
            "annotations": {
                "helix.io/display-name": config.name,
                "helix.io/created-at": config.created_at.isoformat(),
            },
        },
        "spec": {
            "snssai": {"sst": config.sst, "sd": config.sd[2:]},
            "qos": {
                "fiveQi": config.qos_5qi,
                "arpPriority": config.arp_priority,
                "guaranteedBitrateMbps": config.guaranteed_bitrate_mbps,
                "maxBitrateMbps": config.max_bitrate_mbps,
                "latencyBudgetMs": config.latency_ms,
            },
            "isolation": config.isolation,
            "securityLevel": config.security_level,
            "coverage": {"location": config.location, "expectedDevices": config.device_count},
        },
    }


def to_flow_rules(config: SliceConfig) -> dict:
    """The OpenFlow rules the controller installed for this slice."""
    from services.sdn_controller import build_flow_rules

    installed = sdn_controller.get_flow_rules(config.slice_id)
    rules = installed or [rule.as_dict() for rule in build_flow_rules(config)]
    return {
        "sliceId": config.slice_id,
        "sliceName": config.name,
        "installed": bool(installed),
        "ruleCount": len(rules),
        "rules": rules,
    }


def export_slice(config: SliceConfig, fmt: str) -> tuple[str, str]:
    """Render a slice in ``fmt``. Returns (content, media_type)."""
    if fmt == "json":
        return config.model_dump_json(indent=2), "application/json"

    builders = {
        "snssai": to_snssai,
        "open5gs": to_open5gs,
        "kubernetes": to_kubernetes,
        "flow-rules": to_flow_rules,
    }
    builder = builders.get(fmt)
    if builder is None:
        raise ValueError(f"Unknown export format '{fmt}'. Use one of: {', '.join(EXPORT_FORMATS)}")

    document = builder(config)
    if fmt == "flow-rules":
        return json.dumps(document, indent=2), "application/json"
    return to_yaml(document) + "\n", "application/yaml"


def export_all(configs: list[SliceConfig], fmt: str) -> tuple[str, str]:
    """Render several slices as one multi-document artefact."""
    if fmt == "json":
        payload = [json.loads(config.model_dump_json()) for config in configs]
        return json.dumps(payload, indent=2), "application/json"

    documents = [export_slice(config, fmt)[0].rstrip() for config in configs]
    if fmt == "flow-rules":
        return "[\n" + ",\n".join(documents) + "\n]", "application/json"
    return "---\n" + "\n---\n".join(documents) + "\n", "application/yaml"


# --- naming helpers --------------------------------------------------------------


def _dnn(config: SliceConfig) -> str:
    """Data Network Name derived from the use case."""
    return _k8s_label(config.use_case) or "internet"


def _k8s_label(value: str) -> str:
    """Lowercase, hyphenated, safe for a Kubernetes label value."""
    cleaned = "".join(char if char.isalnum() else "-" for char in value.lower())
    return "-".join(part for part in cleaned.split("-") if part)[:63]


def _k8s_name(config: SliceConfig) -> str:
    """A stable, valid resource name for a slice."""
    stem = _k8s_label(config.name)[:40].strip("-") or "slice"
    return f"{stem}-{config.slice_id[:8]}"
