"""HELIX - 5G Intent-Based Network Slicing System.

FastAPI application entry point: wires configuration, logging, middleware,
routers and the application lifespan.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.logging_config import configure_logging, get_logger
from core.middleware import install_middleware
from routers import (
    events_router,
    exports_router,
    manager,
    metrics_router,
    slices_router,
    system_router,
    telemetry_router,
    topology_router,
    websocket_router,
)
from services.monitor_loop import monitor_loop

configure_logging()
logger = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start and stop background subsystems alongside the HTTP server."""
    logger.info(
        "%s v%s starting (env=%s, parser=%s, capacity=%.0f Mbps)",
        settings.app_name,
        settings.version,
        settings.environment,
        "llm" if settings.llm_available else "rule-based",
        settings.total_bandwidth_mbps,
    )
    monitor_loop.set_broadcaster(manager)
    await monitor_loop.start()
    yield
    await monitor_loop.stop()
    logger.info("%s shutting down", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    description=(
        "5G Intent-Based Network Slicing System - transform natural language into "
        "validated 5G network slice configurations."
    ),
    version=settings.version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

install_middleware(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(slices_router)
app.include_router(telemetry_router)
app.include_router(events_router)
app.include_router(topology_router)
app.include_router(exports_router)
app.include_router(system_router)
app.include_router(metrics_router)
app.include_router(websocket_router)


@app.get("/", tags=["system"])
async def root() -> dict:
    """Root endpoint listing the available API surface."""
    return {
        "name": settings.app_name,
        "description": "5G Intent-Based Network Slicing System",
        "version": settings.version,
        "endpoints": {
            "provision_slice": "POST /api/slices/provision",
            "get_all_slices": "GET /api/slices",
            "get_slice": "GET /api/slices/{slice_id}",
            "delete_slice": "DELETE /api/slices/{slice_id}",
            "get_stats": "GET /api/slices/stats/summary",
            "simulate_slice": "POST /api/slices/simulate",
            "telemetry_summary": "GET /api/telemetry/summary",
            "slice_telemetry": "GET /api/telemetry/{slice_id}",
            "sla_violations": "GET /api/telemetry/violations",
            "audit_events": "GET /api/events",
            "topology": "GET /api/topology",
            "export_slice": "GET /api/export/slices/{slice_id}?format=kubernetes",
            "metrics": "GET /metrics",
            "slice_placement": "GET /api/topology/placement/{slice_id}",
            "system_info": "GET /api/system/info",
            "parser_status": "GET /api/system/parser",
            "websocket": "WS /ws",
            "docs": "GET /docs",
        },
    }


@app.get("/health", tags=["system"])
async def health_check() -> dict:
    """Liveness probe for container orchestration."""
    return {"status": "healthy", "version": settings.version}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)
