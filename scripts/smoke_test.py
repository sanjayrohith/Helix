#!/usr/bin/env python3
"""End-to-end smoke test against a running HELIX API.

Exercises the path a real operator takes - dry run, provision, inspect
telemetry, export, tear down - and fails loudly if any step misbehaves. Used
by CI after the unit suite, and useful locally to check a deployment.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

DEFAULT_BASE = "http://localhost:8000"
INTENT = (
    "Dedicated smart factory slice in Chennai with 6ms latency and 90 Mbps for 700 robots"
)


class SmokeFailure(AssertionError):
    """A smoke-test step did not behave as expected."""


def call(base: str, method: str, path: str, payload: dict | None = None):
    """Issue one API call, returning parsed JSON or raw text."""
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        f"{base}{path}", data=data, method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode()
    except urllib.error.HTTPError as error:
        raise SmokeFailure(
            f"{method} {path} returned {error.code}: {error.read().decode()[:300]}"
        ) from error
    except urllib.error.URLError as error:
        raise SmokeFailure(f"{method} {path} could not connect: {error.reason}") from error

    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return body


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def run(base: str) -> None:
    steps: list[str] = []

    def note(message: str) -> None:
        steps.append(message)
        print(f"  ok  {message}")

    health = call(base, "GET", "/health")
    check(health.get("status") == "healthy", f"unhealthy: {health}")
    note(f"health reports version {health.get('version')}")

    readiness = call(base, "GET", "/api/system/readiness")
    check(readiness.get("ready") is True, f"not ready: {readiness}")
    note("readiness probe passes")

    simulation = call(base, "POST", "/api/slices/simulate", {"intent": INTENT})
    check("would_deploy" in simulation, "simulation did not return a verdict")
    check(
        simulation["capacity_after_mbps"] > simulation["capacity_before_mbps"],
        "simulation reported no capacity impact",
    )
    note(f"dry run says would_deploy={simulation['would_deploy']}")

    deployment = call(base, "POST", "/api/slices/provision", {"intent": INTENT})
    check(deployment["success"] is True, f"provisioning failed: {deployment['message']}")
    slice_id = deployment["slice_config"]["slice_id"]
    note(f"provisioned '{deployment['slice_config']['name']}' via {deployment['parser_used']}")

    call(base, "POST", "/api/telemetry/tick")
    call(base, "POST", "/api/telemetry/tick")
    telemetry = call(base, "GET", f"/api/telemetry/{slice_id}")
    check(telemetry["latest"] is not None, "no telemetry sample was produced")
    check(len(telemetry["history"]) >= 2, "telemetry history did not accumulate")
    note(f"telemetry: {len(telemetry['history'])} samples, SLA {telemetry['sla']['status']}")

    placement = call(base, "GET", f"/api/topology/placement/{slice_id}")
    check(placement["placed"] is True, f"slice was not placed: {placement['explanation']}")
    note(f"placed on {placement['node_name']}")

    for fmt in ("kubernetes", "open5gs", "snssai", "flow-rules"):
        body = call(base, "GET", f"/api/export/slices/{slice_id}?format={fmt}")
        check(bool(body), f"{fmt} export was empty")
    note("all export formats produce output")

    metrics = call(base, "GET", "/metrics")
    check("helix_network_capacity_mbps" in metrics, "metrics are missing capacity")
    check("helix_sla_compliance_score" in metrics, "metrics are missing SLA scores")
    note("Prometheus metrics expose capacity and SLA")

    events = call(base, "GET", f"/api/events?slice_id={slice_id}")
    check(len(events) >= 1, "no audit events were recorded for the slice")
    note(f"audit journal recorded {len(events)} event(s)")

    suspended = call(base, "POST", f"/api/slices/{slice_id}/suspend")
    check(suspended["new_status"] == "pending", "suspend did not change status")
    resumed = call(base, "POST", f"/api/slices/{slice_id}/resume")
    check(resumed["new_status"] == "active", "resume did not restore the slice")
    note("suspend and resume round-trip")

    removed = call(base, "DELETE", f"/api/slices/{slice_id}")
    check(removed["released_mbps"] > 0, "delete did not release bandwidth")
    note(f"deleted, {removed['released_mbps']:.0f} Mbps released")

    print(f"\n{len(steps)} checks passed against {base}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE, help="API base URL")
    args = parser.parse_args()

    print(f"HELIX smoke test -> {args.base_url}\n")
    try:
        run(args.base_url.rstrip("/"))
    except SmokeFailure as failure:
        print(f"\nFAILED: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
