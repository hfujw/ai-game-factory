"""WebSocket 连接管理器。"""

from fastapi import WebSocket
from typing import Dict
import json
import logging

logger = logging.getLogger(__name__)


class WSManager:
    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        self.connections[session_id] = websocket

    async def disconnect(self, session_id: str):
        self.connections.pop(session_id, None)

    async def _safe_send(self, session_id: str, payload: dict):
        """安全发送：连接断开时静默处理，不抛崩主流程"""
        ws = self.connections.get(session_id)
        if not ws:
            return
        try:
            await ws.send_text(json.dumps(payload, ensure_ascii=False))
        except Exception as e:
            logger.debug("WebSocket 发送失败 [%s]: %s", session_id, str(e))
            self.connections.pop(session_id, None)

    async def send_progress(self, session_id: str, agent: str, status: str, message: str, data: dict = None):
        await self._safe_send(session_id, {
            "type": "agent_progress",
            "agent": agent,
            "status": status,
            "message": message,
            "data": data or {},
        })

    async def send_json(self, session_id: str, payload: dict):
        await self._safe_send(session_id, payload)

    async def send_game_ready(self, session_id: str, game_code: str):
        await self._safe_send(session_id, {
            "type": "game_ready",
            "game_code": game_code,
        })

    async def send_failed(self, session_id: str, reason: str, suggestions: list):
        await self._safe_send(session_id, {
            "type": "generation_failed",
            "reason": reason,
            "suggestions": suggestions,
        })


ws_manager = WSManager()
