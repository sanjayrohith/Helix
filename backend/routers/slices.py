"""API router for slice management endpoints."""

import time

from fastapi import APIRouter, HTTPException

from models.slice_models import (
    SliceConfig,
    SliceDeploymentResult,
    SliceIntent,
    SliceStats,
)
from routers.websocket import manager
from services.conflict_detector import conflict_detector
from services.intent_parser import intent_parser
from services.sdn_controller import sdn_controller
from services.slice_registry import slice_registry

router = APIRouter(prefix="/api/slices", tags=["slices"])


@router.post("/provision", response_model=SliceDeploymentResult)
async def provision_slice(intent: SliceIntent):
    """
    Provision a new network slice from natural language intent.

    Process:
    1. Parse intent using LLM to generate slice configuration
    2. Run conflict detection against existing slices
    3. If no conflicts, deploy to SDN controller
    4. Broadcast update via WebSocket

    Returns:
        SliceDeploymentResult with success status, config, and any conflicts
    """
    start_time = time.time()

    try:
        # Step 1: Parse intent using Groq LLM
        slice_config = intent_parser.parse_intent(intent.intent)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse intent: {e}") from e

    # Step 2: Run conflict detection
    conflict_report = conflict_detector.detect_conflicts(slice_config)

    if conflict_report.has_conflict:
        # Conflict detected - do NOT deploy
        slice_config.status = "conflict"
        deploy_time = time.time() - start_time

        # Broadcast conflict event
        await manager.broadcast_conflict_detected(
            {
                "slice_name": slice_config.name,
                "conflict_type": conflict_report.conflict_type,
                "details": conflict_report.details,
            }
        )

        return SliceDeploymentResult(
            success=False,
            slice_config=slice_config,
            conflict_report=conflict_report,
            deploy_time_seconds=round(deploy_time, 2),
            message=f"Slice provisioning failed due to {conflict_report.conflict_type} conflict.",
        )

    # Step 3: No conflicts - deploy to SDN controller
    try:
        deployment_success = await sdn_controller.deploy_slice(slice_config)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"SDN controller deployment failed: {e}"
        ) from e

    if deployment_success:
        slice_config.status = "active"
        slice_registry.add_slice(slice_config)

        # Broadcast slice creation event
        await manager.broadcast_slice_created(slice_config.model_dump(mode="json"))
    else:
        slice_config.status = "rejected"

    deploy_time = time.time() - start_time

    return SliceDeploymentResult(
        success=deployment_success,
        slice_config=slice_config,
        conflict_report=conflict_report,
        deploy_time_seconds=round(deploy_time, 2),
        message=(
            f"Slice '{slice_config.name}' successfully deployed and activated."
            if deployment_success
            else "Slice deployment was rejected by the SDN controller."
        ),
    )


@router.get("", response_model=list[SliceConfig])
async def get_all_slices():
    """
    Retrieve all network slices from the registry.

    Returns:
        List of all SliceConfig objects
    """
    return slice_registry.get_all_slices()


@router.get("/stats/summary", response_model=SliceStats)
async def get_slice_stats():
    """
    Get summary statistics for the slice registry.

    Returns:
        SliceStats with totals for slices, bandwidth, and conflicts
    """
    return slice_registry.get_stats()


@router.get("/{slice_id}", response_model=SliceConfig)
async def get_slice(slice_id: str):
    """
    Retrieve a specific slice by ID.

    Args:
        slice_id: UUID of the slice

    Returns:
        SliceConfig for the requested slice

    Raises:
        404 if slice not found
    """
    slice_config = slice_registry.get_slice(slice_id)
    if not slice_config:
        raise HTTPException(
            status_code=404, detail=f"Slice with ID '{slice_id}' not found"
        )
    return slice_config


@router.delete("/{slice_id}", response_model=dict)
async def delete_slice(slice_id: str):
    """
    Delete a slice from the registry and SDN controller.

    Args:
        slice_id: UUID of the slice to delete

    Returns:
        Confirmation message

    Raises:
        404 if slice not found
    """
    slice_config = slice_registry.get_slice(slice_id)
    if not slice_config:
        raise HTTPException(
            status_code=404, detail=f"Slice with ID '{slice_id}' not found"
        )

    # Remove from SDN controller
    await sdn_controller.remove_slice(slice_id)

    # Remove from registry
    deleted_slice = slice_registry.delete_slice(slice_id)

    # Broadcast deletion event
    await manager.broadcast_slice_deleted(slice_id)

    return {
        "message": f"Slice '{deleted_slice.name}' successfully deleted",
        "slice_id": slice_id,
    }
