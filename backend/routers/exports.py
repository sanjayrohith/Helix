"""API router for exporting slice configurations to deployable formats."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from services.exporters import EXPORT_FORMATS, export_all, export_slice
from services.slice_registry import slice_registry

router = APIRouter(prefix="/api/export", tags=["export"])

_EXTENSIONS = {
    "open5gs": "yaml",
    "kubernetes": "yaml",
    "snssai": "yaml",
    "flow-rules": "json",
    "json": "json",
}


@router.get("/formats")
async def list_formats() -> dict:
    """The export formats this instance supports."""
    return {
        "formats": [
            {
                "id": "open5gs",
                "label": "Open5GS subscriber profile",
                "media_type": "application/yaml",
                "description": "Session and AMBR profile for an Open5GS subscriber database",
            },
            {
                "id": "kubernetes",
                "label": "Kubernetes NetworkSlice CR",
                "media_type": "application/yaml",
                "description": "Custom resource for applying the slice through a GitOps pipeline",
            },
            {
                "id": "snssai",
                "label": "3GPP S-NSSAI descriptor",
                "media_type": "application/yaml",
                "description": "S-NSSAI with the full 5QI and ARP QoS profile",
            },
            {
                "id": "flow-rules",
                "label": "OpenFlow rules",
                "media_type": "application/json",
                "description": "The flow rules the SDN controller installed for this slice",
            },
            {
                "id": "json",
                "label": "Raw HELIX configuration",
                "media_type": "application/json",
                "description": "The slice record exactly as HELIX stores it",
            },
        ]
    }


@router.get("/slices")
async def export_every_slice(
    fmt: str = Query(default="kubernetes", alias="format", description="Export format"),
    status: str | None = Query(default=None, description="Only slices with this status"),
    download: bool = Query(default=False, description="Send as a file attachment"),
) -> Response:
    """Export every slice as one multi-document artefact."""
    _validate(fmt)
    slices = slice_registry.get_all_slices()
    if status:
        slices = [config for config in slices if config.status == status]
    if not slices:
        raise HTTPException(status_code=404, detail="No slices match the requested filter")

    content, media_type = export_all(slices, fmt)
    return _respond(content, media_type, f"helix-slices.{_EXTENSIONS[fmt]}", download)


@router.get("/slices/{slice_id}")
async def export_one_slice(
    slice_id: str,
    fmt: str = Query(default="kubernetes", alias="format", description="Export format"),
    download: bool = Query(default=False, description="Send as a file attachment"),
) -> Response:
    """Export one slice in the requested format."""
    _validate(fmt)
    config = slice_registry.get_slice(slice_id)
    if not config:
        raise HTTPException(status_code=404, detail=f"Slice '{slice_id}' not found")

    content, media_type = export_slice(config, fmt)
    return _respond(content, media_type, f"{slice_id[:8]}.{_EXTENSIONS[fmt]}", download)


def _validate(fmt: str) -> None:
    if fmt not in EXPORT_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown format '{fmt}'. Supported: {', '.join(EXPORT_FORMATS)}",
        )


def _respond(content: str, media_type: str, filename: str, download: bool) -> Response:
    headers = (
        {"Content-Disposition": f'attachment; filename="{filename}"'} if download else {}
    )
    return Response(content=content, media_type=media_type, headers=headers)
