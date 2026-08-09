import json
import logging

from fastapi import WebSocket, WebSocketDisconnect

from backend.db.models import Signal, Verdict
from backend.logging_config import log_event

logger = logging.getLogger("dashboard.ws")


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active:
            self.active.remove(websocket)

    async def broadcast(self, message: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Dashboard doesn't need to send anything up; just keep the
            # connection alive and detect disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


def _signal_to_ws_message(signal: Signal, verdict: Verdict | None) -> dict:
    return {
        "type": "new_signal",
        "signal": {
            "id": signal.id,
            "event_id": signal.event_id,
            "symbol": signal.symbol,
            "direction": signal.direction,
            "price": signal.price,
            "received_at": signal.received_at.isoformat() if signal.received_at else None,
        },
        "verdict": None if verdict is None else {
            "id": verdict.id,
            "llm_decision": verdict.llm_decision,
            "checklist": verdict.checklist,
            "rationale": verdict.rationale,
            "manual_decision": verdict.manual_decision,
        },
    }


async def broadcast_new_signal(signal: Signal, verdict: Verdict | None):
    message = _signal_to_ws_message(signal, verdict)
    log_event(logger, "broadcasting_signal", event_id=signal.event_id)
    await manager.broadcast(message)
