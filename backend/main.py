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
from routers import slices_router, system_router, websocket_router

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
    yield
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(slices_router)
app.include_router(system_router)
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
