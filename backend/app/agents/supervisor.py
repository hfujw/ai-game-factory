"""Supervisor —— 消息总线驱动的编排器。

用 MessageBus 替代 if-elif 分发。Agent 通过总线收任务、返回结果。
orchestrator 仍正常工作——Supervisor 是并行通路，Phase 4 验证用。
"""

import asyncio
import logging
from app.agents.message_bus import MessageBus
from app.agents.researcher_agent import ResearcherAgent
from app.agents.designer_agent import DesignerAgent
from app.agents.render_agent import RenderAgent
from app.tools.verify import tool_verify

logger = logging.getLogger(__name__)


# 工具 → Agent 执行函数映射（替代 if-elif 链）
TOOL_HANDLERS = {
    "search":    lambda ctx, bus: ResearcherAgent().run(
        topic=ctx.get("user_input", ""),
        existing_material=ctx.get("material", []),
        session_records=ctx.get("cost_records"),
    ),
    "design":    lambda ctx, bus: DesignerAgent().run(
        ctx.get("material", []), ctx.get("user_input", ""),
        push=ctx.get("_push"), session_records=ctx.get("cost_records"),
    ),
    "compose":   lambda ctx, bus: DesignerAgent().run(
        ctx.get("material", []), ctx.get("user_input", ""),
        push=ctx.get("_push"), session_records=ctx.get("cost_records"),
    ),
    "render":    lambda ctx, bus: RenderAgent().run(
        ctx.get("design") or {}, ctx.get("content") or {},
        push=ctx.get("_push"), session_records=ctx.get("cost_records"),
    ),
    "verify":    lambda ctx, bus: tool_verify(
        ctx.get("html", ""), ctx.get("content") or {},
    ),
}


async def run_via_bus(ctx: dict, tool_name: str) -> dict:
    """用消息总线调用工具——orchestrator 的 _execute_tool 替代实现。

    跟原来的 if-elif 功能一样，但通过 MessageBus 分发。
    方便未来 Agent 之间直接通信。
    """
    bus = MessageBus()
    bus.register(tool_name)

    handler = TOOL_HANDLERS.get(tool_name)
    if handler is None:
        return {"error": f"未知工具: {tool_name}"}

    # 通过总线发任务（当前阶段同步执行，Phase 5 改异步）
    task = asyncio.create_task(_execute_handler(tool_name, handler(ctx, None), bus))
    result = await task
    return result


async def _execute_handler(name: str, coro, bus: MessageBus) -> dict:
    """执行 Agent 处理函数，返回结果。"""
    try:
        result = await coro
        logger.debug("Supervisor=tool_done | tool=%s", name)
        return result
    except Exception as e:
        logger.error("Supervisor=tool_failed | tool=%s | error=%s", name, e)
        return {"error": str(e)}
