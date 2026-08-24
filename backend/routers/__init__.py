"""Routers package for STRIX."""

from .slices import router as slices_router
from .websocket import manager
from .websocket import router as websocket_router

__all__ = ["slices_router", "websocket_router", "manager"]
