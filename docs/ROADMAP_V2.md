# HELIX v2.1 Roadmap — Production Hardening

v2.0 built the feature surface: parsing, admission control, telemetry, SLA,
topology, export. This phase closes the gaps that separate a working demo
from something a senior engineer would sign off on putting in front of real
traffic. None of these are cosmetic — each one is a genuine failure mode
found by auditing the v2.0 codebase directly.

## What the audit found

| Gap | Why it matters |
| --- | --- |
| **No authentication anywhere** | Any request can suspend, delete or reconfigure any slice. There is no distinction between a read-only dashboard viewer and an operator. |
| **`intent` has no length limit** | A client can POST a multi-megabyte string to `/provision`; it gets parsed, LLM-called (if configured) and stored in the audit journal in full. |
| **No global exception handler** | An unexpected error returns FastAPI's default 500, which in some deployment configurations includes the traceback. |
| **No idempotency on provisioning** | A retried request (client timeout, double-click, proxy retry) creates a second slice instead of returning the first result. |
| **No pagination** | `GET /api/slices` and `GET /api/events` return everything, unbounded. Fine at demo scale, a real liability at thousands of rows. |
| **No optimistic concurrency on PATCH** | Two concurrent updates to the same slice silently overwrite each other with no conflict signal. |
| **No request body size limit** | Nothing caps request size below what Starlette itself allows. |
| **No security headers** | No `X-Content-Type-Options`, `Referrer-Policy`, or a documented CORS story beyond `allow_origins=["*"]` by default. |
| **No SQLite migration path** | `schema_version` is written but never read; a schema change has no upgrade story for an existing database. |
| **Zero frontend tests** | The backend has 154 tests; the frontend — API client, filter logic, WebSocket reconnection — has none. |
| **No error boundary in React** | An uncaught render error blanks the entire dashboard instead of degrading one panel. |
| **Unpinned dependencies** | `requirements.txt` uses `>=` with no lockfile; a transitive upgrade can silently change behavior between two otherwise-identical `pip install` runs. |
| **No static type checking in CI** | Ruff catches style and some bugs; nothing catches a type mismatch before runtime. |
| **Topology occupancy recomputed from scratch per call** | `_usage()` scans every placement for every node on every request; fine today, a real cost once slice/node counts grow. |
| **No load or perf baseline** | Nothing in the repo says what "acceptable" latency or throughput looks like, so a regression has nothing to be caught against. |

## Plan (grouped by phase, ~50 commits)

1. **Security & auth** — API-key authentication with read/write scopes, security
   headers, input-length limits, a global exception handler that never leaks
   internals, idempotency keys on provisioning, authenticated actor recorded
   in the audit journal instead of a hardcoded `"system"`.
2. **API robustness** — pagination on list endpoints, a consistent list
   envelope, machine-readable error codes, `ETag`/`If-Match` optimistic
   concurrency on `PATCH`, a request body size cap.
3. **Data integrity** — a real (small, dependency-free) SQLite migration
   runner that actually reads `schema_version`, a backup/restore CLI.
4. **Frontend testing** — Vitest + Testing Library, tests for the API client,
   filter/sort logic, the WebSocket client's reconnection behavior and the
   sparkline math; a React error boundary; an accessibility pass on the
   detail drawer and toasts.
5. **Performance** — cache topology occupancy instead of recomputing it per
   request, a documented load-test script and baseline numbers.
6. **Code quality & tooling** — pre-commit hooks, pinned dependencies via a
   lockfile, mypy in CI, ESLint/Prettier for the frontend.
7. **Docs** — `SECURITY.md`, updated `API.md` and `ARCHITECTURE.md`, a v2.1
   changelog entry.

Each phase lands as several small, reviewable commits rather than one large
one, same discipline as v2.0. Every behavior change ships with a test that
would have caught its absence.
