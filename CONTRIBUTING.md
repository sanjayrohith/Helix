# Contributing to HELIX

## Getting set up

```bash
make setup     # virtualenv + backend and frontend dependencies
make dev       # API on :8000, dashboard on :5173
```

No `GROQ_API_KEY` is required. Without one HELIX uses its deterministic intent
parser, and everything else — admission control, telemetry, SLA grading,
topology, export — behaves identically.

To use the LLM parser, copy `.env.example` to `.env` and set `GROQ_API_KEY`.

## Before you push

```bash
make lint      # ruff on the backend, tsc on the frontend
make test      # backend test suite
make smoke     # end-to-end, against a running API
```

CI runs all three. The suite finishes in about a second; if a change makes it
noticeably slower, something is probably sleeping or hitting the network when
it should not be.

## Conventions

**Commits** follow Conventional Commits: `feat(scope):`, `fix(scope):`,
`test(scope):`, `docs:`, `chore:`, `ci:`, `style:`. Write the body to explain
*why*, not what the diff already shows. If a test caught a real bug, say so.

**Python** is formatted to a 100-column limit and linted by ruff (`E`, `F`,
`I`, `UP`, `B`, `C4`). Use `from __future__ import annotations` and PEP 604
unions. Every public function gets a docstring saying what it does, not
restating its signature.

**TypeScript** runs under `strict`. Prefer explicit types on module
boundaries; let inference handle the rest.

**Comments** explain reasoning that is not obvious from the code — a
non-obvious constant, a deliberate trade-off, a bug being guarded against.
Do not narrate what the next line does.

## Adding to the domain

**A new conflict check** goes in `ConflictDetector` as a `_check_*` method
returning `ConflictFinding | None`, added to the tuple in `detect_conflicts`.
Choose its severity carefully: `blocking` prevents deployment, so use it only
when the slice genuinely cannot work. Give it a `remediation` if a mechanical
fix exists, and add a test that the remediation actually clears the finding.

**A new use-case profile** goes in `core/telecom.py`. Keywords are matched
against lowercased intent text, and multi-word keywords score double, so
prefer specific phrases over single common words.

**A new export format** is a builder function in `services/exporters.py`
registered in `export_slice`. Add it to `EXPORT_FORMATS` and to the parametrised
test that asserts every format parses.

**A new KPI** needs a field on `SliceTelemetry`, derivation in
`TelemetryEngine._derive`, and — if it should be graded — a target in
`derive_target` plus a weight in `KPI_WEIGHTS`.

## Testing notes

The test configuration in `backend/tests/conftest.py` removes every source of
non-determinism: the deterministic parser, no persistence, no simulated
deployment sleeps, and no random telemetry outages. If you need an outage in a
test, inject one by setting `outage_ticks_remaining` on the slice's runtime
state rather than raising the global rate.

Tests that touch the shared registry should save and restore its contents, as
the existing fixtures do — the registry is a module-level singleton.
