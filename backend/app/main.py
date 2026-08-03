"""AI 游戏工坊 — FastAPI 入口。

WebSocket 端点：/ws/generate
- 用户输入历史事件 → 触发 LangGraph Agent Pipeline → 实时推送进度 → 返回游戏代码
"""

import logging
import uuid
import asyncio
import json
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.graph.state import initial_state
from app.graph.workflow import build_workflow
from app.llm_client import get_cost_summary, reset_cost
from app.ws_manager import ws_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("main")

app = FastAPI(title="时光像素", version="0.1.0")

# CORS — 允许前端开发时的跨域请求（Vite dev server: localhost:5173）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 编译 LangGraph 工作流（启动时执行一次）
workflow = build_workflow()

from app.knowledge.kb import get_all_events


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "AI 游戏工坊"}


@app.get("/api/cost")
async def get_cost():
    """返回 LLM 调用花费统计。"""
    return get_cost_summary()


@app.get("/api/events")
async def list_events(category: str = None):
    """返回示例话题列表。category 可选过滤：'computer_history' / 'bagu' / 不传=全部。"""
    events = get_all_events(category=category if category else None)
    result = []
    for e in events:
        name = e.get("event", e.get("title", ""))
        difficulty = e.get("difficulty", 0)
        result.append({
            "name": name,
            "category": e.get("category", "computer_history"),
            "difficulty": difficulty,
        })
    return {"events": result, "total": len(result)}


@app.websocket("/ws/generate")
async def generate_game(websocket: WebSocket):
    """WebSocket 端点——接收用户输入，触发 Agent Pipeline，实时推送进度。"""
    session_id = str(uuid.uuid4())[:8]
    await ws_manager.connect(session_id, websocket)

    try:
        # 接收用户输入
        data = await websocket.receive_json()
        user_input = data.get("event", "").strip()

        if not user_input:
            await ws_manager.send_failed(session_id, "请输入一个主题", [])
            return

        # 通知前端开始
        await ws_manager.send_progress(session_id, "system", "running", f"收到事件：「{user_input}」")

        # 创建初始状态
        state = initial_state(user_input)

        # 运行 LangGraph 工作流
        # astream_events 推送实时进度，同时累积输出为最终状态
        prev_node = None
        prev_node_output = {}
        final_output = {}

        AGENT_NAMES = {
            "planner": "策划Agent",
            "crawler": "爬虫Agent",
            "writer": "文案Agent",
            "artist_pre": "美术设计Agent",
            "orchestrator": "协调Agent",
            "coder": "程序Agent",
            "reviewer": "审查Agent",
            "artist_post": "美术渲染Agent",
        }

        async for event in workflow.astream_events(state, version="v2"):
            kind = event.get("event")

            if kind == "on_chain_start":
                node_name = event.get("name", "")
                if node_name in AGENT_NAMES:
                    # 检测 reviewer→coder 回退
                    if node_name == "coder" and prev_node == "reviewer":
                        review_feedback = prev_node_output.get("review_feedback", "")
                        retries = prev_node_output.get("retry_count", 1)
                        await ws_manager.send_json(session_id, {
                            "type": "review_rejected",
                            "feedback": review_feedback,
                            "retry": retries,
                        })
                        await ws_manager.send_progress(
                            session_id, node_name, "running",
                            f"程序Agent 第{retries}次重试中…（审查反馈：{review_feedback[:60]}）"
                        )
                    else:
                        await ws_manager.send_progress(
                            session_id, node_name, "running",
                            f"{AGENT_NAMES.get(node_name, node_name)} 正在工作中…"
                        )

            elif kind == "on_chain_end":
                node_name = event.get("name", "")
                output = event.get("data", {}).get("output", {})
                if node_name in AGENT_NAMES:
                    # 推送完成状态 + 决策摘要
                    summary = ""
                    if node_name == "crawler":
                        verified = output.get("agent_logs", [{}])[-1].get("action", "")
                        summary = "命中验证知识库" if verified == "verified" else "DeepSeek检索"
                    elif node_name == "planner":
                        puzzle = output.get("puzzle_type", "?")
                        summary = f"选择谜题类型：{puzzle}"
                    elif node_name == "reviewer":
                        passed = output.get("review_passed", False)
                        summary = "✓ 审查通过" if passed else "✗ 审查不通过"

                    await ws_manager.send_progress(
                        session_id, node_name, "done",
                        f"{AGENT_NAMES.get(node_name, node_name)} 完成 · {summary}" if summary
                        else f"{AGENT_NAMES.get(node_name, node_name)} 完成 ✓",
                    )

                    # 推送全部 agent_log（AI 思考过程可见化）
                    agent_logs = output.get("agent_logs", [])
                    for log in agent_logs:
                        await ws_manager.send_json(session_id, {
                            "type": "agent_log",
                            "agent": log.get("agent") or node_name,
                            "action": log.get("action", ""),
                            "detail": log.get("detail", ""),
                        })

                    prev_node = node_name
                    prev_node_output = output
                    # 累积所有输出为最终状态（后面的覆盖前面的同名字段）
                    if isinstance(output, dict):
                        final_output.update(output)

        # 推送花费
        cost = get_cost_summary()
        logger.info(f"生成完成，本次花费: ¥{cost['estimated_cost_rmb']} ({cost['calls']}次LLM调用)")
        logger.info(f"final_output keys: {list(final_output.keys())} status={final_output.get('status')} styled_len={len(final_output.get('styled_code',''))}")

        # 推送结果：用 astream_events 累积的 final_output
        if final_output.get("status") == "success":
            await ws_manager.send_game_ready(session_id, final_output.get("styled_code", ""))
        else:
            await ws_manager.send_failed(
                session_id,
                final_output.get("error_message", "生成失败"),
                final_output.get("suggestions", []),
            )

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await ws_manager.send_failed(session_id, f"系统错误: {str(e)}", [])
    finally:
        await ws_manager.disconnect(session_id)
