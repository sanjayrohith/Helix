# Security

HELIX's threat model, what is actually enforced today, and what a real
deployment still has to add on top. Written for whoever is deciding whether
to point this at anything beyond a laptop demo.

## What HELIX is

An internal network-operations tool for provisioning and monitoring 5G
network slices - not a multi-tenant SaaS product, not internet-facing by
default. That framing drives every choice below: the goal is to stop an
unauthenticated caller on the same network from silently reconfiguring or
tearing down production slices, not to defend against a hostile public
internet on HELIX's own doorstep. A deployment that *does* face the public
internet needs a reverse proxy in front of it (see "What HELIX does not do"
below) - HELIX assumes one is there, the same way it assumes TLS termination
happens somewhere it doesn't have to think about.

## Authentication and authorization

API-key auth with two scopes - `read` and `write` - covers the one
distinction that actually matters here: can this caller only look at the
network, or can it change it. Full OAuth2/JWT with session management would
add a real class of new bugs (token refresh, session fixation, password
storage) to guard against a threat this deployment doesn't have; API keys
with two scopes is what infrastructure tools at this scope actually use
(Grafana, most internal SRE dashboards).

- Configure with `HELIX_API_KEYS`, a comma-separated list of
  `key:scope[:label]` entries: `sk_abc123:write:ops-team,sk_def456:read:dashboard`.
- Send a key as `Authorization: Bearer <key>` or `X-API-Key: <key>`.
- `write` satisfies anything `read` also satisfies - an operator key can do
  everything a viewer key can.
- **Auth is opt-in.** Leave `HELIX_API_KEYS` unset and every request is
  treated as an authenticated "system" principal with full access - the same
  behavior as before auth existed, so a demo, `make dev`, and the test suite
  all keep working with zero configuration. Set at least one key and the API
  starts enforcing scopes on *every* route; there is no half-on state.
- Malformed entries in `HELIX_API_KEYS` (wrong field count, unknown scope,
  empty key) are skipped with a warning, not a startup crash - a typo in one
  entry doesn't take down the whole key list.
- Keys are never logged in full. `core/auth.redact()` produces a stable
  `key-xxxxxxxx` label (first 8 hex chars of a SHA-256 digest) for the audit
  journal and logs when no explicit label was configured for a key.
- `/health` and `/api/system/readiness` are deliberately left unauthenticated
  - a load balancer's liveness probe cannot supply a key, and neither
  endpoint reveals anything beyond "the process is up."
- The WebSocket endpoint (`/ws`) takes the key as a query parameter
  (`?api_key=...`, since browsers can't set custom headers on a WebSocket
  handshake) and closes with code `4401` before accepting the connection if
  auth is configured and the key is missing or wrong.

Every mutating audit-log entry now records the authenticated actor
(`principal.actor`) rather than a generic system label, so `GET /api/events`
answers "who did this," not just "what happened."

## Request integrity

- **Idempotency keys** (`Idempotency-Key` header on `POST /api/slices/provision`)
  make retries safe: the same key replays the cached result instead of
  provisioning a second slice, scoped per-actor so one client's key can't
  collide with another's. Entries expire after a TTL and the cache caps
  itself at 10,000 entries, dropping the oldest half if that's ever reached.
- **Optimistic concurrency** (`ETag` / `If-Match`) on slice reads and updates
  stops a lost-update race: `GET /api/slices/{id}` returns an `ETag`, and
  `PATCH` with a stale `If-Match` gets `412 Precondition Failed` instead of
  silently overwriting a change made in between.
- **Body size limit** (`HELIX_MAX_BODY_BYTES`, default 1 MiB) rejects an
  oversized request by its declared `Content-Length` before any of it is
  read into memory. This is a backstop for well-behaved clients, not a
  complete defence - see "What HELIX does not do."
- **Schema-level validation** caps intent length (2000 chars) and rejects
  blank/whitespace-only intents at the Pydantic boundary (`422`), before the
  request reaches the parser at all.

## Response hardening

`SecurityHeadersMiddleware` sets `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, a restrictive
`Permissions-Policy`, and `Strict-Transport-Security` on every response.
HELIX is a JSON API with no server-rendered HTML, so most of these are
defence in depth rather than closing an active hole - but "it's just an API"
is exactly the reasoning that leaves an admin endpoint one misconfigured
reverse proxy away from being framed or content-sniffed, and setting them
costs nothing.

Every response also carries `X-Request-ID` (reusing an inbound one when
present, so a trace started upstream continues through HELIX's own logs) and
`X-Response-Time-Ms`.

## Error handling

Every error - a validation failure, a deliberate `HTTPException`, or a truly
unexpected exception - returns the same JSON envelope:
`{"detail": ..., "code": ..., "request_id": ...}`. The catch-all handler for
unexpected exceptions is the one place this could leak internals if written
carelessly, so it does the least: log the full traceback server-side with
the request id, and tell the client nothing beyond that id and a generic
message. There is no configuration that makes a raw traceback reach a
client, regardless of how the process is launched (`--reload`, a debug-mode
ASGI wrapper, an unconfigured proxy) - the previous default depended on
that, which was fragile.

## Rate limiting

A per-client sliding-window limiter (`HELIX_RATE_LIMIT_PER_MINUTE`, default
60/minute) covers write endpoints only - reads stay unrestricted so
dashboards can poll freely. The client key prefers `X-Forwarded-For` when
present, which means it trusts whatever sits in front of HELIX to set that
header honestly (see below).

## Data at rest

SQLite persistence (`HELIX_PERSISTENCE_ENABLED`) is unencrypted at rest by
design - encryption belongs at the filesystem or volume layer in any real
deployment, not duplicated in application code with a hand-rolled key
management story. `scripts/backup_db.py` produces backups via SQLite's
online backup API (safe under concurrent writes, unlike a raw file copy) and
verifies integrity before ever touching a live database on restore.

## Reporting a vulnerability

This is a demo/reference project, not a maintained product with a security
contact or a disclosure SLA. If you find something serious, open an issue
describing the impact without a working exploit in the public report, and
give the maintainer a chance to look before any wider disclosure.

## What HELIX does not do

Being explicit about the gaps matters more than the list above - a
deployment that assumes HELIX covers these will be wrong.

- **No TLS termination.** HELIX speaks plain HTTP. A production deployment
  needs a reverse proxy (nginx, an ALB, Caddy) in front of it for TLS,
  and that proxy is also the right place for `client_max_body_size` as
  the *first* line of defence against oversized bodies - HELIX's own
  `Content-Length` check is a backstop, not a substitute, and does not
  catch a chunked-transfer body sent without a declared length.
- **`X-Forwarded-For` is trusted as-is.** The rate limiter and the audit
  log's client attribution read it directly. Fine behind a proxy that sets
  it itself and strips any client-supplied copy; wrong if HELIX is ever
  exposed directly, where any caller can put whatever they want in that
  header and blend into someone else's rate-limit bucket.
- **No key rotation or expiry.** `HELIX_API_KEYS` is static configuration -
  rotating a key means editing the environment and restarting the process.
  There is no revocation list, no per-key TTL, no audit trail of *when* a
  key was issued.
- **No encryption at rest** for the SQLite database beyond whatever the host
  filesystem provides.
- **No secrets management integration.** `GROQ_API_KEY` and `HELIX_API_KEYS`
  are read from the environment; wiring in Vault, AWS Secrets Manager, or
  similar is left to the deployment, same as any twelve-factor app.
- **No CSRF protection.** Not applicable to a pure JSON API consumed by a
  frontend that doesn't rely on cookie-based sessions, but worth stating
  rather than leaving implicit - if HELIX ever grows session cookies, this
  changes.
