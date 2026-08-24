# Performance notes

Baselines and the reasoning behind the one real optimisation made so far.
These are honest numbers from this machine, not aspirational ones - re-run
`scripts/load_test.py` on your own hardware before trusting a number here
for capacity planning.

## API load test baseline

`scripts/load_test.py` against a local instance (demo data, deterministic
parser, SDN deployment steps set to instant via `HELIX_SDN_STEP_SCALE=0`),
200 requests per endpoint at concurrency 10:

| Endpoint | mean | p50 | p95 | max |
| --- | --- | --- | --- | --- |
| `GET /health` | 10.4 ms | 10.1 ms | 13.0 ms | 17.3 ms |
| `GET /api/slices` | 17.8 ms | 16.8 ms | 25.1 ms | 36.1 ms |
| `GET /api/slices/stats/summary` | 13.8 ms | 14.0 ms | 18.0 ms | 20.6 ms |
| `GET /api/topology` | 19.4 ms | 17.5 ms | 55.9 ms | 67.0 ms |
| `GET /api/telemetry/summary` | 16.8 ms | 16.6 ms | 20.8 ms | 27.6 ms |
| `POST /api/slices/simulate` | 20.7 ms | 20.3 ms | 25.6 ms | 28.1 ms |

All under 30 ms at this scale (a handful of demo slices). Run with
`HELIX_RATE_LIMIT_PER_MINUTE=0` - with the default limit of 60 write
requests/minute in place, hammering `POST /api/slices/simulate` at
concurrency 10 hits `429 Too Many Requests` almost immediately, which is
the rate limiter doing exactly its job rather than a load-test bug. Point
the script at a real deployment's actual rate limit if you want a number
that reflects what a client experiences in production.

```bash
python scripts/load_test.py --base-url http://localhost:8000 --requests 200 --concurrency 10
```

## Topology occupancy: one real optimisation, honestly measured

`TopologyManager._usage()` was called once per node from both `utilization()`
and `evaluate()`, and each call independently scanned every placement in the
network to find that one node's share - O(nodes × placements) work to
produce something that only needs O(placements). Replaced with
`_usage_by_node()`, which groups placements by node in a single pass and
reuses that grouping across every node in the same call - O(nodes +
placements).

Measured directly (old implementation reconstructed for comparison, 20
calls averaged per data point):

| Slices placed | Old | New | Speedup |
| --- | --- | --- | --- |
| 100 | 0.10 ms | 0.12 ms | 0.8x (new is *slower* here) |
| 1,000 | 0.93 ms | 0.78 ms | 1.2x |
| 5,000 | 6.2-7.9 ms | 5.1-5.6 ms | 1.2-1.4x |

Reported honestly rather than rounded up: the win is real but modest at
HELIX's actual node count (7 in the default topology), and at very small
slice counts the extra dict bookkeeping in the new version can be slightly
slower than the old one's simplicity. The asymptotic difference - O(nodes +
placements) instead of O(nodes × placements) - only pays off as *nodes*
grows, not just placements; a topology with dozens of radio sites rather
than a handful would show a much larger gap than these numbers do. The
change is kept because it removes a genuine anti-pattern (the same full
scan repeated once per node) and reads more clearly as a single pass with
one source of truth for occupancy, not because 1.2x was, on its own, worth
a special trip.

## What is not covered here

- Groq LLM latency (network-dependent, outside HELIX's control; the
  deterministic parser exists partly because of this).
- SQLite write throughput under heavy concurrent provisioning - untested at
  a scale beyond what a single operator dashboard would generate.
- WebSocket broadcast fan-out cost with a large number of simultaneously
  connected dashboards.

None of these have caused a problem in practice yet; if one becomes worth
measuring, it belongs here with the same treatment as the sections above -
a script, real numbers, and an honest read of what they show.
