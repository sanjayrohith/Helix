"""Routers package for STRIX."""

from .slices import router as slices_router
from .websocket import router as websocket_router, manager

__all__ = ["slices_router", "websocket_router", "manager"]
