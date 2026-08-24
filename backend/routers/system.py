"""System introspection endpoints: health, readiness and effective configuration."""

from __future__ import annotations

import platform
import time

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from core.auth import Principal, ReadScope
from core.config import settings
from services.intent_parser import intent_parser
from services.metrics import render_metrics
from services.monitor_loop import monitor_loop
from services.sdn_controller import sdn_controller
from storage.sqlite_store import get_store

router = APIRouter(prefix="/api/system", tags=["system"])

_STARTED_AT = time.time()


@router.get("/info")
async def system_info(principal: Principal = ReadScope) -> dict:
    """Report the effective, non-secret configuration of this instance."""
    return {
        "app": settings.as_dict(),
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.system(),
            "uptime_seconds": round(time.time() - _STARTED_AT, 1),
        },
        "storage": get_store().stats(),
        "monitor": monitor_loop.status(),
    }


@router.get("/parser")
async def parser_status(principal: Principal = ReadScope) -> dict:
    """Report which intent parser is active and whether the LLM is reachable."""
    return intent_parser.describe()


@router.get("/controller")
async def controller_status(principal: Principal = ReadScope) -> dict:
    """Report the state of the (simulated) SDN controller."""
    return sdn_controller.get_controller_status()


@router.get("/readiness")
async def readiness() -> dict:
    """Readiness probe: the API is ready when a parser and controller exist.

    Deliberately unauthenticated, like /health: an orchestrator's readiness
    probe generally cannot attach an API key, and the response reveals
    nothing beyond a boolean and a handful of subsystem names.
    """
    controller = sdn_controller.get_controller_status()
    checks = {
        "parser": True,  # the rule-based parser is always available
        "sdn_controller": bool(controller.get("connected")),
        "telemetry": monitor_loop.running or not settings.telemetry_enabled,
    }
    return {"ready": all(checks.values()), "checks": checks}


metrics_router = APIRouter(tags=["system"])


@metrics_router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics(principal: Principal = ReadScope) -> str:
    """Prometheus exposition endpoint.

    Mounted at the root rather than under /api so a default scrape config
    finds it without extra path configuration. Requires a read-scoped key
    when auth is enabled - the exposition includes slice and node names, so
    it is not something to leave open by default the way /health is. A
    Prometheus scrape_config can attach one via 'authorization: credentials:'.
    """
    return render_metrics()
