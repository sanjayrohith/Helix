"""WebSocket router for real-time slice updates."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.auth import try_authenticate_websocket
from core.logging_config import get_logger
from models.slice_models import WebSocketMessage

logger = get_logger("ws")

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections for broadcasting slice updates."""

    def __init__(self):
        self.active_connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        self.active_connections.discard(websocket)

    async def broadcast(self, message: WebSocketMessage):
        """Broadcast a message to all connected clients."""
        message_json = message.model_dump_json()
        disconnected = set()

        for connection in self.active_connections:
            try:
                await connection.send_text(message_json)
            except Exception:
                disconnected.add(connection)

        # Clean up disconnected clients
        for connection in disconnected:
            self.active_connections.discard(connection)

    async def broadcast_slice_created(self, slice_data: dict):
        """Broadcast a slice creation event."""
        message = WebSocketMessage(event="slice_created", data=slice_data)
        await self.broadcast(message)

    async def broadcast_slice_deleted(self, slice_id: str):
        """Broadcast a slice deletion event."""
        message = WebSocketMessage(event="slice_deleted", data={"slice_id": slice_id})
        await self.broadcast(message)

    async def broadcast_slice_updated(self, slice_data: dict):
        """Broadcast a slice configuration change."""
        message = WebSocketMessage(event="slice_updated", data=slice_data)
        await self.broadcast(message)

    async def broadcast_conflict_detected(self, conflict_data: dict):
        """Broadcast a conflict detection event."""
        message = WebSocketMessage(event="conflict_detected", data=conflict_data)
        await self.broadcast(message)

    async def broadcast_telemetry(self, payload: dict):
        """Broadcast one telemetry interval to every connected dashboard."""
        await self.broadcast(WebSocketMessage(event="telemetry", data=payload))

    async def broadcast_sla_alert(self, payload: dict):
        """Broadcast an SLA status change."""
        await self.broadcast(WebSocketMessage(event="sla_alert", data=payload))

    @property
    def connection_count(self) -> int:
        """How many dashboards are currently connected."""
        return len(self.active_connections)


# Global connection manager instance
manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, api_key: str | None = None):
    """
    WebSocket endpoint for real-time slice updates.

    Clients connect to this endpoint to receive:
    - slice_created: When a new slice is successfully deployed
    - slice_deleted: When a slice is removed
    - conflict_detected: When a slice provisioning fails due to conflict
    - telemetry: A sampling interval's KPIs and SLA verdicts

    When HELIX_API_KEYS is configured, a key (read scope is sufficient) must
    be supplied as ?api_key=... - browsers cannot attach a custom header to
    a WebSocket handshake, so a query parameter is the only practical option.
    Unset HELIX_API_KEYS and the socket behaves exactly as before: open to
    anyone who can reach it.
    """
    principal = try_authenticate_websocket(api_key)
    if principal is None:
        # Close before accept(): the handshake never completes, so this
        # never touches the connection pool or broadcasts.
        await websocket.close(code=4401, reason="Invalid or missing API key")
        logger.warning("Rejected WebSocket connection with an invalid API key")
        return

    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, waiting for messages
            # Client can send ping/pong or heartbeat messages
            data = await websocket.receive_text()
            # Echo back any received message (for connection health check)
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
