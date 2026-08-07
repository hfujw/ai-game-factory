"""WebSocket 消息 Pydantic 模型 — 所有 event type 的校验规则。

使用方式：
    from app.schemas.websocket import ClientMessage, ServerMessage
    data = await websocket.receive_json()
    msg = ClientMessage.model_validate(data)  # 自动校验
"""

from __future__ import annotations
from typing import Literal, Annotated
from pydantic import BaseModel, Field, field_validator


# ═══════════════════════════════════════════════════════════
# 客户端 → 服务端
# ═══════════════════════════════════════════════════════════

class GenerateRequest(BaseModel):
    """用户发起生成请求。"""
    type: Literal["generate"] = "generate"
    event: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="用户输入的主题",
    )
    idempotency_key: str | None = Field(
        None,
        min_length=8,
        max_length=64,
        description="幂等键：相同 key 的重复请求返回缓存结果",
    )

    @field_validator("event")
    @classmethod
    def no_control_chars(cls, v: str) -> str:
        if any(ord(c) < 32 for c in v if c not in ("\n", "\t")):
            raise ValueError("输入包含无效控制字符")
        return v.strip()


class CancelRequest(BaseModel):
    """用户取消正在进行的生成。"""
    type: Literal["cancel"] = "cancel"


class PingRequest(BaseModel):
    """心跳保活。"""
    type: Literal["ping"] = "ping"


# 联合类型
ClientMessage = GenerateRequest | CancelRequest | PingRequest


# ═══════════════════════════════════════════════════════════
# 服务端 → 客户端
# ═══════════════════════════════════════════════════════════

class ThinkingMessage(BaseModel):
    """完整的思考气泡。"""
    type: Literal["thinking"] = "thinking"
    step: int = Field(..., ge=0)
    thought: str = Field(..., max_length=5000)
    tool: str = Field(..., max_length=32)
    budget: float = Field(..., ge=0)


class ThinkingStreamMessage(BaseModel):
    """流式思考——逐 chunk 追加。"""
    type: Literal["thinking_stream"] = "thinking_stream"
    step: int = Field(..., ge=0)
    chunk: str = Field(..., max_length=1000)
    tool: str = Field(..., max_length=32)
    budget: float = Field(..., ge=0)


class HeartbeatMessage(BaseModel):
    """保活信号。"""
    type: Literal["heartbeat"] = "heartbeat"
    tool: str = Field(..., max_length=32)
    step: int = Field(..., ge=0)
    budget: float = Field(..., ge=0)


class ToolResultMessage(BaseModel):
    """工具执行完成。"""
    type: Literal["tool_result"] = "tool_result"
    step: int = Field(..., ge=0)
    tool: Literal["search", "design", "compose", "render", "verify", "system"]  # type: ignore[arg-type]
    summary: str = Field(..., max_length=500)
    budget: float = Field(..., ge=0)


class HtmlChunkMessage(BaseModel):
    """流式 HTML 片段。"""
    type: Literal["html_chunk"] = "html_chunk"
    html: str = Field(..., max_length=100_000)


class PageReadyMessage(BaseModel):
    """生成完成。"""
    type: Literal["page_ready"] = "page_ready"
    page_html: str = Field(..., max_length=500_000)


class GenerationFailedMessage(BaseModel):
    """生成失败。"""
    type: Literal["generation_failed"] = "generation_failed"
    reason: str = Field(..., max_length=500)
    suggestions: list[str] = Field(default_factory=list, max_length=10)


class SuccessMessage(BaseModel):
    """完整成功结果（orchestrator 返回）。"""
    type: Literal["complete"] = "complete"
    html: str = Field(..., max_length=500_000)
    steps: int = Field(..., ge=0)
    budget: float = Field(..., ge=0)


class FailedMessage(BaseModel):
    """orchestrator 判定失败。"""
    type: Literal["failed"] = "failed"
    reason: str = Field(..., max_length=500)
    steps: int = Field(..., ge=0)
    budget: float = Field(..., ge=0)


# 联合类型
ServerMessage = (
    ThinkingMessage | ThinkingStreamMessage | HeartbeatMessage |
    ToolResultMessage | HtmlChunkMessage | PageReadyMessage |
    GenerationFailedMessage | SuccessMessage | FailedMessage
)


# ═══════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════

def parse_client_message(data: dict) -> ClientMessage:
    """安全解析客户端消息——比 receive_json() 多一层 Pydantic 校验。"""
    msg_type = data.get("type", "generate")
    if msg_type == "cancel":
        return CancelRequest(**data)
    elif msg_type == "ping":
        return PingRequest(**data)
    else:
        return GenerateRequest(**data)
