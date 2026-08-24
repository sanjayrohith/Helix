"""Shared pytest fixtures for the HELIX backend test suite."""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

# Tests must never reach out to Groq or touch the developer's database.
os.environ.setdefault("HELIX_FORCE_RULE_PARSER", "true")
os.environ.setdefault("HELIX_PERSISTENCE_ENABLED", "false")
os.environ.setdefault("HELIX_TELEMETRY_ENABLED", "false")
os.environ.setdefault("HELIX_LOG_LEVEL", "WARNING")
# Deployments are simulated with real sleeps; scale them away so tests stay fast.
os.environ.setdefault("HELIX_SDN_STEP_SCALE", "0")
os.environ.setdefault("HELIX_RATE_LIMIT_PER_MINUTE", "0")

import pytest  # noqa: E402


@pytest.fixture
def intent_samples() -> dict[str, str]:
    """Representative operator intents covering each use-case family."""
    return {
        "healthcare": "Deploy an ultra-reliable slice for remote surgery at Apollo Hospital Chennai with 3ms latency",
        "iot": "Connect 50k smart meters across Bangalore for the utility company",
        "broadband": "Provide 2 Gbps broadband for 5000 employees in the Mumbai office",
        "vehicles": "Dedicated V2X slice for an autonomous vehicle fleet at 200 Mbps",
        "industrial": "Smart factory automation slice for robots on the assembly line in Pune",
    }
