"""Routers package for HELIX."""

from .events import router as events_router
from .slices import router as slices_router
from .system import router as system_router
from .telemetry import router as telemetry_router
from .topology import router as topology_router
from .websocket import manager
from .websocket import router as websocket_router

__all__ = [
    "slices_router",
    "telemetry_router",
    "events_router",
    "topology_router",
    "system_router",
    "websocket_router",
    "manager",
]
