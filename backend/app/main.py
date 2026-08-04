"""AI 游戏工坊 — FastAPI 入口。"""

import logging
from logging.handlers import RotatingFileHandler
import sys
import os

# ═══════════════════════════════════════════════════════════════
# 日志系统 — 必须在所有业务 import 之前配置，防止被 uvicorn 抢占
# ═══════════════════════════════════════════════════════════════
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

root = logging.getLogger()
root.setLevel(logging.DEBUG)
for h in list(root.handlers):
    try: h.close()
    except: pass
    root.removeHandler(h)

# 终端：INFO 及以上 → stdout
_sh = logging.StreamHandler(sys.stdout)
_sh.setLevel(logging.INFO)
_sh.setFormatter(logging.Formatter("%(asctime)s | %(name)-22s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S"))
root.addHandler(_sh)

# 文件：DEBUG 及以上 → detail.log
_fh = RotatingFileHandler(
    os.path.join(LOG_DIR, "detail.log"),
    maxBytes=5 * 1024 * 1024, backupCount=10, encoding="utf-8",
)
_fh.setLevel(logging.DEBUG)
_fh.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s"))
root.addHandler(_fh)

# 压低第三方噪音
for _n in ("uvicorn.access", "httpx", "httpcore", "openai"):
    logging.getLogger(_n).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# 业务 import
# ═══════════════════════════════════════════════════════════════
import uuid
import asyncio
import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.llm_client import get_cost_summary, reset_cost
from app.ws_manager import ws_manager

app = FastAPI(title="时光像素", version="0.1.0")

# CORS — 允许前端开发时的跨域请求（Vite dev server: localhost:5173）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    reset_cost()

    try:
        # 接收用户输入
        data = await websocket.receive_json()
        user_input = data.get("event", "").strip()

        if not user_input:
            await ws_manager.send_failed(session_id, "请输入一个主题", [])
            return

        # 通知前端开始
        await ws_manager.send_progress(session_id, "system", "running", f"收到事件：「{user_input}」")
        print(f"\n[时光像素] 新请求 | {session_id} | {user_input}", flush=True)

        # T+0 立即推第一条日志，不等 Agent 启动
        await ws_manager.send_json(session_id, {
            "type": "thinking",
            "step": 0,
            "thought": f"收到主题「{user_input}」，准备策展...",
            "tool": "thinking",
            "budget": 0,
        })

        # 运行编排Agent
        from app.agents.orchestrator import orchestrator_node

        async def push(msg: dict):
            """实时推送到前端。"""
            if msg.get("type") == "thinking":
                await ws_manager.send_json(session_id, {
                    "type": "thinking", "step": msg["step"],
                    "thought": msg["thought"], "tool": msg["tool"],
                    "budget": msg["budget"],
                })
            elif msg.get("type") == "tool_result":
                await ws_manager.send_json(session_id, {
                    "type": "tool_result", "step": msg["step"],
                    "tool": msg["tool"], "summary": msg["summary"],
                    "budget": msg["budget"],
                })
            elif msg.get("type") == "complete":
                await ws_manager.send_game_ready(session_id, msg["html"])
            elif msg.get("type") == "failed":
                await ws_manager.send_failed(session_id, msg["reason"], [])

        result = await orchestrator_node({"user_input": user_input, "_push": push})

        cost = get_cost_summary()
        print(f"[时光像素] 生成结束 | {session_id} | status={result.get('status')} | "
              f"steps={result.get('steps')} | 花费=¥{cost['estimated_cost_rmb']} | "
              f"LLM调用={cost['calls']}次", flush=True)

        if result.get("status") != "success":
            await ws_manager.send_failed(
                session_id,
                f"这个主题的素材不够清晰，AI 尝试了 {result.get('steps', 0)} 步仍无法绘出完整的故事。换一个信息更充分的主题试试。",
                [],
            )

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.exception("生成流程异常")
        try:
            await ws_manager.send_failed(session_id, f"系统错误: {str(e)}", [])
        except Exception:
            pass
    finally:
        await ws_manager.disconnect(session_id)
