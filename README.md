<p align="center">
  <img src="https://img.shields.io/badge/5G-Network%20Slicing-00d4ff?style=for-the-badge&logo=5g&logoColor=white" alt="5G Network Slicing"/>
  <img src="https://img.shields.io/badge/LLM-Powered-00ff88?style=for-the-badge&logo=openai&logoColor=white" alt="LLM Powered"/>
  <img src="https://img.shields.io/badge/Intent-Based-ff6b6b?style=for-the-badge&logo=target&logoColor=white" alt="Intent Based"/>
</p>

<h1 align="center">
  <br>
  <img src="https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/clockify.svg" width="100" alt="HELIX Logo"/>
  <br>
  HELIX
  <br>
</h1>

<h4 align="center">🧬 Transform Natural Language into Production-Ready 5G Network Slices</h4>

<p align="center">
  <a href="#-the-problem">Problem</a> •
  <a href="#-our-solution">Solution</a> •
  <a href="#-features">Features</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#-api-reference">API</a> •
  <a href="docs/ARCHITECTURE.md">Architecture Doc</a> •
  <a href="#-roadmap">Roadmap</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/React-61DAFB?style=flat-square&logo=react&logoColor=black" alt="React"/>
  <img src="https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript"/>
  <img src="https://img.shields.io/badge/Tailwind-38B2AC?style=flat-square&logo=tailwind-css&logoColor=white" alt="Tailwind"/>
  <img src="https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker"/>
  <img src="https://img.shields.io/badge/Groq-FF6B6B?style=flat-square&logo=groq&logoColor=white" alt="Groq"/>
</p>

---

## 🎯 The Problem

### The 5G Network Slicing Challenge

Today's telecom operators face a **critical bottleneck** in 5G network management:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CURRENT STATE: Manual CLI Configuration                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Network Engineer                                                          │
│        │                                                                    │
│        ▼                                                                    │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌────────────┐  │
│   │ Understand  │───▶│  Translate  │───▶│   Write     │───▶│  Deploy &  │  │
│   │ Requirements│    │  to Params  │    │ CLI Commands│    │   Debug    │  │
│   └─────────────┘    └─────────────┘    └─────────────┘    └────────────┘  │
│                                                                             │
│   ⏱️ Time: Hours to Days    ❌ Error-prone    🔒 Requires Deep Expertise    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Key Pain Points

| Challenge | Impact | Industry Cost |
|-----------|--------|---------------|
| **Complex Configuration** | Engineers must master 50+ parameters (S-NSSAI, 5QI, ARP, QoS profiles) | $2.3B annually in training costs |
| **Slow Provisioning** | Average 4-8 hours to provision a single slice | Lost revenue from delayed services |
| **Human Errors** | 23% of network outages caused by misconfigurations | $5.6M average cost per outage |
| **Scalability Crisis** | Can't keep pace with enterprise 5G demands | 340% increase in slice requests by 2025 |
| **Knowledge Silos** | Expertise locked in few senior engineers | 67% of telcos report skill shortages |

---

## 💡 Our Solution

### HELIX: Intent-Based Network Slicing

HELIX bridges the gap between **human intent** and **3GPP configuration** — then
keeps watching the slice after it is deployed.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      HELIX: Natural Language to 5G Slice                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Network Operator                                                          │
│        │                                                                    │
│        ▼                                                                    │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  "Create a high-security low-latency slice for 500 hospital         │   │
│   │   devices in Chennai with guaranteed 50Mbps"                        │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│        │                                                                    │
│        ▼                                                                    │
│   ┌─────────┐  ┌──────────┐  ┌─────────┐  ┌───────────┐  ┌────────────┐    │
│   │ Intent  │─▶│Admission │─▶│  SDN    │─▶│ Placement │─▶│ Telemetry  │    │
│   │ Parser  │  │ Control  │  │ Deploy  │  │  on Node  │  │  + SLA     │    │
│   └─────────┘  └──────────┘  └─────────┘  └───────────┘  └────────────┘    │
│    LLM with     8 checks,     OpenFlow      scored on      live KPIs,       │
│    offline      all findings  rules         real capacity  graded verdicts  │
│    fallback     at once                                                     │
│                                                                             │
│   ⏱️ Seconds    ✅ Validated    📈 Monitored    📤 Exportable               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### How We Solve Each Problem

| Problem | HELIX Solution | Result |
|---------|----------------|--------|
| Complex configuration | Plain English maps to 3GPP-compliant parameters, and the parser shows how it derived each one | No CLI knowledge required |
| Slow provisioning | One automated pipeline from intent to active, monitored slice | Seconds instead of hours |
| Human error | Eight admission checks report every problem at once, with a fix that provably converges | Fewer resubmit cycles |
| No feedback after deploy | Live KPIs and SLA verdicts derived from the slice's own intent | Violations surface on their own |
| Configuration lock-in | Export to Open5GS, Kubernetes, S-NSSAI or OpenFlow | The output is deployable elsewhere |
| Knowledge silos | Templates that double as documentation for what the parser understands | Anyone can provision a slice |

---

## ✨ Features

### 🧠 Intent Parsing With a Fallback That Actually Works

Two parsers share one contract. The **LLM parser** (Groq) handles arbitrary
phrasing. The **deterministic parser** handles the common cases offline, with
no API key and no network call — and takes over automatically on *any* LLM
failure, recording why on the response.

```
"hospital" / "remote surgery"   →  SST=2 (URLLC), 5QI=69, ARP=1, strict isolation
"smart meters" / "IoT sensors"  →  SST=3 (mMTC),  5QI=80, ARP=8, shared isolation
"autonomous vehicles" / "V2X"   →  SST=2 (URLLC), 5QI=79, ARP=2, dedicated
"factory robots"                →  SST=2 (URLLC), 5QI=82, ARP=3, dedicated
"cloud gaming" / "VR"           →  SST=1 (eMBB),  5QI=80, ARP=6, dedicated
"stadium broadcast"             →  SST=1 (eMBB),  5QI=2,  ARP=4, dedicated
"first responders"              →  SST=2 (URLLC), 5QI=65, ARP=1, critical
"campus broadband"              →  SST=1 (eMBB),  5QI=9,  ARP=5, shared
```

The deterministic parser is **unit-aware** — it reads `2 Gbps`, `800 kbps`,
`500 microseconds`, `50k sensors`, `1,200 vehicles` — and **explainable**: it
records how it derived every field, which the dashboard shows under *"How was
this derived?"*.

### 🛡️ Admission Control That Reports Everything At Once

Eight checks run on every request. All findings come back together, ranked by
severity, with a **merged set of changes that would make the slice deploy**.

| Check | Severity | Catches |
| --- | --- | --- |
| Bandwidth capacity | blocking | Total GBR over capacity; names preemptable slices |
| S-NSSAI collision | blocking | Duplicate SST+SD; proposes the next free SD |
| ARP priority | blocking | A second slice claiming ARP=1 |
| Regulatory policy | blocking | Large populations without strict isolation |
| Latency feasibility | warning | A target tighter than the 5QI packet delay budget |
| Isolation consistency | warning | Critical security running on shared resources |
| Device density | advisory | Implausible per-device bandwidth |
| Capacity share | advisory | One slice reserving over half the network |

Only **blocking** findings stop a deployment — an optimistic latency target is
worth flagging, not worth refusing. Applying the merged remediation to a slice
with three simultaneous blocking conflicts produces a configuration that
passes cleanly; there is a test that asserts exactly that.

### 📈 Live Telemetry and SLA Monitoring

Every active slice carries running KPIs — throughput, offered load, latency,
jitter, packet loss, PRB utilisation, attached devices, availability —
regenerated on a background loop and streamed to every open dashboard.

The numbers **derive from the slice's own configuration**, so they mean
something: a strictly isolated slice really does show lower jitter and loss
than a shared one, and latency inflates toward the 5QI budget under congestion.

SLA targets come from the intent rather than a separate policy file: the
latency target with tolerance, availability by security classification (99.99%
for critical), packet loss by slice type (0.1% for URLLC). Verdicts are graded
over a rolling window and reported as a 0–100 compliance score with per-KPI
breaches — and the monitor alerts on status *transitions*, so a slice sitting
in violation alerts once, not on every tick.

### 🗺️ Network Topology Digital Twin

The network is modelled as real gNB, edge, UPF and core nodes across four
metros, each with its own capacity, slice slots, device limit, latency floor
and supported isolation levels. Every slice is **placed on a node**, and the
placement is explainable — each candidate carries its score and the reasons it
was preferred or ruled out.

Nodes can be marked degraded or offline to exercise failover.

### 🔄 Full Slice Lifecycle

Beyond create and delete: **dry-run** an intent before committing to it,
**patch** a live slice, **scale** its bandwidth by a factor or to an absolute
value, and **suspend/resume** to return guaranteed bandwidth to the pool
without losing the configuration.

### 📤 Export to Something Deployable

A slice that only exists inside HELIX is a demo. Export any slice — or the
whole network as one multi-document artefact — as an **Open5GS** subscriber
profile, a **Kubernetes** `NetworkSlice` custom resource, a **3GPP S-NSSAI**
descriptor with the full 5QI and ARP profile, or the **OpenFlow rules** the
controller installed.

### 🔭 Operations

- **Prometheus metrics** at `/metrics` — 16 families covering capacity, slice
  inventory, per-slice KPIs, SLA scores, node occupancy and controller health
- **Audit journal** — every provisioning attempt, conflict, lifecycle change
  and SLA transition, persisted and queryable
- **Request correlation** — an `X-Request-ID` that flows through the logs, so
  one provisioning request is followable across every stage
- **SQLite persistence** — slices survive a restart instead of vanishing
- **Rate limiting** on writes, with reads left free for dashboards

### ⚡ WebSocket Real-Time Updates

```javascript
{ "event": "slice_created",     "data": { /* full slice config */ } }
{ "event": "slice_updated",     "data": { /* full slice config */ } }
{ "event": "slice_deleted",     "data": { "slice_id": "uuid" } }
{ "event": "conflict_detected", "data": { "conflict_type": "...", "auto_remediation": {...} } }
{ "event": "telemetry",         "data": { "samples": [...], "sla": [...], "summary": {...} } }
```

The dashboard polls only while the socket is closed.

---

## 🚀 Quick Start

> **No API key required.** Without `GROQ_API_KEY`, HELIX uses its deterministic
> intent parser and every other feature — admission control, telemetry, SLA
> grading, topology, export — behaves identically.

### Docker

```bash
git clone https://github.com/yourusername/helix.git
cd helix
docker compose up --build
```

To enable the LLM parser, add a key first:

```bash
cp .env.example .env
# set GROQ_API_KEY in .env
```

### Local development

```bash
make setup     # virtualenv + backend and frontend dependencies
make dev       # API on :8000, dashboard on :5173
```

Run `make help` for every available task.

### Verify it works

```bash
make test      # backend suite, ~1 second, no network needed
make smoke     # end-to-end against a running API
```

`make smoke` drives the whole path — dry run, provision, telemetry, placement,
every export format, metrics, audit journal, suspend/resume, teardown — and
prints each check as it passes.

### Access points

| Service | URL | Description |
|---------|-----|-------------|
| 🖥️ Dashboard | http://localhost:5173 | Operator interface |
| 🔌 API | http://localhost:8000 | REST endpoints |
| 📚 Docs | http://localhost:8000/docs | Swagger UI |
| 📊 Metrics | http://localhost:8000/metrics | Prometheus exposition |

### Try it

Paste any of these into the intent box — or open **Templates** for eight
ready-made examples:

```
Ultra-reliable strictly isolated slice for remote surgery at Apollo Hospital
Chennai with 3ms latency and 80 Mbps for 400 medical devices

Connect 50k smart meters across Bangalore for the utility company with 40 Mbps

Dedicated V2X slice for an autonomous vehicle fleet in Pune at 150 Mbps
```

Hit **Dry run** first to see whether an intent would deploy, and what it would
take if not, without touching the network.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              HELIX ARCHITECTURE                              │
└─────────────────────────────────────────────────────────────────────────────┘

                              ┌─────────────────┐
                              │   OPERATOR UI   │
                              │  React + Vite   │
                              │   Tailwind CSS  │
                              └────────┬────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
                    ▼                  ▼                  ▼
            ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
            │  REST API    │  │  WebSocket   │  │   Static     │
            │  /api/slices │  │     /ws      │  │   Assets     │
            └──────┬───────┘  └──────┬───────┘  └──────────────┘
                   │                 │
                   └────────┬────────┘
                            │
                   ┌────────▼────────┐
                   │    FastAPI      │
                   │   Application   │
                   └────────┬────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│ Intent Parser │  │   Conflict    │  │     SDN       │
│   (Groq LLM)  │  │   Detector    │  │  Controller   │
│               │  │               │  │    (Mock)     │
│ ┌───────────┐ │  │ • Bandwidth   │  │               │
│ │  LLaMA    │ │  │ • S-NSSAI     │  │ • Deploy      │
│ │  3.3-70b  │ │  │ • ARP         │  │ • Remove      │
│ └───────────┘ │  │ • Regulatory  │  │ • Status      │
└───────────────┘  └───────────────┘  └───────┬───────┘
                                              │
                                     ┌────────▼────────┐
                                     │  Slice Registry │
                                     │   (In-Memory)   │
                                     │                 │
                                     │ Pre-populated:  │
                                     │ • eMBB Slice    │
                                     │ • URLLC Slice   │
                                     │ • mMTC Slice    │
                                     └─────────────────┘
```

### Project Structure

```
helix/
├── 🔙 backend/
│   ├── main.py                     # FastAPI entry point and lifespan
│   ├── core/
│   │   ├── config.py               # ⚙️  All settings, resolved from the environment
│   │   ├── logging_config.py       # 📝 Console + JSON formatters, correlation ids
│   │   ├── middleware.py           # 🔗 Request context, timing, rate limiting
│   │   └── telecom.py              # 📡 3GPP tables: 5QI, ARP bands, use-case profiles
│   ├── models/                     # Pydantic schemas
│   │   ├── slice_models.py         #    slices, conflicts, simulation
│   │   ├── telemetry_models.py     #    KPI samples, SLA targets and verdicts
│   │   ├── topology_models.py      #    nodes, links, placement
│   │   ├── event_models.py         #    audit journal
│   │   └── lifecycle_models.py     #    update, scale, status transitions
│   ├── routers/
│   │   ├── slices.py               # Provision, simulate, lifecycle, stats
│   │   ├── telemetry.py            # KPIs, SLA verdicts, violations
│   │   ├── topology.py             # Nodes, occupancy, placement
│   │   ├── exports.py              # Open5GS / Kubernetes / S-NSSAI / flow rules
│   │   ├── events.py               # Audit journal
│   │   ├── system.py               # Health, readiness, info, /metrics
│   │   └── websocket.py            # Real-time event stream
│   ├── services/
│   │   ├── intent_parser.py        # 🧠 Parser selection and fallback
│   │   ├── llm_parser.py           # 🤖 Groq integration (lazy)
│   │   ├── rule_parser.py          # 📐 Deterministic offline parser
│   │   ├── conflict_detector.py    # 🛡️  Admission control + remediation
│   │   ├── slice_registry.py       # 💾 Authoritative slice state
│   │   ├── sdn_controller.py       # 🌐 Simulated Ryu controller + flow rules
│   │   ├── topology.py             # 🗺️  Digital twin and placement scoring
│   │   ├── telemetry.py            # 📈 KPI simulation
│   │   ├── sla_monitor.py          # 🎯 SLA derivation and grading
│   │   ├── monitor_loop.py         # 🔄 Background sampling loop
│   │   ├── audit_log.py            # 📜 Append-only event journal
│   │   ├── metrics.py              # 📊 Prometheus exposition
│   │   └── exporters.py            # 📤 Deployable config artefacts
│   ├── storage/
│   │   └── sqlite_store.py         # Durable slices and audit events
│   └── tests/                      # 154 tests, ~1s, no network required
│
├── 🎨 frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── IntentInput.tsx         # NL input, templates, history, dry run
│   │   │   ├── SimulationResult.tsx    # Dry-run verdict and capacity impact
│   │   │   ├── DeploymentResult.tsx    # Outcome and parse provenance
│   │   │   ├── ConflictAlert.tsx       # Findings by severity + remediation
│   │   │   ├── NetworkKpiBar.tsx       # Live network KPIs
│   │   │   ├── SlaAlertPanel.tsx       # Slices outside SLA
│   │   │   ├── TopologyPanel.tsx       # Node occupancy
│   │   │   ├── SliceDetailDrawer.tsx   # Per-slice deep dive
│   │   │   ├── SliceFilterBar.tsx      # Search, filter, sort
│   │   │   ├── ActivityFeed.tsx        # Audit journal
│   │   │   ├── Sparkline.tsx           # Inline SVG KPI charts
│   │   │   └── ...
│   │   ├── services/{api,websocket}.ts
│   │   ├── hooks/useIntentHistory.ts
│   │   └── types/{slice,telemetry}.ts
│   └── package.json
│
├── 📄 docs/
│   ├── ARCHITECTURE.md             # How it fits together, and why
│   ├── API.md                      # Full endpoint reference
│   ├── SECURITY.md                 # Threat model, auth, what's out of scope
│   └── PERFORMANCE.md              # Load-test baselines and the one real optimisation
├── scripts/smoke_test.py           # End-to-end verification
├── .github/workflows/ci.yml        # Lint, test, build, smoke
├── Makefile                        # make help
└── docker-compose.yml
```

---

## 📡 API Reference

### Provision a Slice

```bash
POST /api/slices/provision
```

**Request:**
```json
{
  "intent": "Create a high-security low-latency slice for 500 hospital devices in Chennai with guaranteed 50Mbps"
}
```

**Response:**
```json
{
  "success": true,
  "slice_config": {
    "slice_id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Chennai Hospital Critical Care",
    "sst": 2,
    "sd": "0x000100",
    "qos_5qi": 69,
    "arp_priority": 1,
    "guaranteed_bitrate_mbps": 50.0,
    "max_bitrate_mbps": 100.0,
    "latency_ms": 5,
    "security_level": "critical",
    "isolation": "strict",
    "device_count": 500,
    "use_case": "healthcare",
    "location": "Chennai",
    "status": "active",
    "created_at": "2024-01-15T10:30:00Z"
  },
  "conflict_report": {
    "has_conflict": false,
    "conflict_type": null,
    "details": "No conflicts detected",
    "suggestions": []
  },
  "deploy_time_seconds": 2.34,
  "message": "Slice 'Chennai Hospital Critical Care' successfully deployed"
}
```

### All Endpoints

Full reference in [`docs/API.md`](docs/API.md); interactive docs at `/docs`.

**Slices**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/slices/provision` | Create a slice from an intent |
| `POST` | `/api/slices/simulate` | Dry run — would this deploy, and what would it take? |
| `GET` | `/api/slices` | List slices (`?use_case=`, `?location=`, `?status=`) |
| `GET` | `/api/slices/{id}` | One slice |
| `PATCH` | `/api/slices/{id}` | Partial update, re-checking capacity |
| `POST` | `/api/slices/{id}/scale` | Scale bandwidth by factor or to a target |
| `POST` | `/api/slices/{id}/suspend` · `/resume` | Release and reclaim bandwidth |
| `DELETE` | `/api/slices/{id}` | Tear down, reporting bandwidth released |
| `GET` | `/api/slices/stats/summary` · `/breakdown` | Counters and groupings |

**Telemetry, SLA and topology**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/telemetry/summary` | Network-wide KPI rollup |
| `GET` | `/api/telemetry/{id}` | Latest sample, SLA verdict, history |
| `GET` | `/api/telemetry/violations` | Slices at risk or breaching |
| `GET` | `/api/telemetry/{id}/sla-target` | The SLA derived from the slice |
| `POST` | `/api/telemetry/tick` | Run one sampling interval now |
| `GET` | `/api/topology` | Nodes, links and slice placements |
| `GET` | `/api/topology/placement/{id}` | Where a slice runs, and every node's score |
| `POST` | `/api/topology/placement/{id}/rebalance` | Re-run placement |

**Export, events and system**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/export/slices/{id}?format=` | `kubernetes`, `open5gs`, `snssai`, `flow-rules`, `json` |
| `GET` | `/api/export/slices?format=` | The whole network as one artefact |
| `GET` | `/api/events` | Audit journal (filterable) |
| `GET` | `/api/system/info` · `/parser` · `/readiness` | Configuration and health |
| `GET` | `/health` · `/metrics` | Liveness probe · Prometheus exposition |
| `WS` | `/ws` | Real-time slice, conflict and telemetry events |

---

## 🔬 5G Technical Reference

### S-NSSAI (Network Slice Selection)

| SST | Name | Use Case | Characteristics |
|-----|------|----------|-----------------|
| 1 | **eMBB** | Enhanced Mobile Broadband | High throughput, video streaming |
| 2 | **URLLC** | Ultra-Reliable Low-Latency | Mission-critical, healthcare |
| 3 | **mMTC** | Massive Machine Type | IoT, sensors, smart city |

### 5QI (QoS Identifier)

| 5QI | Service | Latency | Use Case |
|-----|---------|---------|----------|
| 1 | Conversational Voice | 100ms | VoLTE |
| 9 | Video Streaming | 300ms | Netflix, YouTube |
| 69 | Mission Critical | 60ms | Healthcare, emergency |
| 79 | V2X | 50ms | Autonomous vehicles |
| 80 | Low-latency eMBB | 10ms | Gaming, AR/VR |

### ARP (Allocation & Retention Priority)

| Priority | Level | Use Case |
|----------|-------|----------|
| 1 | Highest | Emergency services, critical healthcare |
| 2-5 | High | Enterprise premium services |
| 6-10 | Medium | Standard business |
| 11-15 | Low | Consumer, best effort |

---

## 🛤️ Roadmap

### Shipped

- ✅ Deterministic offline parser with automatic LLM fallback
- ✅ Eight-check admission control reporting every finding at once
- ✅ Auto-remediation that converges to a deployable configuration
- ✅ Dry-run simulation before committing to a change
- ✅ Live KPI telemetry streamed over WebSocket
- ✅ SLA targets derived from intent, graded on a rolling window
- ✅ Network topology twin with explainable slice placement
- ✅ Full lifecycle: patch, scale, suspend, resume
- ✅ Export to Open5GS, Kubernetes, S-NSSAI and OpenFlow
- ✅ SQLite persistence, audit journal, Prometheus metrics
- ✅ 154 tests and an end-to-end smoke test in CI

### Next

- 🔜 Multi-operator authentication and per-tenant slice isolation
- 🔜 Real Ryu / ONOS controller integration behind the current interface
- 🔜 Closed-loop remediation: act on an SLA violation, do not only report it
- 🔜 Historical telemetry retention beyond the in-memory ring buffer
- 🔜 Slice templates saved from an existing deployment
- 🔜 Multi-region topology with inter-region link constraints

---

## 🤝 Contributing

Full guide in [`CONTRIBUTING.md`](CONTRIBUTING.md).

```bash
make setup          # virtualenv + dependencies
make dev            # API on :8000, dashboard on :5173

# before pushing
make lint           # ruff on the backend, tsc on the frontend
make test           # backend suite
make smoke          # end-to-end against a running API
```

Commits follow [Conventional Commits](https://www.conventionalcommits.org/).
Write the body to explain *why*, not what the diff already shows.

---

## 📊 Performance and Quality

| Metric | Value | Notes |
|--------|-------|-------|
| Intent parse (deterministic) | <1 ms | No network call, no API key |
| Intent parse (LLM) | ~2–5 s | Groq API latency; falls back on failure |
| Admission control | <5 ms | Eight checks over in-memory state |
| SDN deployment | 1–3 s | Simulated; `HELIX_SDN_STEP_SCALE=0` for instant |
| Telemetry interval | 2 s | Configurable; streamed to every dashboard |
| Backend test suite | ~1 s | 154 tests, no network or database required |
| Dashboard bundle | 64 KB gzipped | No charting library; sparklines are inline SVG |

**Quality gates in CI:** ruff on the backend, `tsc --noEmit` and a production
build on the frontend, the full test suite, then an eleven-assertion smoke test
against a live instance.

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Groq** - Lightning-fast LLM inference
- **3GPP** - 5G standards and specifications
- **FastAPI** - Modern Python web framework
- **React** - UI component library
- **Tailwind CSS** - Utility-first styling

---

<p align="center">
  <b>Built with ❤️ for the future of 5G networking</b>
</p>

<p align="center">
  <a href="https://github.com/yourusername/helix/issues">Report Bug</a>
  •
  <a href="https://github.com/yourusername/helix/issues">Request Feature</a>
  •
  <a href="https://github.com/yourusername/helix/discussions">Discussions</a>
</p>

<p align="center">
  <img src="https://img.shields.io/github/stars/yourusername/helix?style=social" alt="Stars"/>
  <img src="https://img.shields.io/github/forks/yourusername/helix?style=social" alt="Forks"/>
  <img src="https://img.shields.io/github/watchers/yourusername/helix?style=social" alt="Watchers"/>
</p>
