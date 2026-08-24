"""
HELIX - 5G Intent-Based Network Slicing System

Main FastAPI application entry point.
"""

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import slices_router, websocket_router

# Load environment variables
load_dotenv()

# Create FastAPI application
app = FastAPI(
    title="HELIX",
    description="5G Intent-Based Network Slicing System - Transform natural language into validated 5G network slice configurations",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS - allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(slices_router)
app.include_router(websocket_router)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "HELIX",
        "description": "5G Intent-Based Network Slicing System",
        "version": "1.0.0",
        "endpoints": {
            "provision_slice": "POST /api/slices/provision",
            "get_all_slices": "GET /api/slices",
            "get_slice": "GET /api/slices/{slice_id}",
            "delete_slice": "DELETE /api/slices/{slice_id}",
            "get_stats": "GET /api/slices/stats/summary",
            "websocket": "WS /ws",
            "docs": "GET /docs",
        },
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
