# Changelog

All notable changes to HELIX are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

## [2.0.0]

A substantial expansion: HELIX goes from a provisioning form to a control
plane that validates, deploys, places and continuously monitors slices.

### Added

**Intent parsing**
- Deterministic offline parser with unit-aware extraction of bitrate
  (kbps–Tbps), latency (µs/ms/s), device populations including `50k` scale
  suffixes, and locations, layered onto eight use-case profiles
- Parser facade that prefers the LLM and degrades on any failure, recording
  the reason on the response
- Parse traces explaining how each field was derived, surfaced in the UI

**Admission control**
- Four new checks: latency feasibility against the 5QI packet delay budget,
  isolation consistency, per-device bandwidth density, and capacity share
- Severity levels — only `blocking` findings stop a deployment
- Auto-remediation merged across all findings, verified to converge
- `POST /api/slices/simulate` for dry runs

**Telemetry and SLA**
- Per-slice KPI simulation driven by persistent state and slice configuration
- SLA targets derived from each slice's own intent, graded on a rolling window
  into a 0–100 compliance score with per-KPI breaches
- Background monitor loop streaming telemetry over a new WebSocket event
- Transition-based alerting so a violating slice alerts once, not per tick

**Topology**
- gNB, edge, UPF and core node model with capacity, slot, device, latency and
  isolation constraints
- Explainable placement scoring; node health for exercising failover
- Rebalance endpoint

**Lifecycle**
- `PATCH`, `scale`, `suspend` and `resume`; suspend returns guaranteed
  bandwidth to the pool without losing the configuration

**Operations**
- SQLite persistence for slices and the audit journal
- Append-only audit journal with filtered queries
- Prometheus metrics at `/metrics` (16 families)
- Request correlation ids, response timing, sliding-window rate limiting
- System info, parser status and readiness endpoints
- Centralised settings; every tunable is an environment variable

**Export**
- Open5GS subscriber profiles, Kubernetes `NetworkSlice` custom resources,
  3GPP S-NSSAI descriptors and OpenFlow rules, per slice or network-wide

**Dashboard**
- Live KPI bar with trend sparklines and SLA compliance breakdown
- SLA alert panel listing only slices outside their SLA, worst first
- Slice detail drawer: performance, configuration, placement, export
- Search, filtering and sorting; topology occupancy panel; activity feed
- Intent templates, recent-intent history and a dry-run action
- Connection status driven by real WebSocket state

**Engineering**
- 154 backend tests running in about a second with no network or database
- End-to-end smoke test with eleven assertions
- GitHub Actions CI: lint, test, typecheck, build, smoke
- Makefile, architecture and API documentation, contributor guide

### Fixed

- **The API could not start without `GROQ_API_KEY`.** The Groq client was
  constructed at module import time, so a missing key raised during import of
  the router chain and took down the whole service. The client is now built
  lazily and any LLM failure degrades to the deterministic parser.
- **Admission control reported only the first conflict**, forcing an operator
  with several problems to resubmit repeatedly.
- **Every healthy slice was reported as violating its throughput SLA** whenever
  demand was below its guarantee. Offered load is now tracked separately from
  delivered throughput, so an idle slice is not treated as a failing one.
- **Availability was graded from too few intervals**, turning a single early
  outage into a false violation. It is now only graded after 60 intervals.
- **YAML exports corrupted numeric-looking identifiers.** A Slice
  Differentiator of `000002` was emitted unquoted and parsed back as the
  integer `2`.
- **The dashboard was hard-coded to `localhost:8000`**, so any deployment
  other than a developer laptop pointed at the wrong host.
- **The device-population parser did not recognise people nouns**, so
  "broadband for 5000 employees" silently used a profile default.
- **The WebSocket had no observable state**, so the header showed "Connected"
  regardless of reality, and reconnection had no jitter or heartbeat.
- Deprecated `datetime.utcnow` replaced throughout with a timezone-aware
  helper.

### Changed

- Registry restores from disk on boot and seeds demo data only on a genuinely
  fresh instance
- The SDN controller emits real flow rules and records deployments; timing is
  configurable, making the test suite roughly twenty times faster
- `SliceConfig` normalises and validates the Slice Differentiator, trims blank
  names and raises a maximum bitrate below the guaranteed rate
- Compose passes settings through, mounts a volume for persistence, and waits
  for the backend health check before starting the frontend
- Dropped the stale pnpm lockfile; npm is the single source of truth

## [1.0.0]

Initial release: LLM intent parsing, four conflict checks, in-memory registry,
simulated SDN deployment, WebSocket updates and the React dashboard.
