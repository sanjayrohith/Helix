"""Routers package for HELIX."""

from .slices import router as slices_router
from .system import router as system_router
from .websocket import manager
from .websocket import router as websocket_router

__all__ = ["slices_router", "websocket_router", "system_router", "manager"]
