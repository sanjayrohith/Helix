# HELIX Architecture

HELIX turns a plain-English network requirement into a validated, deployed and
continuously monitored 5G network slice. This document explains how the pieces
fit together and, where a design could reasonably have gone another way, why it
went this way.

## Request path

A provisioning request walks through five stages:

```
intent (natural language)
   │
   ▼
1. Intent parsing        services/intent_parser.py
   │  LLM (Groq) with a deterministic fallback
   ▼
2. Admission control     services/conflict_detector.py
   │  eight checks, every finding reported, remediation proposed
   ▼
3. Deployment            services/sdn_controller.py
   │  OpenFlow rules across simulated datapaths
   ▼
4. Placement             services/topology.py
   │  scored against real node capacity and constraints
   ▼
5. Monitoring            services/monitor_loop.py
      KPI simulation, SLA grading, WebSocket streaming
```

Each stage writes to the audit journal, so the whole path is reconstructable
after the fact from `GET /api/events`.

## Components

### `core/` — cross-cutting concerns

| Module | Responsibility |
| --- | --- |
| `config.py` | Every tunable, resolved once from the environment |
| `logging_config.py` | Console and JSON formatters, request correlation ids |
| `middleware.py` | Correlation, timing, sliding-window rate limiting, body-size limit, security headers |
| `telecom.py` | 3GPP tables: 5QI characteristics, ARP bands, use-case profiles |
| `auth.py` | API-key authentication, `read`/`write` scopes |
| `errors.py` | Global exception handlers, one JSON envelope for every error |
| `etag.py` | Content-hash `ETag` generation and `If-Match` comparison (RFC 7232) |
| `pagination.py` | Offset/limit pagination and RFC 5988 `Link` headers |

`telecom.py` is the single source of truth for standards data. The parser, the
conflict engine and the exporters all read from it, so a change to a 5QI's
packet delay budget propagates everywhere at once.

### `services/` — domain logic

| Module | Responsibility |
| --- | --- |
| `intent_parser.py` | Chooses a parser and normalises the result |
| `llm_parser.py` | Groq-backed parsing, constructed lazily |
| `rule_parser.py` | Deterministic pattern-matching parser |
| `conflict_detector.py` | Admission control and remediation |
| `slice_registry.py` | Authoritative slice state, mirrored to SQLite |
| `sdn_controller.py` | Simulated Ryu controller and flow rules |
| `topology.py` | Node model, occupancy, placement scoring |
| `telemetry.py` | Per-slice KPI simulation |
| `sla_monitor.py` | SLA derivation and grading |
| `monitor_loop.py` | The background sampling loop |
| `audit_log.py` | Append-only event journal |
| `metrics.py` | Prometheus exposition |
| `exporters.py` | Open5GS, Kubernetes, S-NSSAI, flow-rule output |
| `idempotency.py` | TTL-based cache backing `Idempotency-Key` on provisioning |

### `storage/` — persistence

| Module | Responsibility |
| --- | --- |
| `sqlite_store.py` | Slice and audit-event persistence |
| `migrations.py` | Forward-only, `PRAGMA user_version`-tracked schema migrations |

## Design decisions

### Two parsers, not one

The LLM parser handles arbitrary phrasing; the rule-based parser handles the
common cases with no network call and no API key. The facade prefers the LLM
and falls back on *any* failure — missing key, auth error, timeout, malformed
JSON — recording the reason on the outcome.

This matters more than it first appears. The original implementation built its
Groq client at module import time, so a missing `GROQ_API_KEY` raised during
import of the router chain and the entire API failed to start. A demo without
network access had no working system at all. Now the worst case is a
deterministic parse and a note in the response explaining why.

The deterministic parser is also *explainable*: it records how it derived each
field in a `ParseTrace`, which the dashboard surfaces under "How was this
derived?".

### Every conflict, not the first one

Admission control originally returned on its first finding, so an operator
whose slice had four problems resubmitted four times. The engine now runs all
eight checks, ranks findings by severity, and merges their remediations into
one set of field changes.

Severity is the important half of the design. Only `blocking` findings stop a
deployment. A latency target tighter than the chosen 5QI's packet delay budget
is worth telling an operator about, but refusing to deploy over it would be
wrong — the slice is valid, the expectation is optimistic.

The merged remediation is verified to converge: applying it to a slice with
three simultaneous blocking conflicts produces a configuration that passes
cleanly. There is a test that asserts exactly this.

### Telemetry that means something

KPIs are not random noise. Each slice carries simulation state — a load phase
on a slow sinusoid, a congestion level that builds while demand exceeds the
guaranteed rate and decays otherwise — and its KPIs derive from that state plus
its own configuration. A strictly isolated slice genuinely shows lower jitter
and loss than a shared one, because isolation is an input to the model.

Offered load is tracked separately from delivered throughput. This distinction
is what makes the SLA meaningful: a slice carrying little traffic is idle, not
failing. Grading delivered-versus-guaranteed put every healthy slice in
violation whenever demand happened to be low.

Availability is only graded once a slice has been observed for 60 intervals.
A handful of samples cannot distinguish 99.9% from 95%, and grading them
anyway produced false violations.

### SLAs derived from intent

Rather than a separate policy file, each slice's SLA comes from its own
configuration: the latency target with tolerance, availability by security
classification, packet loss by slice type. A slice is held to the contract its
intent implied, and there is no second place for the two to drift apart.

The monitor reports status *transitions*, not every evaluation, so a slice
sitting in violation alerts once rather than on every tick.

### Topology as a real constraint

Treating the network as one pool of bandwidth let admission control accept
slices no individual site could host. Nodes now carry capacity, slice slots,
device limits, a latency floor and the isolation levels they support.

Placement scoring has one deliberately counter-intuitive rule: among feasible
nodes, it prefers the one with the *least* latency headroom that still fits.
Sending a 100 ms IoT slice to a 1 ms edge node would work, but it burns a
scarce site that a URLLC slice will need later.

### Persistence without an ORM

The schema is four tables of known shape that are never round-tripped through
a query builder. `sqlite3` with hand-written SQL and a threading lock is less
code and less indirection than SQLAlchemy would be here. Rows that fail to
validate after a schema change are skipped with a warning rather than
crashing startup.

### Auth, idempotency and concurrency are all opt-in the same way

`HELIX_API_KEYS` unset, `Idempotency-Key` header absent, `If-Match` header
absent: all three features are silently no-ops, and the pre-existing
behavior (unauthenticated, every request provisions independently, last
write wins) is preserved exactly. This is the same pattern the LLM parser
already used - a demo, `make dev`, and the test suite need zero configuration
to keep working, and a real deployment opts into each guarantee it actually
needs rather than being forced into all of them at once.

### A body-size limit belongs before the app runs, not inside it

The first implementation of `MaxBodySizeMiddleware` wrapped `receive()` and
raised mid-stream when too many bytes arrived, relying on FastAPI's narrow
`except HTTPException: raise` carve-out in its body-parsing code to turn that
into a clean `413`. It didn't work: with two `BaseHTTPMiddleware` layers
between this middleware and the router, each running the downstream app in
its own `anyio` task group, the exception's type fidelity didn't reliably
survive two nested task-group re-raises by the time FastAPI's routing code
saw it - it consistently came back as a generic `400` instead. The fix that
actually works is simpler than the one that didn't: check the declared
`Content-Length` before calling into the rest of the app at all, so there is
no nested call stack for an exception to survive crossing. It also matches
how a real deployment already handles this at the reverse proxy layer
(nginx's `client_max_body_size`) - HELIX's own check is the in-process
backstop, not the primary defence.

### A real migration runner instead of `CREATE TABLE IF NOT EXISTS`

The original schema setup ran one `executescript()` on every startup, which
works until the schema needs to change under an existing database - there
was no way to add a column or index without either a manual `ALTER TABLE` or
wiping the data. `storage/migrations.py` tracks the schema version in
SQLite's own `PRAGMA user_version` and applies whatever hasn't run yet, in
order, on every startup. Each migration is a plain SQL string in an ordered
tuple - no framework, no down-migrations (a fresh forward migration is the
answer to a mistake, matching how this project already treats a broken
config: fix and move forward, not roll back).

### Distinguishing a reachable `None` from a provably unreachable one

Concurrent-safety bugs found via mypy's Optional-narrowing got two different
fixes depending on whether the null case was actually reachable. In
`DELETE /api/slices/{id}`, the code awaits the SDN controller between
checking a slice exists and deleting it from the registry - a second
concurrent delete can genuinely win that race, so the fix is a real `404`
check. In `_apply_update`, `suspend_slice` and `resume_slice`, there is no
`await` between the same kind of existence check and the following registry
call, so the registry cannot have changed underneath them - those keep a
documented `assert` instead of unneeded error-handling for a state that
cannot occur. The type checker flagged both shapes identically; only reading
the actual code told them apart.

### YAML without PyYAML

The exporters emit shallow, fully-known documents and never read YAML back in,
so a ~40-line writer replaces the dependency. The output is verified against a
real parser in the test suite — which is how the bug where a Slice
Differentiator of `000002` came back as the integer `2` was caught.

## Data flow at runtime

```
                 ┌──────────────┐
   HTTP  ───────►│  routers/    │
                 └──────┬───────┘
                        │
              ┌─────────▼──────────┐        ┌───────────────┐
              │  services/         │◄──────►│ storage/      │
              │  (domain logic)    │        │ SQLite        │
              └─────────┬──────────┘        └───────────────┘
                        │
        ┌───────────────┼────────────────┐
        ▼               ▼                ▼
   ConnectionManager  audit_log     metrics.py
   (WebSocket)        (journal)     (/metrics)
        │
        ▼
   dashboards
```

The monitor loop is the only writer that runs without an HTTP request behind
it. It samples, grades, broadcasts and journals on a fixed cadence, and is
started and stopped with the application lifespan.

## Configuration

Every knob is an environment variable with a working default; see
`.env.example`. The ones that change behaviour most:

| Variable | Default | Effect |
| --- | --- | --- |
| `GROQ_API_KEY` | unset | Enables the LLM parser |
| `HELIX_FORCE_RULE_PARSER` | `false` | Skip the LLM even with a key |
| `HELIX_TOTAL_BANDWIDTH_MBPS` | `1000` | Network capacity for admission control |
| `HELIX_PERSISTENCE_ENABLED` | `true` | SQLite persistence |
| `HELIX_TELEMETRY_ENABLED` | `true` | The monitor loop |
| `HELIX_TELEMETRY_OUTAGE_RATE` | `0.004` | Set to 0 for a deterministic simulator |
| `HELIX_SDN_STEP_SCALE` | `1.0` | Set to 0 for instant deployments |
| `HELIX_RATE_LIMIT_PER_MINUTE` | `60` | Write requests per client; 0 disables |
| `HELIX_API_KEYS` | unset | `key:scope[:label]` list; enables auth on every route once set |
| `HELIX_MAX_BODY_BYTES` | `1048576` | Request body size limit; 0 disables |

See [SECURITY.md](SECURITY.md) for the full threat model behind the
security-related settings.

## Testing

The suite runs in about a second and needs no API key, no database and no
network. That is deliberate: `HELIX_FORCE_RULE_PARSER`,
`HELIX_PERSISTENCE_ENABLED=false`, `HELIX_SDN_STEP_SCALE=0` and
`HELIX_TELEMETRY_OUTAGE_RATE=0` in the test configuration remove every source
of non-determinism and every simulated sleep.

`scripts/smoke_test.py` covers what unit tests cannot: that a real running
instance can be driven through provisioning, telemetry, placement, export,
metrics, lifecycle and teardown.
