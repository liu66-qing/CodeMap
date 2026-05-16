"""WebSocket endpoints for real-time streaming."""

from __future__ import annotations

import json
import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import structlog

from evograph.agent.orchestrator import AgentOrchestrator
from evograph.storage.redis_cache import redis_client

logger = structlog.get_logger()
router = APIRouter()

orchestrator = AgentOrchestrator()


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, channel: str) -> None:
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = []
        self.active_connections[channel].append(websocket)

    def disconnect(self, websocket: WebSocket, channel: str) -> None:
        if channel in self.active_connections:
            self.active_connections[channel].remove(websocket)

    async def broadcast(self, channel: str, message: dict) -> None:
        if channel in self.active_connections:
            for connection in self.active_connections[channel]:
                try:
                    await connection.send_json(message)
                except Exception:
                    pass


manager = ConnectionManager()


@router.websocket("/ws/query/{session_id}")
async def query_websocket(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, f"query:{session_id}")
    try:
        while True:
            data = await websocket.receive_json()
            question = data.get("question", "")
            if not question:
                continue

            await websocket.send_json({"type": "start", "question": question})

            async for chunk in orchestrator.stream(question, session_id):
                await websocket.send_json({"type": "chunk", "data": chunk})

            await websocket.send_json({"type": "end"})
    except WebSocketDisconnect:
        manager.disconnect(websocket, f"query:{session_id}")


@router.websocket("/ws/graph/updates")
async def graph_updates_websocket(websocket: WebSocket):
    await manager.connect(websocket, "graph_updates")
    try:
        while True:
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        manager.disconnect(websocket, "graph_updates")
