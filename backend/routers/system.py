"""System introspection endpoints: health, readiness and effective configuration."""

from __future__ import annotations

import platform
import time

from fastapi import APIRouter

from core.config import settings
from services.intent_parser import intent_parser
from services.monitor_loop import monitor_loop
from services.sdn_controller import sdn_controller
from storage.sqlite_store import get_store

router = APIRouter(prefix="/api/system", tags=["system"])

_STARTED_AT = time.time()


@router.get("/info")
async def system_info() -> dict:
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
async def parser_status() -> dict:
    """Report which intent parser is active and whether the LLM is reachable."""
    return intent_parser.describe()


@router.get("/controller")
async def controller_status() -> dict:
    """Report the state of the (simulated) SDN controller."""
    return sdn_controller.get_controller_status()


@router.get("/readiness")
async def readiness() -> dict:
    """Readiness probe: the API is ready when a parser and controller exist."""
    controller = sdn_controller.get_controller_status()
    checks = {
        "parser": True,  # the rule-based parser is always available
        "sdn_controller": bool(controller.get("connected")),
        "telemetry": monitor_loop.running or not settings.telemetry_enabled,
    }
    return {"ready": all(checks.values()), "checks": checks}
