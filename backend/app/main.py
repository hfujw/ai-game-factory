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
async def list_events():
    """返回知识库事件列表——前端用做推荐chips。"""
    events = get_all_events()
    return {
        "events": [
            {"name": e["event"], "keywords": e.get("keywords", [])[:3]}
            for e in events
        ],
        "total": len(events),
    }


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
            await ws_manager.send_failed(session_id, "请输入一个计算机历史事件", [])
            return

        # 通知前端开始
        await ws_manager.send_progress(session_id, "system", "running", f"收到事件：「{user_input}」")

        # 创建初始状态
        state = initial_state(user_input)

        # 运行 LangGraph 工作流
        # 使用 astream_events 获取每个节点执行的事件
        final_state = None
        prev_node = None
        prev_node_output = {}

        AGENT_NAMES = {
            "planner": "策划Agent", "crawler": "爬虫Agent", "writer": "文案Agent",
            "artist_pre": "美术设计Agent", "coder": "程序Agent", "reviewer": "审查Agent",
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

                    # 推送 agent_log（决策理由可见化）
                    agent_logs = output.get("agent_logs", [])
                    if agent_logs:
                        last_log = agent_logs[-1]
                        await ws_manager.send_json(session_id, {
                            "type": "agent_log",
                            "agent": node_name,
                            "action": last_log.get("action", ""),
                            "detail": last_log.get("detail", ""),
                        })

                    prev_node = node_name
                    prev_node_output = output

                    # 保存最终状态
                    if isinstance(output, dict) and "status" in output:
                        final_state = output

        # 如果没有通过事件拿到最终状态，直接 run
        if final_state is None:
            final_state = await asyncio.to_thread(workflow.invoke, state)

        # 推送花费
        cost = get_cost_summary()
        logger.info(f"生成完成，本次花费: ¥{cost['estimated_cost_rmb']} ({cost['calls']}次LLM调用)")

        # 推送结果
        if final_state.get("status") == "success":
            await ws_manager.send_game_ready(session_id, final_state.get("styled_code", ""))
        else:
            await ws_manager.send_failed(
                session_id,
                final_state.get("error_message", "生成失败"),
                final_state.get("suggestions", []),
            )

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await ws_manager.send_failed(session_id, f"系统错误: {str(e)}", [])
    finally:
        await ws_manager.disconnect(session_id)
