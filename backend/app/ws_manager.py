"""WebSocket 连接管理器 — 管理前端连接，推送 Agent 进度。

每个连接对应一次"生成游戏"的会话。
Agent 每完成一步 → 通过 WebSocket 推送给前端。
"""

from fastapi import WebSocket
from typing import Dict
import json


class WSManager:
    """管理 WebSocket 连接池。"""

    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        """接受新的 WebSocket 连接。"""
        await websocket.accept()
        self.connections[session_id] = websocket

    async def disconnect(self, session_id: str):
        """断开连接并清理。"""
        if session_id in self.connections:
            del self.connections[session_id]

    async def send_progress(self, session_id: str, agent: str, status: str, message: str, data: dict = None):
        """推送 Agent 进度消息。"""
        if session_id not in self.connections:
            return
        ws = self.connections[session_id]
        payload = {
            "type": "agent_progress",
            "agent": agent,
            "status": status,
            "message": message,
            "data": data or {},
        }
        await ws.send_text(json.dumps(payload, ensure_ascii=False))

    async def send_json(self, session_id: str, payload: dict):
        """推送任意 JSON 消息（用于 agent_log、review_rejected 等自定义类型）。"""
        if session_id not in self.connections:
            return
        ws = self.connections[session_id]
        await ws.send_text(json.dumps(payload, ensure_ascii=False))

    async def send_game_ready(self, session_id: str, game_code: str):
        """推送游戏完成消息。"""
        if session_id not in self.connections:
            return
        ws = self.connections[session_id]
        await ws.send_text(json.dumps({
            "type": "game_ready",
            "game_code": game_code,
        }, ensure_ascii=False))

    async def send_failed(self, session_id: str, reason: str, suggestions: list):
        """推送失败消息。"""
        if session_id not in self.connections:
            return
        ws = self.connections[session_id]
        await ws.send_text(json.dumps({
            "type": "generation_failed",
            "reason": reason,
            "suggestions": suggestions,
        }, ensure_ascii=False))


# 全局单例
ws_manager = WSManager()
