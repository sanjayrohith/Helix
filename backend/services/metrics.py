"""Prometheus exposition for HELIX.

Written by hand rather than pulling in prometheus_client: HELIX exports a
fixed, small set of gauges derived from state it already tracks, so the
dependency would buy little. The output follows the text exposition format so
a standard Prometheus scrape or Grafana data source works unmodified.
"""

from __future__ import annotations

from core.config import settings
from services.sdn_controller import sdn_controller
from services.sla_monitor import sla_monitor
from services.slice_registry import slice_registry
from services.telemetry import telemetry_engine
from services.topology import topology_manager

# Label values are escaped per the exposition format.
_ESCAPES = str.maketrans({"\\": "\\\\", '"': '\\"', "\n": "\\n"})


def _escape(value: object) -> str:
    return str(value).translate(_ESCAPES)


class MetricsWriter:
    """Accumulates metric families in exposition-format order."""

    def __init__(self) -> None:
        self._lines: list[str] = []

    def family(self, name: str, help_text: str, metric_type: str = "gauge") -> None:
        self._lines.append(f"# HELP {name} {help_text}")
        self._lines.append(f"# TYPE {name} {metric_type}")

    def sample(self, name: str, value: float, **labels: object) -> None:
        if labels:
            rendered = ",".join(f'{key}="{_escape(val)}"' for key, val in labels.items())
            self._lines.append(f"{name}{{{rendered}}} {_format(value)}")
        else:
            self._lines.append(f"{name} {_format(value)}")

    def render(self) -> str:
        return "\n".join(self._lines) + "\n"


def _format(value: float) -> str:
    """Render a number without scientific notation or a trailing '.0'."""
    if isinstance(value, bool):
        return "1" if value else "0"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def render_metrics() -> str:
    """Build the full Prometheus exposition payload."""
    writer = MetricsWriter()
    slices = slice_registry.get_all_slices()
    active = [s for s in slices if s.status == "active"]

    # --- capacity -------------------------------------------------------------
    writer.family("helix_network_capacity_mbps", "Total guaranteed bandwidth capacity")
    writer.sample("helix_network_capacity_mbps", settings.total_bandwidth_mbps)

    used = slice_registry.get_total_active_bandwidth()
    writer.family("helix_network_allocated_mbps", "Guaranteed bandwidth reserved by active slices")
    writer.sample("helix_network_allocated_mbps", used)

    writer.family(
        "helix_network_utilization_ratio", "Reserved bandwidth as a fraction of capacity"
    )
    writer.sample(
        "helix_network_utilization_ratio",
        used / settings.total_bandwidth_mbps if settings.total_bandwidth_mbps else 0.0,
    )

    # --- slice inventory -------------------------------------------------------
    writer.family("helix_slices_total", "Slices in the registry, by status")
    by_status: dict[str, int] = {}
    for config in slices:
        by_status[config.status] = by_status.get(config.status, 0) + 1
    for status in ("active", "pending", "conflict", "rejected"):
        writer.sample("helix_slices_total", by_status.get(status, 0), status=status)

    writer.family("helix_slices_by_sst", "Active slices by slice/service type")
    by_sst: dict[int, int] = {}
    for config in active:
        by_sst[config.sst] = by_sst.get(config.sst, 0) + 1
    for sst, label in ((1, "eMBB"), (2, "URLLC"), (3, "mMTC")):
        writer.sample("helix_slices_by_sst", by_sst.get(sst, 0), sst=sst, type=label)

    writer.family("helix_devices_total", "Devices attached across active slices")
    writer.sample("helix_devices_total", sum(config.device_count for config in active))

    # --- per-slice telemetry ------------------------------------------------------
    latest = telemetry_engine.latest_all()
    writer.family("helix_slice_throughput_mbps", "Delivered throughput per slice")
    writer.family("helix_slice_latency_ms", "Observed latency per slice")
    writer.family("helix_slice_packet_loss_percent", "Observed packet loss per slice")
    writer.family("helix_slice_prb_utilization_percent", "PRB utilisation per slice")
    for config in active:
        sample = latest.get(config.slice_id)
        if sample is None:
            continue
        labels = {
            "slice_id": config.slice_id,
            "slice": config.name,
            "use_case": config.use_case,
            "location": config.location,
        }
        writer.sample("helix_slice_throughput_mbps", sample.throughput_mbps, **labels)
        writer.sample("helix_slice_latency_ms", sample.latency_ms, **labels)
        writer.sample("helix_slice_packet_loss_percent", sample.packet_loss_percent, **labels)
        writer.sample(
            "helix_slice_prb_utilization_percent", sample.prb_utilization_percent, **labels
        )

    # --- SLA compliance ------------------------------------------------------------
    evaluations = sla_monitor.evaluate_all(active)
    counts = sla_monitor.status_counts(evaluations)
    writer.family("helix_sla_slices", "Slices by SLA status")
    for status, count in counts.items():
        writer.sample("helix_sla_slices", count, status=status)

    writer.family("helix_sla_compliance_score", "SLA compliance score per slice (0-100)")
    for evaluation in evaluations:
        writer.sample(
            "helix_sla_compliance_score",
            evaluation.compliance_score,
            slice_id=evaluation.slice_id,
            slice=evaluation.slice_name,
        )

    # --- topology ---------------------------------------------------------------------
    writer.family("helix_node_utilization_percent", "Bandwidth utilisation per node")
    writer.family("helix_node_hosted_slices", "Slices hosted per node")
    for node in topology_manager.utilization():
        labels = {"node_id": node.node_id, "node": node.name, "type": node.node_type}
        writer.sample("helix_node_utilization_percent", node.utilization_percent, **labels)
        writer.sample("helix_node_hosted_slices", node.hosted_slices, **labels)

    # --- controller -------------------------------------------------------------------
    controller_status = sdn_controller.get_controller_status()
    writer.family("helix_sdn_connected", "Whether the SDN controller is reachable")
    writer.sample("helix_sdn_connected", 1 if controller_status["connected"] else 0)

    writer.family("helix_sdn_deployments_total", "Slice deployments attempted", "counter")
    writer.sample(
        "helix_sdn_deployments_total", controller_status["total_deployments"], outcome="success"
    )
    writer.sample(
        "helix_sdn_deployments_total", controller_status["failed_deployments"], outcome="failure"
    )

    return writer.render()
