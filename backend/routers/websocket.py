"""WebSocket router for real-time slice updates."""


from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from models.slice_models import WebSocketMessage

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

    async def broadcast_conflict_detected(self, conflict_data: dict):
        """Broadcast a conflict detection event."""
        message = WebSocketMessage(event="conflict_detected", data=conflict_data)
        await self.broadcast(message)


# Global connection manager instance
manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time slice updates.

    Clients connect to this endpoint to receive:
    - slice_created: When a new slice is successfully deployed
    - slice_deleted: When a slice is removed
    - conflict_detected: When a slice provisioning fails due to conflict
    """
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
