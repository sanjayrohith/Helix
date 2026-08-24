# HELIX API Reference

Interactive documentation is served at `/docs` (Swagger) and `/redoc`.
Everything below is relative to the API base URL, `http://localhost:8000` by
default.

Write requests are rate limited per client (60/minute by default,
`HELIX_RATE_LIMIT_PER_MINUTE`); reads are not. Every response carries
`X-Request-ID` and `X-Response-Time-Ms`, and an inbound `X-Request-ID` is
reused so a trace started upstream continues through the logs.

## Slices

### `POST /api/slices/provision`

Parse an intent, run admission control, deploy and place the slice.

```json
{ "intent": "Ultra-reliable slice for remote surgery at Chennai with 3ms latency and 80 Mbps" }
```

The response carries the generated `slice_config`, the full `conflict_report`,
`parser_used`, `parse_fallback_reason` when the LLM was bypassed, and
`parse_trace` explaining how each field was derived.

A blocking conflict returns `200` with `success: false` — it is a valid answer
to a valid request, not an error — and
`conflict_report.auto_remediation` holds the field changes that would make it
deploy.

### `POST /api/slices/simulate`

Dry run: the same evaluation with nothing written.

```json
{ "intent": "...", "apply_remediation": true }
```

Returns `would_deploy`, the capacity before and after, and — when
`apply_remediation` is set — the remediated configuration and its own
conflict report.

### `GET /api/slices`

List slices. Optional `use_case`, `location` and `status` filters.

### `GET /api/slices/{slice_id}`

One slice, or `404`.

### `PATCH /api/slices/{slice_id}`

Partial update. Any subset of `name`, `guaranteed_bitrate_mbps`,
`max_bitrate_mbps`, `latency_ms`, `arp_priority`, `device_count`, `isolation`,
`security_level`. Capacity is rechecked excluding the slice's own current
reservation, so shrinking an oversubscribed slice is not blocked by its own
allocation. Returns `409` when the update would exceed capacity.

### `POST /api/slices/{slice_id}/scale`

`{"factor": 1.5}` or `{"target_gbr_mbps": 250}`.

### `POST /api/slices/{slice_id}/suspend` · `/resume`

Suspend returns the slice's guaranteed bandwidth to the pool without deleting
it. Resume re-runs admission control first and returns `409` if capacity is no
longer available.

### `DELETE /api/slices/{slice_id}`

Withdraws the flow rules, releases the node placement and reports
`released_mbps`.

### `GET /api/slices/stats/summary` · `/stats/breakdown`

Dashboard counters, and a grouping by SST, status, use case, location and
isolation.

## Telemetry and SLA

| Endpoint | Returns |
| --- | --- |
| `GET /api/telemetry/summary` | Network-wide KPI rollup with SLA counts |
| `GET /api/telemetry/latest` | Most recent sample for every slice |
| `GET /api/telemetry/sla` | SLA verdict per slice (`?status=` to filter) |
| `GET /api/telemetry/violations` | Only slices at risk or violating |
| `GET /api/telemetry/{slice_id}` | Latest sample, verdict and history |
| `GET /api/telemetry/{slice_id}/sla-target` | The SLA derived from the slice |
| `GET /api/telemetry/{slice_id}/averages` | Rolling means over `?window=` |
| `POST /api/telemetry/tick` | Run one sampling interval now |

## Topology

| Endpoint | Returns |
| --- | --- |
| `GET /api/topology` | Nodes with occupancy, links, slice placements |
| `GET /api/topology/nodes` | Node occupancy (`?node_type=`, `?location=`) |
| `GET /api/topology/nodes/{node_id}` | One node |
| `POST /api/topology/nodes/{node_id}/health?health=` | `healthy`, `degraded` or `offline` |
| `GET /api/topology/placement/{slice_id}` | Where a slice runs and every node's score |
| `POST /api/topology/placement/{slice_id}/rebalance` | Re-run placement |
| `GET /api/topology/candidates/{slice_id}` | Score nodes without moving anything |

## Export

`GET /api/export/slices/{slice_id}?format=…` and
`GET /api/export/slices?format=…` for the whole network as one multi-document
artefact. Add `&download=true` for a file attachment.

| Format | Output |
| --- | --- |
| `kubernetes` | `NetworkSlice` custom resource (YAML) |
| `open5gs` | Subscriber session and AMBR profile (YAML) |
| `snssai` | 3GPP S-NSSAI with the full 5QI and ARP profile (YAML) |
| `flow-rules` | The OpenFlow rules installed for the slice (JSON) |
| `json` | The raw HELIX record |

`GET /api/export/formats` lists them with descriptions.

## Events and system

| Endpoint | Returns |
| --- | --- |
| `GET /api/events` | Audit journal (`?limit=`, `?slice_id=`, `?event_type=`, `?severity=`) |
| `GET /api/events/summary` | Counts by type and severity |
| `GET /api/system/info` | Effective configuration, storage and monitor status |
| `GET /api/system/parser` | Which parser is active and whether the LLM is configured |
| `GET /api/system/controller` | Simulated SDN controller status |
| `GET /api/system/readiness` | Readiness probe |
| `GET /health` | Liveness probe |
| `GET /metrics` | Prometheus exposition |

## WebSocket `/ws`

Connect and receive JSON frames of the shape `{"event": ..., "data": ...}`.
Send the literal string `ping` for a `pong` heartbeat reply — note that the
reply is not JSON.

| Event | Payload |
| --- | --- |
| `slice_created` | The new slice configuration |
| `slice_updated` | The updated slice configuration |
| `slice_deleted` | `{"slice_id": "..."}` |
| `conflict_detected` | Slice name, conflict type, details, proposed remediation |
| `telemetry` | `{"samples": [...], "sla": [...], "summary": {...}}` each interval |

## Error shape

Errors return FastAPI's standard body:

```json
{ "detail": "Slice 'abc' not found" }
```

| Status | Meaning |
| --- | --- |
| `400` | Unparseable intent, empty update, unknown export format |
| `404` | No such slice or node |
| `409` | Capacity exceeded, or an invalid lifecycle transition |
| `429` | Write rate limit exceeded; see `Retry-After` |
| `502` | The SDN controller failed the deployment |
