#!/usr/bin/env python3
"""A small, dependency-free load test for the HELIX API.

Not a substitute for a real tool (locust, k6, wrk) for serious capacity
planning - this exists to give the repository an actual, reproducible
baseline number instead of an unverified claim, and to catch a gross
regression (an endpoint that used to answer in single-digit milliseconds
suddenly taking seconds) in CI or before a release without pulling in a
load-testing framework as a dependency.

Usage:
    python scripts/load_test.py --base-url http://localhost:8000 [--requests 200] [--concurrency 10]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

DEFAULT_BASE = "http://localhost:8000"


@dataclass
class EndpointResult:
    name: str
    latencies_ms: list[float] = field(default_factory=list)
    errors: int = 0

    def summary(self) -> dict:
        if not self.latencies_ms:
            return {"name": self.name, "errors": self.errors, "requests": 0}
        sorted_ms = sorted(self.latencies_ms)
        return {
            "name": self.name,
            "requests": len(sorted_ms),
            "errors": self.errors,
            "mean_ms": round(statistics.mean(sorted_ms), 2),
            "p50_ms": round(sorted_ms[len(sorted_ms) // 2], 2),
            "p95_ms": round(sorted_ms[int(len(sorted_ms) * 0.95)], 2),
            "max_ms": round(sorted_ms[-1], 2),
        }


def timed_get(base: str, path: str) -> float:
    """One GET request, returning its latency in milliseconds. Raises on error."""
    started = time.perf_counter()
    request = urllib.request.Request(f"{base}{path}")
    with urllib.request.urlopen(request, timeout=10) as response:
        response.read()
    return (time.perf_counter() - started) * 1000


def timed_post(base: str, path: str, payload: dict) -> float:
    started = time.perf_counter()
    data = json.dumps(payload).encode()
    request = urllib.request.Request(
        f"{base}{path}", data=data, method="POST", headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        response.read()
    return (time.perf_counter() - started) * 1000


def run_endpoint(base: str, name: str, call, requests: int, concurrency: int) -> EndpointResult:
    result = EndpointResult(name=name)

    def one() -> float | None:
        try:
            return call()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            return None

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        for latency in pool.map(lambda _: one(), range(requests)):
            if latency is None:
                result.errors += 1
            else:
                result.latencies_ms.append(latency)

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--requests", type=int, default=200, help="Requests per endpoint")
    parser.add_argument("--concurrency", type=int, default=10, help="Concurrent workers")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    print(f"Load test -> {base} ({args.requests} requests, concurrency {args.concurrency})\n")

    endpoints = [
        ("GET /health", lambda: timed_get(base, "/health")),
        ("GET /api/slices", lambda: timed_get(base, "/api/slices")),
        ("GET /api/slices/stats/summary", lambda: timed_get(base, "/api/slices/stats/summary")),
        ("GET /api/topology", lambda: timed_get(base, "/api/topology")),
        ("GET /api/telemetry/summary", lambda: timed_get(base, "/api/telemetry/summary")),
        (
            "POST /api/slices/simulate",
            lambda: timed_post(
                base,
                "/api/slices/simulate",
                {"intent": "iot slice with 10 Mbps in Loadtest"},
            ),
        ),
    ]

    results = []
    for name, call in endpoints:
        result = run_endpoint(base, name, call, args.requests, args.concurrency)
        results.append(result)
        summary = result.summary()
        if summary["requests"] == 0:
            print(f"  {name}: all {result.errors} requests failed")
            continue
        print(
            f"  {name:32} mean {summary['mean_ms']:7.2f} ms  "
            f"p50 {summary['p50_ms']:7.2f} ms  p95 {summary['p95_ms']:7.2f} ms  "
            f"max {summary['max_ms']:7.2f} ms  errors {summary['errors']}"
        )

    total_errors = sum(r.errors for r in results)
    if total_errors:
        print(f"\n{total_errors} request(s) failed.")
        return 1

    print("\nAll requests succeeded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
