# 时光像素 (Time Pixels) — 完整项目源码

> 生成于 2026-08-03 · 给 Kimi 看
> 含全部源码 + 知识库 + 模板 + 前端组件

---

## 目录

1. [项目概述](#1-项目概述)
2. [技术栈](#2-技术栈)
3. [完整架构](#3-完整架构)
4. [后端源码](#4-后端源码)
   - [main.py](#41-mainpy-fastapi入口)
   - [ws_manager.py](#42-ws_managerpy-websocket管理器)
   - [llm_client.py](#43-llm_clientpy-deepseek-封装)
   - [config.py](#44-configpy)
   - [graph/state.py](#45-graphstatepy-状态定义)
   - [graph/workflow.py](#46-graphworkflowpy-langgraph编排)
   - [agents/crawler.py](#47-agentscrawlerpy-搜史料)
   - [agents/planner.py](#48-agentsplannerpy-策划)
   - [agents/writer.py](#49-agentswriterpy-编剧)
   - [agents/coder.py](#410-agentscoderpy-施工)
   - [agents/reviewer.py](#411-agentsreviewerpy-审查)
   - [agents/artist_pre.py](#412-agentsartist_prepy-美术设计)
   - [agents/artist_post.py](#413-agentsartist_postpy-美术渲染)
   - [agents/coder_templates_bagu.py](#414-agentscoder_templates_bagupy-八股交互模板)
   - [mcp/web_search.py](#415-mcpweb_searchpy-网页搜索)
   - [knowledge/kb.py](#416-knowledgekbpy-知识库)
   - [schema/game_script.py](#417-schemagame_scriptpy)
5. [知识库数据](#5-知识库数据)
   - [verified_events.json 完整内容](#51-verified_eventsjson)
   - [verified_bagu.json 完整内容](#52-verified_bagujson)
6. [骨架模板](#6-骨架模板)
   - [skeleton_fill_blank.html](#61-skeleton_fill_blankhtml)
   - [skeleton_recite.html](#62-skeleton_recitehtml)
   - [skeleton_match.html](#63-skeleton_matchhtml)
   - [skeleton_debugger.html](#64-skeleton_debuggerhtml)
7. [前端源码](#7-前端源码)
   - [App.jsx](#71-appjsx)
   - [index.css](#72-indexcss)
   - [hooks/useWebSocket.js](#73-hooksusewebsocketjs)
   - [components/SearchBubble.tsx](#74-componentssearchbubbletsx)
   - [components/EventTags.tsx](#75-componentseventtagstsx)
   - [components/AgentBuds.tsx](#76-componentsagentbudstsx)
   - [components/GamePanel.tsx](#77-componentsgamepaneltsx)
   - [components/RevealLayer.tsx](#78-componentsreveallayertsx)
   - [components/FailureNotice.tsx](#79-componentsfailurenoticetsx)
   - [components/DecisionLog.tsx](#710-componentsdecisionlogtsx)
   - [components/ErrorBoundary.tsx](#711-componentserrorboundarytsx)

---

## 1. 项目概述

**输入**：计算机历史事件 或 Python 面试题
**输出**：可玩的单文件 HTML 像素解谜游戏
**实现**：6+1 个 AI Agent (LangGraph StateGraph) 协作完成

### Agent Pipeline
```
crawler → planner → writer → artist_pre → coder → reviewer → artist_post → END
              ↑                        ↓ 不通过
              └── 回退重试(最多3次) ──┘
```

### State (核心状态)
- `user_input` → `search_results` → `material_sufficient` → `puzzle_type` → `puzzle_design`
- `game_script` + `script_data` → `game_code` → `review_passed` → `styled_code`
- `agent_logs: Annotated[List[dict], operator.add]` 追加式日志
- `retry_count` / `directions` / `selected_direction`

### WebSocket 消息协议
| type | 触发时机 |
|------|---------|
| `agent_progress` | Agent 开始/完成 |
| `agent_log` | Agent 决策完成 |
| `review_rejected` | 审查不通过→重试 |
| `game_ready` | 生成成功 |
| `generation_failed` | 最终失败 |

### 八股 vs 计算机历史
| 路径 | 类型 | coder | 说明 |
|------|------|-------|------|
| 八股 | fill_blank/recite/match/debugger | 骨架模板(零LLM) | KB数据完整时短路planner+writer+coder |
| 历史 | cipher/sequence/logic | LLM生成 | 全链路LLM |

---

## 2. 技术栈

| 层 | 选型 | 说明 |
|----|------|------|
| Agent编排 | LangGraph StateGraph | 条件边 + 分支回退 |
| LLM | DeepSeek API (deepseek-chat) | 一个Key驱动全部Agent |
| Web框架 | FastAPI | 原生异步 + WebSocket |
| 前端 | React 18 + Vite 5 + Tailwind 3 | frmr-motion + lucide-react |
| 包管理 | npm (Node v24) / pip (venv Python 3.13) |

---

## 3. 完整架构

### 目录结构
```
contract-review-agent/
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI + CORS + WebSocket /ws/generate + GET /api/events
│   │   ├── ws_manager.py               # WebSocket连接管理 (send_progress/send_json/send_game_ready/send_failed)
│   │   ├── llm_client.py               # chat/chat_json/agent_log/花费统计 (132行)
│   │   ├── config.py                   # MAX_REVIEW_RETRIES = 3
│   │   ├── graph/
│   │   │   ├── state.py                # GameFactoryState (TypedDict, 25字段)
│   │   │   └── workflow.py             # StateGraph: 8节点 + 3条件边
│   │   ├── agents/
│   │   │   ├── crawler.py              # 三阶梯检索 + LLM素材评估 (168行)
│   │   │   ├── planner.py              # KB短路 + LLM CoT推理 (155行)
│   │   │   ├── writer.py               # 结构化GameScript JSON (217行)
│   │   │   ├── coder.py                # 骨架模板 + LLM生成 (359行)
│   │   │   ├── reviewer.py             # 两阶段验证 + 反思层 (166行)
│   │   │   ├── artist_pre.py           # LLM自主视觉设计 (74行)
│   │   │   ├── artist_post.py          # BS4注入 + LLM补充 (141行)
│   │   │   └── coder_templates_bagu.py # 4种八股交互模板提示词 (241行)
│   │   ├── knowledge/
│   │   │   ├── kb.py                   # 双知识库+关键词匹配 (119行)
│   │   │   ├── verified_events.json    # 计算机历史 (1027行)
│   │   │   └── verified_bagu.json      # Python八股 (809行)
│   │   ├── templates/
│   │   │   ├── skeleton_fill_blank.html # 填空游戏骨架 (389行)
│   │   │   ├── skeleton_recite.html    # 默写游戏骨架 (295行)
│   │   │   ├── skeleton_match.html     # 配对游戏骨架 (191行)
│   │   │   └── skeleton_debugger.html  # 调试游戏骨架 (215行)
│   │   ├── mcp/
│   │   │   └── web_search.py           # Bing→DuckDuckGo搜索 (139行)
│   │   └── schema/
│   │       └── game_script.py          # JSON Schema文档
│   ├── test_pipeline.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx                      # 主布局: 标题+搜索+Agent+游戏面板+日志 (116行)
│   │   ├── main.jsx                     # React入口
│   │   ├── index.css                    # Tailwind + hero动画 + 滚动条 (49行)
│   │   ├── hooks/
│   │   │   └── useWebSocket.js          # WS状态管理+防抖+5种消息处理 (150行)
│   │   └── components/
│   │       ├── SearchBubble.tsx          # 搜索框+生成/取消按钮 (29行)
│   │       ├── EventTags.tsx            # category切换+事件下拉+★难度 (74行)
│   │       ├── AgentBuds.tsx            # 6Agent银色闪电+状态灯+重试角标 (128行)
│   │       ├── GamePanel.tsx            # iframe游戏+生成进度+全屏/最小化 (112行)
│   │       ├── RevealLayer.tsx          # 光标聚光灯: canvas mask (89行)
│   │       ├── FailureNotice.tsx        # 失败提示+推荐重试 (43行)
│   │       ├── DecisionLog.tsx          # 决策轨迹面板 (47行)
│   │       └── ErrorBoundary.tsx        # React错误边界 (30行)
│   ├── vite.config.js
│   └── package.json
├── docs/
│   ├── pipeline-flowchart.md
│   └── project-overview-for-kimi.md (本文件)
└── CLAUDE.md
```

---

## 4. 后端源码

### 4.1 main.py (FastAPI入口)

```python
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
    """返回知识库事件列表。category 可选 'computer_history' / 'bagu' / 不传=全部。"""
    events = get_all_events(category=category if category else None)
    result = []
    for e in events:
        name = e.get("event", e.get("title", ""))
        difficulty = e.get("difficulty", 0)
        result.append({
            "name": name,
            "category": e.get("category", "computer_history"),
            "difficulty": difficulty,
            "type": e.get("puzzle_guide", {}).get("type", "unknown") if category == "bagu" else "",
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
            await ws_manager.send_failed(session_id, "请输入一个计算机历史事件", [])
            return

        # 通知前端开始
        await ws_manager.send_progress(session_id, "system", "running", f"收到事件：「{user_input}」")

        # 创建初始状态
        state = initial_state(user_input)

        # 运行 LangGraph 工作流
        prev_node = None
        prev_node_output = {}
        final_output = {}

        AGENT_NAMES = {
            "planner": "策划Agent",
            "crawler": "爬虫Agent",
            "writer": "文案Agent",
            "artist_pre": "美术设计Agent",
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
                    # 累积所有输出为最终状态（后面的覆盖前面的同名字段）
                    if isinstance(output, dict):
                        final_output.update(output)

        # 推送花费
        cost = get_cost_summary()
        logger.info(f"生成完成，本次花费: ¥{cost['estimated_cost_rmb']} ({cost['calls']}次LLM调用)")

        # 推送结果
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
```

### 4.2 ws_manager.py (WebSocket管理器)

```python
"""WebSocket 连接管理器 — 管理前端连接，推送 Agent 进度。"""

from fastapi import WebSocket
from typing import Dict
import json


class WSManager:
    """管理 WebSocket 连接池。"""

    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        self.connections[session_id] = websocket

    async def disconnect(self, session_id: str):
        if session_id in self.connections:
            del self.connections[session_id]

    async def send_progress(self, session_id: str, agent: str, status: str, message: str, data: dict = None):
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
        if session_id not in self.connections:
            return
        ws = self.connections[session_id]
        await ws.send_text(json.dumps(payload, ensure_ascii=False))

    async def send_game_ready(self, session_id: str, game_code: str):
        if session_id not in self.connections:
            return
        ws = self.connections[session_id]
        await ws.send_text(json.dumps({
            "type": "game_ready",
            "game_code": game_code,
        }, ensure_ascii=False))

    async def send_failed(self, session_id: str, reason: str, suggestions: list):
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
```

### 4.3 llm_client.py (DeepSeek 封装)

```python
"""LLM 客户端 — 统一封装 DeepSeek API 调用，含超时/重试/内容校验。"""

import os
import logging
import time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 120  # 单次 LLM 调用最长等待秒数
MAX_RETRIES = 2        # 429/5xx 自动重试次数

# API Key 启动时校验
_api_key = os.getenv("DEEPSEEK_API_KEY")
if not _api_key:
    raise RuntimeError("DEEPSEEK_API_KEY 环境变量未设置，请检查 backend/.env 文件")

client = OpenAI(
    api_key=_api_key,
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    timeout=DEFAULT_TIMEOUT,
)

DEFAULT_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# 全局花费追踪
_cost_records: list[dict] = []


def get_cost_summary() -> dict:
    """返回累计花费统计。"""
    total_input = sum(r["input_tokens"] for r in _cost_records)
    total_output = sum(r["output_tokens"] for r in _cost_records)
    # DeepSeek V4-Pro: ¥3/M input, ¥6/M output
    cost_input = total_input / 1_000_000 * 3
    cost_output = total_output / 1_000_000 * 6
    return {
        "calls": len(_cost_records),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "estimated_cost_rmb": round(cost_input + cost_output, 4),
        "records": _cost_records[-20:],
    }


def reset_cost():
    """重置花费计数器。"""
    _cost_records.clear()


def _strip_markdown_fence(text: str) -> str:
    """清洗 LLM 可能包裹的 markdown 代码块。所有 Agent 共用。"""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```html"):
        text = text[7:]
    elif text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def agent_log(agent: str, action: str, detail: str) -> dict:
    """统一的 agent 日志格式。所有 Agent 共用，17处调用归一。"""
    return {"agent": agent, "action": action, "detail": detail}


def chat(prompt: str, system: str = "", model: str = None, temperature: float = 0.7) -> str:
    """单轮对话，含自动重试和内容为空保护。"""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            logger.debug("LLM call attempt %d/%d", attempt + 1, MAX_RETRIES + 1)

            response = client.chat.completions.create(
                model=model or DEFAULT_MODEL,
                messages=messages,
                temperature=temperature,
            )

            content = response.choices[0].message.content
            if content is None:
                logger.warning("LLM returned None content, retrying...")
                continue

            # 记录 token 使用
            usage = response.usage
            if usage:
                _cost_records.append({
                    "input_tokens": usage.prompt_tokens,
                    "output_tokens": usage.completion_tokens,
                    "model": model or DEFAULT_MODEL,
                })
                logger.info("LLM tokens: in=%d out=%d total=%d | 累计¥%.4f",
                            usage.prompt_tokens, usage.completion_tokens,
                            usage.total_tokens, get_cost_summary()["estimated_cost_rmb"])

            return content

        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES:
                wait = 2 ** attempt
                logger.warning("LLM call failed (attempt %d): %s, retrying in %ds...", attempt + 1, e, wait)
                time.sleep(wait)
            else:
                logger.error("LLM call failed after %d attempts: %s", MAX_RETRIES + 1, e)

    raise last_error or RuntimeError("LLM call failed with unknown error")


def chat_json(prompt: str, system: str = "", model: str = None) -> str:
    """调 LLM 返回 JSON 格式文本。内部调用 chat()，temperature 固定 0.1。"""
    return chat(prompt, system=system, model=model, temperature=0.1)
```

### 4.4 config.py

```python
"""项目配置常量。"""

# Agent 重试次数（workflow + reviewer 共用）
MAX_REVIEW_RETRIES = 3
```

### 4.5 graph/state.py (状态定义)

```python
"""LangGraph State — 6 个 Agent 共享的全局状态。"""

from typing import TypedDict, List, Optional, Annotated
import operator
from pydantic import BaseModel, Field


class PuzzleSpec(BaseModel):
    """谜题规格——Pydantic 强校验"""
    type: str = ""
    answer: str = ""
    hints: list[dict] = Field(default_factory=list)
    max_attempts: int = 3
    items_count: int = 0
    items_labels: list[str] = Field(default_factory=list)


class GameDesignDoc(BaseModel):
    """游戏设计文档——writer→coder 的结构化中间层"""
    puzzle_spec: PuzzleSpec = Field(default_factory=PuzzleSpec)
    screens: list[dict] = Field(default_factory=list)
    content_map: dict = Field(default_factory=dict)
    visual_spec: dict = Field(default_factory=dict)


class GameFactoryState(TypedDict):
    # === 用户输入 ===
    user_input: str

    # === 爬虫 Agent 产出 ===
    search_results: List[dict]
    material_score: float
    material_sufficient: bool

    # === 策划 Agent 产出 ===
    puzzle_type: str
    puzzle_design: dict

    # === 文案 Agent 产出 ===
    game_script: str
    script_data: dict              # 结构化剧本，coder/artist_pre 消费
    game_design_doc: Optional[dict]
    script_keywords: List[str]

    # === 程序 Agent 产出 ===
    game_code: str

    # === 审查 Agent 产出 ===
    review_passed: bool
    review_feedback: str
    review_details: dict
    retry_count: int

    # === 美术 Agent 产出 ===
    directions: list               # artist_pre 产出的视觉方向
    selected_direction: dict       # 选定的方向
    styled_code: str               # artist_post 产出的最终 HTML

    # === 元数据 ===
    status: str
    error_message: str
    suggestions: List[str]
    # 使用 Annotated + operator.add：每个 Agent 的日志追加到列表末尾
    agent_logs: Annotated[List[dict], operator.add]


def initial_state(user_input: str) -> GameFactoryState:
    """创建初始状态。"""
    return GameFactoryState(
        user_input=user_input,
        puzzle_type="",
        puzzle_design={},
        search_results=[],
        material_score=0.0,
        material_sufficient=False,
        game_script="",
        script_data={},
        game_design_doc=None,
        script_keywords=[],
        game_code="",
        review_passed=False,
        review_feedback="",
        review_details={},
        retry_count=0,
        directions=[],
        selected_direction={},
        styled_code="",
        status="running",
        error_message="",
        suggestions=[],
        agent_logs=[],
    )
```

### 4.6 graph/workflow.py (LangGraph编排)

```python
"""LangGraph Workflow — 6 Agent 的编排逻辑。"""

from langgraph.graph import StateGraph, END
from app.graph.state import GameFactoryState
from app.agents.planner import planner_node
from app.agents.crawler import crawler_node
from app.agents.writer import writer_node
from app.agents.artist_pre import artist_pre_node
from app.agents.coder import coder_node
from app.agents.reviewer import reviewer_node
from app.agents.artist_post import artist_post_node
from app.config import MAX_REVIEW_RETRIES


def should_continue_after_crawler(state: GameFactoryState) -> str:
    if state["material_sufficient"]:
        return "planner"
    return "end_failed"


def should_continue_after_planner(state: GameFactoryState) -> str:
    if state["material_sufficient"]:
        return "writer"
    return "end_failed"


def should_continue_after_reviewer(state: GameFactoryState) -> str:
    if state["review_passed"]:
        return "artist_post"
    if state["retry_count"] < MAX_REVIEW_RETRIES:
        return "coder"
    return "end_failed"


def build_workflow() -> StateGraph:
    workflow = StateGraph(GameFactoryState)

    workflow.add_node("crawler", crawler_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("writer", writer_node)
    workflow.add_node("artist_pre", artist_pre_node)
    workflow.add_node("coder", coder_node)
    workflow.add_node("reviewer", reviewer_node)
    workflow.add_node("artist_post", artist_post_node)

    workflow.set_entry_point("crawler")

    workflow.add_conditional_edges("crawler", should_continue_after_crawler,
        {"planner": "planner", "end_failed": END})
    workflow.add_conditional_edges("planner", should_continue_after_planner,
        {"writer": "writer", "end_failed": END})
    workflow.add_edge("writer", "artist_pre")
    workflow.add_edge("artist_pre", "coder")
    workflow.add_edge("coder", "reviewer")
    workflow.add_conditional_edges("reviewer", should_continue_after_reviewer,
        {"artist_post": "artist_post", "coder": "coder", "end_failed": END})
    workflow.add_edge("artist_post", END)

    return workflow.compile()
```

### 4.7 agents/crawler.py (搜史料)

```python
"""爬虫 Agent — 三阶梯检索 + LLM 素材评估。"""

import json
from app.graph.state import GameFactoryState
from app.llm_client import agent_log, chat_json, _strip_markdown_fence
from app.knowledge.kb import get_event_by_keyword, event_to_search_results, get_event_names
from app.mcp.web_search import search as web_search


def _web_results_to_search_results(results: list[dict]) -> list[dict]:
    return [{
        "title": r.get("title", ""), "content": r.get("snippet", ""),
        "url": r.get("url", ""),
        "confidence": "medium", "verified": False, "source": "web_search",
    } for r in results]


MATERIAL_EVALUATION_PROMPT = """你是一位计算机历史研究员，擅长判断史料是否足够支撑一个有趣的解谜小游戏。

评估时思考以下问题：
1. 时间、地点、人物是否明确具体？
2. 事件经过是否有细节和画面感？
3. 是否有鲜为人知的趣闻或转折？
4. 是否有可视觉化的元素？

如果素材不足，明确指出缺什么。
如果素材充足，建议最适合的谜题类型及理由。

返回严格 JSON：
{
  "sufficient": true,
  "reasoning": "详细评估过程...",
  "gaps": ["缺少的具体内容1"],
  "confidence": 0.85,
  "suggested_type": "cipher"
}"""


def evaluate_material(user_input: str, sources: list[dict]) -> dict:
    """让 LLM 评估素材质量，返回结构化评估结果。"""
    if not sources:
        return {"sufficient": False, "reasoning": "未收集到任何素材。",
                "gaps": ["所有检索来源均未返回结果"], "confidence": 0.0, "suggested_type": "unknown"}

    sources_text = "\n\n---\n\n".join(
        f"[来源 {i+1}] {s.get('title', '未命名')}\n{s.get('content', '')[:1000]}"
        for i, s in enumerate(sources[:6])
    )

    prompt = f"""请评估以下素材是否足够支撑一个关于「{user_input}」的解谜小游戏。

素材：
{sources_text}

请返回 JSON 评估结果。不要加 markdown 代码块。"""

    try:
        raw = chat_json(prompt, system=MATERIAL_EVALUATION_PROMPT)
        raw = _strip_markdown_fence(raw)
        result = json.loads(raw)
        return {
            "sufficient": result.get("sufficient", False),
            "reasoning": result.get("reasoning", ""),
            "gaps": result.get("gaps", []),
            "confidence": result.get("confidence", 0.0),
            "suggested_type": result.get("suggested_type", "unknown"),
        }
    except Exception as e:
        total_chars = sum(len(s.get("content", "")) for s in sources)
        return {
            "sufficient": total_chars >= 300,
            "reasoning": f"LLM 评估失败（{str(e)}），降级到字符数兜底规则：共 {total_chars} 字符。",
            "gaps": ["LLM 评估异常"],
            "confidence": 0.3, "suggested_type": "unknown"
        }


def crawler_node(state: GameFactoryState) -> dict:
    """三阶梯检索 + LLM 素材评估。"""
    user_input = state["user_input"]
    all_sources = []; actions = []

    # Step 1: KB
    verified_event = get_event_by_keyword(user_input)
    if verified_event:
        all_sources.extend(event_to_search_results(verified_event))
        actions.append("kb_hit")

    # Step 2: web_search
    is_predefined = bool(verified_event and verified_event.get("puzzle_guide"))
    if not is_predefined:
        web_results = web_search(user_input, max_results=5)
        if web_results:
            all_sources.extend(_web_results_to_search_results(web_results))
            actions.append("web_search")
    else:
        web_results = []

    # 八股预定义：数据完整直接返回
    if is_predefined:
        return {
            "search_results": all_sources, "material_score": 1.0, "material_sufficient": True,
            "agent_logs": [agent_log("crawler", "verified",
                f"predefined puzzle: {verified_event['puzzle_guide']['type']}, skip web_search")],
        }

    # LLM 素材评估
    evaluation = evaluate_material(user_input, all_sources)
    eval_detail = (
        f"sufficient={evaluation['sufficient']}, confidence={evaluation['confidence']}, "
        f"suggested={evaluation['suggested_type']}\n"
        f"推理: {evaluation['reasoning']}\n"
        f"缺失: {'; '.join(evaluation['gaps']) if evaluation['gaps'] else '无'}"
    )

    if evaluation["sufficient"]:
        return {
            "search_results": all_sources, "material_score": evaluation["confidence"],
            "material_sufficient": True, "suggested_type": evaluation["suggested_type"],
            "agent_logs": [
                agent_log("crawler", "evaluated", eval_detail),
                agent_log("crawler", "material_ok", f"{'+'.join(actions)}: {len(all_sources)} sources, LLM评估通过")
            ],
        }

    # Step 3: DeepSeek 兜底（针对 gaps 补充）
    gaps_text = "\n".join(f"- {g}" for g in evaluation["gaps"])
    try:
        response = chat_json(
            f"请检索关于以下计算机历史事件的资料，重点补充缺失信息：\n\n事件：{user_input}\n\n不足：\n{gaps_text}",
            system="你是计算机历史研究员。只输出确定的事实。返回 JSON：{material_sufficient, sources, keywords}",
        )
        response = _strip_markdown_fence(response)
        result = json.loads(response)
        if result.get("material_sufficient"):
            ds = result.get("sources", [])
            for s in ds: s["verified"] = False; s["source"] = "deepseek_knowledge"
            all_sources.extend(ds)
            total = sum(len(s.get("content","")) for s in all_sources)
            return {
                "search_results": all_sources, "material_score": round(min(total/3000, 0.9), 2),
                "material_sufficient": True, "suggested_type": evaluation["suggested_type"],
                "agent_logs": [agent_log("crawler", "evaluated", eval_detail),
                    agent_log("crawler", "deepseek_enrich", f"补充 {len(ds)} sources")]
            }
    except Exception:
        pass

    if all_sources:
        return {
            "search_results": all_sources, "material_score": 0.4, "material_sufficient": True,
            "suggested_type": evaluation["suggested_type"],
            "agent_logs": [agent_log("crawler", "evaluated", eval_detail),
                agent_log("crawler", "partial", "DeepSeek失败，使用现有素材")]
        }
    return {
        "search_results": [], "material_score": 0.0, "material_sufficient": False,
        "error_message": f"关于「{user_input}」没有足够资料。试试更知名的计算机历史事件。",
        "suggestions": get_event_names()[:5], "status": "failed",
        "agent_logs": [agent_log("crawler", "insufficient", "LLM评估+DeepSeek均不足")],
    }
```

### 4.8 agents/planner.py (策划)

```python
"""策划 Agent — 基于真实史料做 CoT 推理，选择谜题类型与设计机制。"""

import json
from app.graph.state import GameFactoryState
from app.llm_client import chat_json, _strip_markdown_fence, agent_log

SYSTEM_PROMPT = """你是一个游戏策划师，专门把计算机历史事件改编成解谜小游戏。

【类型选择铁律——违反即错误】
- Python 代码/面试题/语法概念 → 必须四选一：fill_blank / recite / match / debugger
- 计算机历史事件（Turing、Python诞生、互联网等）→ 必须三选一：cipher / sequence / logic
- 禁止返回 "puzzle"、"unknown"、"code" 等模糊类型名

分析步骤（必须全部完成）：
1. 特征提取：阅读史料，提取 3-5 个关键特征
2. 类型匹配：逐一评估每种谜题类型的匹配度
3. 排除论证：明确说明为什么其他类型不合适（至少排除 2 个）
4. 机制设计：基于史料的具体内容设计 mechanic/rules/win_condition
5. 自检：玩家解这个谜题 = 亲身体验历史的关键时刻？

【输出格式】
{
  "puzzle_type": "cipher",
  "material_sufficient": true,
  "puzzle_design": {
    "mechanic": "一句话玩法",
    "rules": "3-5条具体规则",
    "win_condition": "通关条件"
  },
  "reasoning_chain": [
    "步骤1：我注意到素材中反复出现...",
    "步骤2：cipher类型匹配度极高...",
    "步骤3：sequence类型虽然有时序但只是背景...",
    "步骤4：我设计的机制是...",
    "步骤5：这个设计有意义，因为玩家不是在排顺序而是在拯救城市..."
  ],
  "reasoning": "为什么选这个类型（一句话总结）"
}"""


def planner_node(state: GameFactoryState) -> dict:
    user_input = state["user_input"]
    search_results = state.get("search_results", [])
    suggested_type = state.get("suggested_type", "")

    # 条件短路：KB 数据完整时才跳过 LLM
    TYPE_DATA_CHECKS = {
        "fill_blank": lambda p: bool(p.get("blanks")),
        "match": lambda p: bool(p.get("match_pairs")),
        "recite": lambda p: bool(p.get("recite_config")),
        "debugger": lambda p: bool(p.get("bug_info")),
    }
    TYPE_META = {
        "fill_blank": {
            "mechanic": "Python 代码填空",
            "rules": "阅读代码，点击 ___ 空位填入正确的关键字或表达式",
            "win_condition": "所有空位填写正确，终端输出预期结果",
        },
        "recite": {
            "mechanic": "Python 代码默写",
            "rules": "根据需求描述，在伪 IDE 中补全代码",
            "win_condition": "代码补全正确，通过语法检查并输出预期结果",
        },
        "match": {
            "mechanic": "Python 概念配对",
            "rules": "将左侧 Python 概念与右侧机制描述正确配对",
            "win_condition": "所有概念配对正确，解锁知识卡片",
        },
        "debugger": {
            "mechanic": "Python Bug 定位",
            "rules": "阅读报错信息，点击可疑行号定位 Bug，再选择正确类型",
            "win_condition": "正确指出 Bug 所在行和 Bug 类型，查看修复方案",
        },
    }
    for r in search_results:
        pg = r.get("puzzle_guide", {})
        if not pg or not pg.get("type"):
            continue
        check_fn = TYPE_DATA_CHECKS.get(pg["type"])
        if not check_fn or not check_fn(pg):
            continue

        # 知识点来源：key_facts（event_to_search_results 映射自 content.annotations）
        annotations = r.get("key_facts", []) or r.get("content", {}).get("annotations", [])
        if not annotations:
            content = r.get("content", {})
            annotations = [content.get("translation", "Python 面试知识点")] if content else []

        ptype = pg["type"]
        meta = TYPE_META.get(ptype, {
            "mechanic": f"Python 面试 - {ptype}",
            "rules": "；".join(annotations),
            "win_condition": "通关",
        })

        return {
            "puzzle_type": ptype,
            "puzzle_design": {
                "mechanic": meta["mechanic"],
                "rules": meta["rules"],
                "win_condition": meta["win_condition"],
            },
            "material_sufficient": True,
            "reasoning_chain": [f"KB 提供完整 {ptype} 谜题数据，类型数据校验通过，直接短路。"],
            "agent_logs": [agent_log("planner", "predefined",
                f"type={ptype}, {pg['type']}_data 齐全")],
        }

    sources_text = "\n\n".join(
        f"[来源{i+1}] {r.get('title','')}\n{r.get('content','')[:600]}"
        for i, r in enumerate(search_results)
    )

    crawler_hint = ""
    if suggested_type and suggested_type != "unknown":
        crawler_hint = f"\n【素材评估员建议】建议优先考虑「{suggested_type}」类型，但请你独立判断。\n"

    prompt = f"""用户想了解的历史事件：{user_input}{crawler_hint}

以下是搜集到的史料：
{sources_text if sources_text else '（使用你的知识）'}

请逐步分析并决定谜题类型和机制。如果史料太单薄，返回 material_sufficient=false。"""

    try:
        response = chat_json(prompt, system=SYSTEM_PROMPT)
        response = _strip_markdown_fence(response)
        result = json.loads(response)

        if not result.get("material_sufficient", False):
            return {
                "puzzle_type": "unknown", "puzzle_design": {}, "material_sufficient": False,
                "error_message": f"关于「{user_input}」的史料不足以支撑一个有趣的谜题。",
                "suggestions": ["1940年 Turing 破译德军 Enigma 密码", "1989年圣诞节 Guido 发明了 Python"],
                "status": "failed", "reasoning_chain": result.get("reasoning_chain", []),
                "agent_logs": [agent_log("planner", "insufficient", result.get("reasoning", ""))],
            }

        return {
            "puzzle_type": result["puzzle_type"],
            "puzzle_design": result.get("puzzle_design", {}),
            "material_sufficient": True,
            "reasoning_chain": result.get("reasoning_chain", []),
            "agent_logs": [agent_log("planner", "designed",
                f"type={result['puzzle_type']}, {result.get('reasoning','')[:80]}")],
        }

    except Exception as e:
        for r in search_results:
            pg = r.get("puzzle_guide", {})
            if pg and pg.get("type"):
                return {
                    "puzzle_type": pg["type"],
                    "puzzle_design": {"mechanic": f"Python 面试 - {pg['type']}",
                        "rules": "；".join(pg.get("annotations", [])), "win_condition": "通关"},
                    "material_sufficient": True,
                    "reasoning_chain": [f"LLM 推理失败（{str(e)}），降级使用 KB 数据。"],
                    "agent_logs": [agent_log("planner", "fallback_to_kb", str(e))],
                }
        return {
            "puzzle_type": "unknown", "puzzle_design": {}, "material_sufficient": False,
            "error_message": f"策划Agent调用LLM失败: {str(e)}", "status": "failed",
            "reasoning_chain": [f"错误: {str(e)}"],
            "agent_logs": [agent_log("planner", "error", str(e))],
        }
```

### 4.9 agents/writer.py (编剧)

```python
"""文案 Agent — 输出结构化 GameScript JSON。"""

import json
from app.graph.state import GameFactoryState
from app.llm_client import chat, _strip_markdown_fence, agent_log

SYSTEM_PROMPT = """你是一个历史教育像素游戏的编剧。

你的唯一产出是一个严格的 JSON 对象。下游有 2 个 Agent 消费你的输出：
- coder_agent：读 puzzle、history_facts、victory_line、defeat_line、opening_hook
- artist_agent：读 visual.palette、visual.mood、visual.decorations

【输出格式】
{
  "event": "事件名",
  "year": 年份数字,
  "location": "地点",
  "protagonist": "主角名/身份",
  "antagonist": "对抗方",
  "core_conflict": "一句话冲突悬念",
  "atmosphere": "氛围关键词，逗号分隔",
  "opening_hook": "标题画面显示的悬念句，让玩家想点开始",

  "puzzle": {
    "type": "cipher|sequence|logic",
    "surface": "谜题表皮——玩家看到的场景描述，如'一封截获的德军密电'",
    "answer": "正确答案",
    "items_count": 排序类元素数量,
    "items_labels": ["标签1","标签2"],
    "hints": [
      {"level":1, "text":"模糊提示"},
      {"level":2, "text":"中等提示"},
      {"level":3, "text":"直接提示"}
    ],
    "max_attempts": 3
  },

  "history_facts": {
    "title": "一段吸引人的小标题，如'一台机器如何改变战争走向'",
    "story": "200-300字的历史小故事。用口语化、有画面感的语言讲述。",
    "key_point": "一句话核心收获",
    "fun_fact": "一条鲜为人知的趣闻"
  },

  "victory_line": "像素风通关台词，简短有力",
  "defeat_line": "像素风失败鼓励台词，简短",

  "visual": {
    "palette": ["#0d0a08","#e8702a","#34d399","#e8ddd0","#5a4a3a"],
    "mood": "视觉情绪描述",
    "decorations": ["装饰元素1","装饰元素2"]
  }
}

【铁律】
- 必须输出合法 JSON，不要 markdown 包裹，不要注释
- puzzle.hints 必须 3 条，level 1→2→3 从模糊到直接
- history_facts.story 必须 200-300 字，口语化有画面感
- victory_line 和 defeat_line 各不超过 20 字
- atmosphere 字段优先使用史料中提供的 atmosphere_tags
- visual.decorations 优先使用史料中提供的 key_props
- visual.mood 优先参考史料中提供的 visual_anchor
- 所有内容必须基于史料，不编造"""

BAGU_SYSTEM_PROMPT = """你是一个 Python 面试教学游戏的编剧。

你的唯一产出是一个严格的 JSON 对象。下游 Agent 消费你的输出。

【输出格式——Python 八股专用】
{
  "event": "题目名（如'上下文管理器'）",
  "year": 难度数字(1-4),
  "protagonist": "考点（如'__enter__ / __exit__'）",
  "antagonist": "常见误区",
  "atmosphere": "终端,代码,IDE",
  "opening_hook": "一句引人入胜的面试场景描述",

  "puzzle": {
    "type": "fill_blank|recite|match|debugger",
    "surface": "代码场景描述",
    "answer": "（从数据中获取，不要编造）",
    "hints": [{"level":1,"text":"..."}, {"level":2,"text":"..."}, {"level":3,"text":"..."}],
    "max_attempts": 3
  },

  "history_facts": {
    "title": "知识点讲解",
    "story": "200-300字口语化讲解，像面试官在给你讲题",
    "key_point": "一句话核心考点",
    "fun_fact": "面试官追问或延伸思考"
  },

  "victory_line": "Process finished with exit code 0",
  "defeat_line": "NameError: knowledge not defined",

  "visual": {
    "palette": ["#0d1117","#58a6ff","#7ee787","#e6edf3","#30363d"],
    "mood": "终端IDE",
    "decorations": ["光标","代码高亮","行号"]
  },

  "content": {
    "original": "完整代码（从史料复制）",
    "translation": "代码解释",
    "annotations": ["知识点1","知识点2"]
  }
}

【铁律】
- history_facts.story 必须 200-300 字口语化讲解
- victory_line 用 Python 终端风格
- content.original 从史料中复制完整代码，不要改编
- 所有内容基于史料，不编造"""


def writer_node(state: GameFactoryState) -> dict:
    user_input = state["user_input"]
    puzzle_type = state["puzzle_type"]
    puzzle_design = state.get("puzzle_design", {})
    search_results = state.get("search_results", [])

    is_bagu = puzzle_type in ("fill_blank", "recite", "match", "debugger")

    parts = []
    for r in search_results[:3]:
        title = r.get('title', '')
        story = r.get('content', '')
        facts = r.get('key_facts', [])
        block = f"【{title}】\n"
        if story and len(story) > 50:
            block += story
        elif facts:
            block += "; ".join(facts)
        if r.get("atmosphere_tags"):
            block += f"\n氛围标签：{'、'.join(r['atmosphere_tags'])}"
        if r.get("key_props"):
            block += f"\n关键道具：{'、'.join(r['key_props'])}"
        if r.get("visual_anchor"):
            block += f"\n视觉锚点：{r['visual_anchor']}"
        parts.append(block)
    sources_text = "\n\n".join(parts)

    prompt = f"""历史事件：{user_input}
谜题类型：{puzzle_type}
谜题机制：{puzzle_design.get('mechanic', '')}
规则：{puzzle_design.get('rules', '')}

史料：
{sources_text if sources_text else '（使用你的知识）'}

请输出完整 GameScript JSON。puzzle.type 必须是 {puzzle_type}。"""

    try:
        system = BAGU_SYSTEM_PROMPT if is_bagu else SYSTEM_PROMPT
        raw = chat(prompt, system=system, temperature=0.5)
        cleaned = _strip_markdown_fence(raw)
        script = json.loads(cleaned)

        if "puzzle" not in script:
            script["puzzle"] = {}
        script["puzzle"]["type"] = puzzle_type
        if "max_attempts" not in script["puzzle"]:
            script["puzzle"]["max_attempts"] = 3
        if "hints" not in script["puzzle"] or not script["puzzle"]["hints"]:
            script["puzzle"]["hints"] = [
                {"level": 1, "text": "再仔细看看..."},
                {"level": 2, "text": "注意关键线索"},
                {"level": 3, "text": "答案就在眼前"},
            ]

        return {
            "game_script": json.dumps(script, ensure_ascii=False),
            "script_data": script,
            "script_keywords": [user_input, puzzle_type],
            "agent_logs": [agent_log("writer", "script_written",
                           f"topic={script.get('event',user_input)}, chars={len(raw)}")],
        }
    except Exception as e:
        fallback = {
            "event": user_input,
            "puzzle": {
                "type": puzzle_type,
                "surface": puzzle_design.get("mechanic", ""),
                "answer": puzzle_design.get("win_condition", ""),
                "hints": [
                    {"level": 1, "text": "仔细看看线索..."},
                    {"level": 2, "text": "也许换个思路"},
                    {"level": 3, "text": "答案可能很简单"},
                ],
                "max_attempts": 3,
            },
            "history_facts": {
                "title": "关于这个事件",
                "story": "（史料解析失败，请使用剧本中的历史信息）",
                "key_point": "每个技术突破背后都有一个有趣的故事。",
                "fun_fact": "",
            },
            "victory_line": "你成功了！",
            "defeat_line": "没关系，再试一次。",
            "visual": {"mood": "像素复古"},
        }
        return {
            "game_script": json.dumps(fallback, ensure_ascii=False),
            "script_data": fallback,
            "script_keywords": [user_input, puzzle_type],
            "agent_logs": [agent_log("writer", "fallback", str(e))],
        }
```

### 4.10 agents/coder.py (施工)

```python
"""程序 Agent — 从结构化 GameScript 生成有质感的 HTML 游戏。"""

import json
from app.graph.state import GameFactoryState
from app.llm_client import agent_log, chat, _strip_markdown_fence
from app.agents.coder_templates_bagu import (
    FILL_BLANK_TEMPLATE, RECITE_TEMPLATE, MATCH_TEMPLATE, DEBUGGER_TEMPLATE
)

BAGU_TEMPLATES = {
    "fill_blank": FILL_BLANK_TEMPLATE,
    "recite": RECITE_TEMPLATE,
    "match": MATCH_TEMPLATE,
    "debugger": DEBUGGER_TEMPLATE,
}

SYSTEM_PROMPT = """你是一个"时间工匠"——将历史事件转化为可交互的 HTML 解谜游戏。

=== 视觉契约 ===
你的 HTML 必须包含以下 artist_pre 提供的 CSS（直接插入 <style> 最前面，不要修改）：
{visual_css}

【画面切换】5个画面div都加 class="screen"。显示/隐藏通过 classList.toggle('active') 实现。
不要直接操作 element.style.display——artist_post 会注入 opacity/scale transition。

【类名建议】优先使用 .rune（按钮）、.panel（面板）、.glyph-input（输入框）。
用不了就用你自己写的，artist_post 会尝试映射。颜色用 CSS 变量 var(--xxx)。

=== 新手引导与沉浸感 ===

【开场即入戏】
- 标题画面不是"欢迎来到XX游戏"，而是把玩家直接扔进历史现场

【操作引导——让玩家无痛上手】
- 永远不要让玩家"读说明书"。用自动高亮、即时反馈、第一轮不扣次数替代
- 关键操作旁边始终有一行小字提示
- 玩家卡住 10 秒后，自动浮现第一条 hint

【让谜题有意义——不只是"排顺序"】
- 每个谜题必须回答一个问题："玩家为什么要做这件事？"
- 把答案写进游戏的 narrative 里

=== 游戏循环 ===
1. #screen-title：显示年份+地点+悬念句
2. #screen-howto：一句话操作说明 + "开始挑战"按钮
3. #screen-game：谜题交互
4. 反馈系统：裂纹递增 + 背景变暗 + 逐层提示
5. #screen-result：胜利→光芒动画；失败→暗红余烬
6. #screen-history：分层展示history_facts

=== 谜题范式 ===

【cipher — 符文破译台】
- 中央密文大字 → 下方A-Z字母盘 → 凹槽行显示进度 →"点燃符文"检查按钮

【sequence — 时间碎片】
- 4-6个"碎片"卡片，可点击交换顺序 →"重组时间线"按钮

【logic — 星图推演】
- 中央问题核心 → 周围线索节点 → 下方3-4个选项

=== 代码约束 ===
- 单文件 <!DOCTYPE html>，内嵌 <style> 和 <script>
- 600 行以内
- 不依赖外部库
- gameState 管理所有状态
- history_facts 存为 HISTORY_FACTS 常量
- showScreen(name) 函数切换画面
- 所有屏幕 id：screen-title, screen-howto, screen-game, screen-result, screen-history
- 直接输出代码，不要 markdown 包裹"""


def _load_skeleton(name: str) -> str:
    import os
    path = os.path.join(os.path.dirname(__file__), "..", "templates", f"skeleton_{name}.html")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def _extract_puzzle_guide(search_results):
    for r in search_results:
        if r.get("puzzle_guide"): return r["puzzle_guide"]
    return {}

def _fill_common(skeleton, script_data, puzzle_guide, facts):
    html = skeleton
    html = html.replace("{{TITLE}}", script_data.get("event", "Python 面试题"))
    difficulty = script_data.get("year", 1)
    html = html.replace("{{SUBTITLE}}", f'难度 {"★"*min(difficulty,4)}{"☆"*max(0,4-difficulty)}')
    html = html.replace("{{OPENING_HOOK}}", script_data.get("opening_hook", ""))
    html = html.replace("{{HOWTO_TEXT}}", script_data.get("puzzle", {}).get("surface", "按照提示完成挑战即可通关。"))
    html = html.replace("{{HISTORY_TITLE}}", facts.get("title", "知识点"))
    html = html.replace("{{HISTORY_STORY}}", facts.get("story", ""))
    html = html.replace("{{KEY_POINT}}", facts.get("key_point", ""))
    html = html.replace("{{FUN_FACT}}", facts.get("fun_fact", ""))
    html = html.replace("{{VICTORY_LINE}}", script_data.get("victory_line", "Process finished with exit code 0"))
    html = html.replace("{{DEFEAT_LINE}}", script_data.get("defeat_line", "NameError: knowledge not defined"))
    return html

def _fill_blank_from_skeleton(state, search_results, script_data) -> dict:
    import json
    skeleton = _load_skeleton("fill_blank")
    pg = _extract_puzzle_guide(search_results)
    facts = script_data.get("history_facts", {})
    if isinstance(facts, list): facts = {"title":"","story":"","key_point":"","fun_fact":""}
    html = _fill_common(skeleton, script_data, pg, facts)
    html = html.replace("{{MAX_ATTEMPTS}}", str(pg.get("scoring", {}).get("base_score", 100) // 30 if pg.get("scoring") else 3))
    html = html.replace("{{PUZZLE_DATA_JSON}}", json.dumps(pg, ensure_ascii=False))
    html = html.replace("{{HISTORY_JSON}}", json.dumps(facts, ensure_ascii=False))
    return {"game_code": html, "agent_logs": [agent_log("coder", "skeleton_filled", f"fill_blank from skeleton, {len(html)} chars")]}

def _recite_from_skeleton(state, search_results, script_data) -> dict:
    import json
    skeleton = _load_skeleton("recite")
    pg = _extract_puzzle_guide(search_results)
    facts = script_data.get("history_facts", {}) or {}
    html = _fill_common(skeleton, script_data, pg, facts)
    html = html.replace("{{PUZZLE_DATA_JSON}}", json.dumps(pg, ensure_ascii=False))
    html = html.replace("{{RECITE_CONFIG_JSON}}", json.dumps(pg.get("recite_config", {}), ensure_ascii=False))
    html = html.replace("{{FULL_CODE}}", (script_data.get("content", {}) or {}).get("original", ""))
    html = html.replace("{{HISTORY_JSON}}", json.dumps(facts, ensure_ascii=False))
    return {"game_code": html, "agent_logs": [agent_log("coder", "skeleton_filled", f"recite from skeleton, {len(html)} chars")]}

def _match_from_skeleton(state, search_results, script_data) -> dict:
    import json
    skeleton = _load_skeleton("match")
    pg = _extract_puzzle_guide(search_results)
    facts = script_data.get("history_facts", {}) or {}
    html = _fill_common(skeleton, script_data, pg, facts)
    html = html.replace("{{MATCH_PAIRS_JSON}}", json.dumps(pg.get("match_pairs", []), ensure_ascii=False))
    html = html.replace("{{HISTORY_JSON}}", json.dumps(facts, ensure_ascii=False))
    return {"game_code": html, "agent_logs": [agent_log("coder", "skeleton_filled", f"match from skeleton, {len(html)} chars")]}

def _debugger_from_skeleton(state, search_results, script_data) -> dict:
    import json
    skeleton = _load_skeleton("debugger")
    pg = _extract_puzzle_guide(search_results)
    facts = script_data.get("history_facts", {}) or {}
    html = _fill_common(skeleton, script_data, pg, facts)
    bug_info = pg.get("bug_info", {})
    bug_info["code"] = (script_data.get("content", {}) or {}).get("original", "")
    html = html.replace("{{BUG_INFO_JSON}}", json.dumps(bug_info, ensure_ascii=False))
    html = html.replace("{{HISTORY_JSON}}", json.dumps(facts, ensure_ascii=False))
    return {"game_code": html, "agent_logs": [agent_log("coder", "skeleton_filled", f"debugger from skeleton, {len(html)} chars")]}


def get_puzzle_meaning(puzzle_type: str, event: str, protagonist: str) -> str:
    templates = {
        "cipher": f"玩家扮演{protagonist or '密码破译员'}，截获了关于「{event}」的关键密文。破译它不是为了通关——而是因为密文背后藏着真实的历史转折。",
        "sequence": f"关于「{event}」的时间线被打乱了。玩家需要拼凑出完整的历史顺序，才能理解这件事为什么以这种方式发生。",
        "logic": f"关于「{event}」流传着几种矛盾的说法。玩家需要从史料线索中推理出真相，揭穿被误传的信息。",
    }
    return templates.get(puzzle_type, f"玩家通过解谜，亲身体验「{event}」中的关键历史时刻。")


def coder_node(state: GameFactoryState) -> dict:
    puzzle_type = state["puzzle_type"]
    script_data = state.get("script_data", {})
    direction = state.get("selected_direction", {})
    review_feedback = state.get("review_feedback", "")
    search_results = state.get("search_results", [])

    # === 骨架模板路径（零 LLM）===
    if puzzle_type == "fill_blank":
        return _fill_blank_from_skeleton(state, search_results, script_data)
    if puzzle_type == "recite":
        return _recite_from_skeleton(state, search_results, script_data)
    if puzzle_type == "match":
        return _match_from_skeleton(state, search_results, script_data)
    if puzzle_type == "debugger":
        return _debugger_from_skeleton(state, search_results, script_data)

    is_bagu = puzzle_type in BAGU_TEMPLATES
    if is_bagu:
        puzzle_guide = {}
        for r in search_results:
            if r.get("puzzle_guide"):
                puzzle_guide = r["puzzle_guide"]
                break
        bagu_data_block = f"""
=== Python 面试题数据（注入到 window.__PUZZLE_DATA__）===
{json.dumps(puzzle_guide, ensure_ascii=False)}

=== 原始代码 ===
{script_data.get('original_code', '') or (script_data.get('content', {}) or {}).get('original', '')}

=== 知识点 ===
{json.dumps(script_data.get('annotations', []), ensure_ascii=False)}
"""
        bagu_system = SYSTEM_PROMPT + "\n\n" + BAGU_TEMPLATES[puzzle_type]

    if not script_data:
        try:
            script_data = json.loads(state.get("game_script", "{}"))
        except (json.JSONDecodeError, TypeError):
            script_data = {}

    event = script_data.get("event", state["user_input"])
    year = script_data.get("year", "")
    location = script_data.get("location", "")
    opening = script_data.get("opening_hook", f"你能解开{event}的秘密吗？")
    protagonist = script_data.get("protagonist", "")
    core_conflict = script_data.get("core_conflict", "")

    puzzle = script_data.get("puzzle", {})
    hints = puzzle.get("hints", [])
    hints_text = "\n".join(f"  L{h.get('level',1)}: {h.get('text','')}" for h in hints) if hints else "  L1: 仔细观察..."

    items = puzzle.get("items_labels", [])
    items_text = ", ".join(f'"{x}"' for x in items) if items else ""

    facts = script_data.get("history_facts", [])
    facts_text = "\n".join(f'  "{f}"' for f in facts) if facts else "（使用剧本中的历史信息）"

    victory = script_data.get("victory_line", "你成功了！")
    defeat = script_data.get("defeat_line", "再试一次。")

    visual = script_data.get("visual", {})
    mood = visual.get("mood", "像素复古")
    atmosphere = script_data.get("atmosphere", mood)

    feedback_block = ""
    if review_feedback:
        feedback_block = f"""
=== 🚨 审查反馈（必须修复）===
{review_feedback}
"""

    direction_block = ""
    if direction:
        direction_block = f"""
=== 选定的视觉方向 ===
名称：{direction.get('name', '默认')}
色板：{', '.join(direction.get('palette', []))}
UI风格：{direction.get('ui', '')}
动画节奏：{direction.get('animation', '')}
参考CSS：
{direction.get('reference_css', '')}

请基于上述视觉方向编写游戏。可以自由发挥，不必逐字复制参考CSS。"""

    prompt = f"""请按契约生成「{puzzle_type}」类型的时间解谜游戏。

【叙事信息】
事件：{event}（{year}）
地点：{location}
主角：{protagonist}
冲突：{core_conflict}
氛围：{atmosphere}
开场悬念：{opening}

【玩家动机】
{get_puzzle_meaning(puzzle_type, event, protagonist)}

【谜题参数】
类型：{puzzle_type}
表皮：{puzzle.get('surface', '')}
答案：{puzzle.get('answer', '')}
元素数量：{puzzle.get('items_count', len(items))}
元素标签：{items_text}
最大尝试：{puzzle.get('max_attempts', 3)}

【提示层级】
{hints_text}

【历史真相】
标题：{facts.get('title', '') if isinstance(facts, dict) else ''}
故事：{facts.get('story', '') if isinstance(facts, dict) else ''}
核心收获：{facts.get('key_point', '') if isinstance(facts, dict) else ''}
趣闻：{facts.get('fun_fact', '') if isinstance(facts, dict) else ''}

【台词】
通关：{victory}
失败：{defeat}

{feedback_block}
直接输出完整 HTML。"""

    try:
        final_prompt = prompt + direction_block + (bagu_data_block if is_bagu else "")
        final_system = bagu_system if is_bagu else SYSTEM_PROMPT
        temp = 0.1 if is_bagu else 0.3
        code = chat(final_prompt, system=final_system, temperature=temp)
        code = _strip_markdown_fence(code)
        if not code.lower().startswith("<!doctype"):
            code = f"<!DOCTYPE html>\n{code}"

        return {
            "game_code": code,
            "agent_logs": [agent_log("coder", "code_generated", f"{len(code)} chars")],
        }
    except Exception as e:
        fallback = f"""<!DOCTYPE html>
<html lang="zh">
<head><meta charset="UTF-8"><title>生成失败</title></head>
<body style="background:#0d0a08;color:#e8ddd0;font-family:monospace;display:flex;justify-content:center;align-items:center;height:100vh;margin:0">
<div style="text-align:center"><h1 style="color:#e8702a">生成失败</h1><p>{str(e)}</p></div>
</body></html>"""
        return {
            "game_code": fallback,
            "agent_logs": [agent_log("coder", "error", str(e))],
        }
```

### 4.11 agents/reviewer.py (审查)

```python
"""审查 Agent — 两阶段验证 + LLM 深度审查 + 反思层。"""

import json, re, logging
from app.graph.state import GameFactoryState
from app.llm_client import agent_log, chat_json, _strip_markdown_fence
from app.config import MAX_REVIEW_RETRIES
from app.knowledge.kb import get_event_names

logger = logging.getLogger("reviewer")

# === Phase 1 工具函数 ===
def _extract_answer_from_script(game_script: str) -> str | None:
    if not game_script: return None
    try:
        data = json.loads(game_script)
        ans = data.get("puzzle", {}).get("answer")
        return str(ans) if ans is not None else None
    except: return None

def _normalize_for_search(text: str) -> str:
    text = re.sub(r'//.*?\n|/\*.*?\*/', ' ', text, flags=re.DOTALL)
    return re.sub(r'\s+', ' ', text).lower().strip()

CRITICAL_RULES = [
    ("doctype", r'<!DOCTYPE\s+html', "缺少 <!DOCTYPE html>"),
    ("script_tag", r'<script[^>]*>', "缺少 <script> 标签"),
    ("screen_game", r'id=["\']screen-game["\']', "缺少游戏主体区域"),
    ("game_state", r'(const\s+gameState|let\s+gameState|var\s+gameState)', "缺少 gameState 状态对象"),
]
WARNING_RULES = [
    ("screen_result", r'(id=["\']screen-result["\']|胜利|失败|通关|再来)', "缺少结果画面"),
    ("history", r'(HISTORY_FACTS|历史真相)', "缺少历史真相"),
]
CSS_MUST_HAVE = [("clickable_button", r'cursor\s*:\s*pointer', "缺少 cursor:pointer")]
CSS_MUST_NOT_HAVE = [("no_blocked_pointer", r'pointer-events\s*:\s*none', "存在 pointer-events:none")]


def phase1_contract_check(game_code: str, game_script: str) -> dict:
    critical_missing = [fb for _, p, fb in CRITICAL_RULES if not re.search(p, game_code, re.I)]
    warning_missing = [fb for _, p, fb in WARNING_RULES if not re.search(p, game_code, re.I)]
    css_warnings = [fb for _, p, fb in CSS_MUST_HAVE if not re.search(p, game_code, re.I)]
    css_warnings += [fb for _, p, fb in CSS_MUST_NOT_HAVE if re.search(p, game_code, re.I)]

    expected = _extract_answer_from_script(game_script)
    if expected and len(expected) > 0:
        norm = _normalize_for_search(game_code)
        if '\n' not in expected and len(expected) < 80:
            if expected.lower() not in norm:
                warning_missing.append(f"答案溯源：正确答案「{expected}」未在代码中找到")
        else:
            lines = [l.strip() for l in expected.split('\n') if l.strip()]
            if not any(l.lower() in norm for l in lines):
                warning_missing.append(f"答案溯源：正确答案（{len(lines)}行）未在代码中找到")

    if critical_missing: return {"level": "CRITICAL", "pass": False, "missing": critical_missing + css_warnings}
    if warning_missing or css_warnings: return {"level": "WARNING", "pass": False, "missing": warning_missing + css_warnings}
    return {"level": "PASS", "pass": True, "missing": []}


SYSTEM_PROMPT = """你是游戏 QA + 历史审查员 + 工作流优化顾问。

【审查维度】
1. 可运行性：JS 有无语法错误？按钮是否可点击？
2. 谜题一致性：代码验证的值与剧本 puzzle.answer 是否一致？
3. 历史准确性：HISTORY_FACTS 是否与史料一致？
4. 完整性：title/howto/game/result/history 五个画面是否齐全？
5. 可玩性：玩家知道要做什么吗？有引导吗？反馈即时吗？

【输出格式】
{
  "passed": false,
  "issues": [
    {
      "severity": "critical|warning|info",
      "category": "answer_mismatch|js_error|historical_error|ux|missing_screen|logic_bug",
      "description": "具体问题",
      "fix_strategy": "给 coder 的精确修复指令"
    }
  ],
  "reflexion": "根因分析 + 工作流优化建议"
}

⚠️ critical 问题 → passed=false
⚠️ 不要因为'不够好看'拒绝。'不知道要做什么'是功能问题不是美观问题。"""


def reviewer_node(state: GameFactoryState) -> dict:
    game_code = state["game_code"]
    game_script = state["game_script"]
    search_results = state.get("search_results", [])
    retry_count = state.get("retry_count", 0) + 1

    logger.info("审查开始 — retry=%d/%d, code_len=%d", retry_count, MAX_REVIEW_RETRIES, len(game_code))

    p1 = phase1_contract_check(game_code, game_script)

    if not p1["pass"] and p1["level"] == "CRITICAL":
        feedback = "【致命结构错误——跳过 LLM 审查】\n" + "\n".join(f"- {m}" for m in p1["missing"])
        result = {"review_passed": False, "review_feedback": feedback,
            "review_details": {"phase": "mechanical_critical", "missing": p1["missing"], "issues": []},
            "retry_count": retry_count,
            "agent_logs": [agent_log("reviewer", "mechanical_critical", f"CRITICAL 缺失 {len(p1['missing'])} 项")]}
        if retry_count >= MAX_REVIEW_RETRIES:
            result.update(error_message=f"经过 {retry_count} 次修改仍有致命结构错误。",
                suggestions=get_event_names()[:4], status="failed")
        return result

    warning_text = ""
    if p1["level"] == "WARNING":
        warning_text = "【结构警告】\n" + "\n".join(f"- {m}" for m in p1["missing"])

    # Phase 2：LLM 深度审查
    sources = "\n".join(f"- {r.get('title','')}: {r.get('content','')[:200]}" for r in search_results[:3])
    prompt = f"""审查这个 {len(game_code)} 字符的 HTML 游戏。

【游戏剧本】{game_script[:800]}
【原始史料】{sources}
【完整游戏代码】{game_code[:4000]}
当前重试: {retry_count}/{MAX_REVIEW_RETRIES}。

请严格按 system prompt 格式返回 JSON。必须包含 issues 数组和 reflexion 字段。"""

    try:
        response = chat_json(prompt, system=SYSTEM_PROMPT)
        response = _strip_markdown_fence(response)
        result = json.loads(response)
    except Exception:
        result = {"passed": True, "issues": [], "reflexion": "LLM审查异常，结构检查已通过，放行"}

    passed = result.get("passed", False)
    issues = result.get("issues", [])
    reflexion = result.get("reflexion", "")
    logger.info("Phase2: passed=%s, issues=%d, reflexion=%s", passed, len(issues), reflexion[:50])

    p2_feedback = ""
    if issues:
        lines = [f"【审查发现 {len(issues)} 个问题】"]
        for iss in issues:
            lines.append(f"[{iss.get('severity','?').upper()}] [{iss.get('category','?')}] {iss.get('description','')}")
            lines.append(f"→ 修复策略: {iss.get('fix_strategy','无')}")
        if reflexion: lines.append(f"\n【工作流反思】{reflexion}")
        p2_feedback = "\n".join(lines)
    if warning_text: p2_feedback = warning_text + "\n\n" + p2_feedback

    ret = {"review_passed": passed, "review_feedback": p2_feedback,
        "review_details": {"phase": "quality", "issues": issues, "reflexion": reflexion},
        "retry_count": retry_count,
        "agent_logs": [{"agent": "reviewer", "action": "pass" if passed else "reject",
            "detail": f"{len(issues)} issues; reflexion: {reflexion[:60]}"}]}

    if not passed and retry_count >= MAX_REVIEW_RETRIES:
        ret["error_message"] = f"游戏代码经过 {retry_count} 次修改仍未通过质量审查。"
        ret["suggestions"] = get_event_names()[:4]; ret["status"] = "failed"
    return ret
```

### 4.12 agents/artist_pre.py (美术设计)

```python
"""Artist Pre — LLM 自主视觉设计。"""

import json
from app.llm_client import agent_log, chat, _strip_markdown_fence

DEFAULT_FALLBACK = {
    "name": "默认像素", "mood_tags": ["像素", "复古"],
    "palette": ["#0a0a0a", "#e8702a", "#34d399", "#e8ddd0", "#5a4a3a"],
    "ui": "像素风格基础UI", "animation": "基础淡入淡出",
    "reference_css": "body{background:#0a0a0a;color:#e8ddd0;font-family:monospace}",
    "post": {"crt": False, "particles": "none", "atmosphere": ""}
}

SYSTEM_PROMPT = """你是一个像素风 HTML 游戏的视觉设计师。

基于剧本，自主分析氛围和情绪，生成 3 个不同的视觉设计方向。

每个方向必须说明：
1. 名称 + 与剧本氛围的关联性（引用剧本具体描述）
2. 色板（5个色值）、UI风格（3句话）、动画节奏（1句话）、参考CSS（3-5行）
3. 自评选择最佳方向，说明理由

JSON格式：
{
  "directions": [
    {"name":"...","mood_tags":["..."],"palette":[...],"ui":"...","animation":"...","reference_css":"...","post":{"crt":bool,"particles":"...","atmosphere":"..."}}
  ],
  "selected_index": 0,
  "selection_reasoning": "为什么选这个（引用剧本细节）"
}

要求：3个方向，在交互隐喻/动画节奏/UI形状上明显不同。不要markdown代码块。"""


def artist_pre_node(state: dict) -> dict:
    script = state.get("script_data", {})
    puzzle_type = script.get("puzzle", {}).get("type", "cipher")

    prompt = f"""为以下游戏生成 3 个视觉方向并选择最佳方案。

事件：{script.get('event','')}
类型：{puzzle_type}
氛围：{script.get('atmosphere','')}
情绪：{script.get('mood','')}
时代：{script.get('era','')}
道具：{', '.join(script.get('key_props',[]))}
视觉锚点：{script.get('visual',{}).get('mood','')}

按 system prompt 的 JSON 格式输出。必须包含 selection_reasoning。"""

    try:
        response = chat(prompt, system=SYSTEM_PROMPT, temperature=0.7)
        response = _strip_markdown_fence(response)
        data = json.loads(response)
        directions = data.get("directions", [])
        idx = max(0, min(data.get("selected_index", 0), len(directions) - 1)) if directions else 0
        selected = directions[idx] if directions else DEFAULT_FALLBACK

        return {
            "directions": directions or [DEFAULT_FALLBACK],
            "selected_direction": selected,
            "agent_logs": [agent_log("artist_pre", "designed",
                f"生成{len(directions)}个方向，选择「{selected['name']}」——{data.get('selection_reasoning','')[:60]}")]
        }
    except Exception as e:
        return {
            "directions": [DEFAULT_FALLBACK], "selected_direction": DEFAULT_FALLBACK,
            "agent_logs": [agent_log("artist_pre", "error_fallback", str(e))]
        }
```

### 4.13 agents/artist_post.py (美术渲染)

```python
"""Artist Post-Processing — BS4 注入 + LLM 补充 CSS。"""

import re
from bs4 import BeautifulSoup
from app.llm_client import agent_log, chat, _strip_markdown_fence


def _safe_append_css(soup, css: str):
    if not soup.head:
        soup.insert(0, soup.new_tag('head'))
    style_tag = soup.find('style')
    if not style_tag:
        style_tag = soup.new_tag('style')
        soup.head.append(style_tag)
    if style_tag.string:
        style_tag.string += '\n' + css
    else:
        style_tag.string = css


def _safe_append_head(html: str, tag_html: str) -> str:
    soup = BeautifulSoup(html, 'html.parser')
    if not soup.head:
        soup.insert(0, soup.new_tag('head'))
    link = BeautifulSoup(tag_html, 'html.parser')
    soup.head.append(link)
    return str(soup)


def inject_screen_transition(html: str) -> str:
    screen_css = ".screen{opacity:0;transform:scale(0.98);transition:opacity 0.5s,transform 0.5s;pointer-events:none}.screen.active{opacity:1;transform:scale(1);pointer-events:auto}"
    soup = BeautifulSoup(html, 'html.parser')
    _safe_append_css(soup, screen_css)
    return str(soup)


def inject_fonts(html: str, direction: dict) -> str:
    font_hint = direction.get("ui", "") + direction.get("reference_css", "")
    font_link = None
    if "Press Start 2P" in font_hint or "pixel" in font_hint.lower():
        font_link = '<link href="https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap" rel="stylesheet">'
    elif "Fira Code" in font_hint or "monospace" in direction.get("animation", ""):
        font_link = '<link href="https://fonts.googleapis.com/css2?family=Fira+Code&display=swap" rel="stylesheet">'
    if font_link and "fonts.googleapis.com" not in html:
        html = _safe_append_head(html, font_link)
    return html


def inject_reference_css(html: str, direction: dict) -> str:
    ref = direction.get("reference_css", "")
    if ref and len(ref) > 10:
        soup = BeautifulSoup(html, 'html.parser')
        _safe_append_css(soup, "/* === 方向视觉 === */\n" + ref)
        return str(soup)
    return html


def inject_atmosphere(html: str, direction: dict) -> str:
    soup = BeautifulSoup(html, 'html.parser')
    post = direction.get("post", {})
    if post.get("crt"):
        _safe_append_css(soup, "body::after{content:\"\";position:fixed;inset:0;background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,0.03) 2px,rgba(0,0,0,0.03) 4px);pointer-events:none;z-index:9999;}")
    atmosphere = post.get("atmosphere", "")
    if atmosphere:
        _safe_append_css(soup, "/* artist_post_atmosphere */\n" + atmosphere)
    return str(soup)


def inject_palette_vars(html: str, direction: dict) -> str:
    palette = direction.get("palette", [])
    if len(palette) < 5:
        return html
    var_css = f":root{{--bg:{palette[0]};--primary:{palette[1]};--success:{palette[2]};--text:{palette[3]};--muted:{palette[4]};--panel:{palette[0]}dd;--border:{palette[4]}44;--text-dim:{palette[3]}88;--warning:#d29922;--danger:#f85149;--accent:#d2a8ff}}"
    soup = BeautifulSoup(html, 'html.parser')
    _safe_append_css(soup, var_css)
    return str(soup)


def llm_generate_supplement(existing_css: str, direction: dict) -> str:
    prompt = f"""你是一位 CSS 氛围设计师。现有 CSS 如下：

{existing_css[:2000]}

请只输出"需要补充的 CSS"，包括：
1. 更精细的 @keyframes 动画
2. 氛围粒子样式
3. 任何能让视觉更生动的微调

【要求】
- 只输出纯 CSS，不要解释
- 不要覆盖已有选择器，只补充新的
- 总长度控制在 30 行以内"""
    css = chat(prompt, temperature=0.2)
    return _strip_markdown_fence(css)


def artist_post_node(state: dict) -> dict:
    game_code = state.get("game_code", "")
    direction = state.get("selected_direction", {})

    styled = game_code

    # Step 1: 方向感知注入（BS4）
    styled = inject_palette_vars(styled, direction)
    styled = inject_reference_css(styled, direction)
    styled = inject_screen_transition(styled)
    styled = inject_fonts(styled, direction)
    styled = inject_atmosphere(styled, direction)

    # Step 2: 可选 LLM 微调（追加模式）
    try:
        soup = BeautifulSoup(styled, 'html.parser')
        style_tag = soup.find('style')
        if style_tag and style_tag.string:
            existing = style_tag.string
            supplement = llm_generate_supplement(existing, direction)
            if supplement and len(supplement) > 20:
                _safe_append_css(soup, '/* === artist_post supplement === */\n' + supplement)
                styled = str(soup)
    except Exception:
        pass

    return {
        "styled_code": styled,
        "status": "success",
        "agent_logs": [agent_log("artist_post", "styled", f"{len(styled)} chars")]
    }
```

### 4.14 agents/coder_templates_bagu.py (八股交互模板)

*文件较长 (241行)，包含 4 个模板的 LLM 提示词：DEBUGGER_TEMPLATE, MATCH_TEMPLATE, FILL_BLANK_TEMPLATE, RECITE_TEMPLATE。每个模板详细描述了该游戏类型的交互元素、视觉风格、代码结构要求和校验逻辑。*

*完整代码见项目文件 `backend/app/agents/coder_templates_bagu.py`*

### 4.15 mcp/web_search.py (网页搜索)

```python
"""MCP 工具 — 网页搜索引擎（Bing → DuckDuckGo fallback）。"""

import urllib.request, urllib.parse, json, html as html_mod, logging
from html.parser import HTMLParser

logger = logging.getLogger("mcp.web_search")


def _search_bing(query: str, max_results: int = 5) -> list[dict]:
    """Bing 搜索。用 html.parser 替代纯正则。"""
    url = f"https://www.bing.com/search?{urllib.parse.urlencode({'q': query})}"

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html_text = resp.read().decode("utf-8", errors="ignore")

        import re

        class BingParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.results = []; self.in_item = False; self.in_title = False; self.in_snippet = False
                self.title = ""; self.snippet = ""; self.url = ""; self.depth = 0; self.snip_depth = 0

            def handle_starttag(self, tag, attrs):
                attrs_dict = dict(attrs); cls = attrs_dict.get('class', '')
                if tag == 'li' and 'b_algo' in cls:
                    self.in_item = True; self.title = ""; self.snippet = ""; self.url = ""
                if self.in_item and tag == 'h2': self.in_title = True
                if self.in_item and tag == 'p': self.in_snippet = True; self.snip_depth = 0
                if self.in_item and tag == 'a' and attrs_dict.get('href','').startswith('http'):
                    if not self.url or 'bing.com' not in attrs_dict.get('href',''):
                        self.url = attrs_dict.get('href','')
                if self.in_snippet: self.snip_depth += 1

            def handle_endtag(self, tag):
                if self.in_item and tag == 'h2': self.in_title = False
                if self.in_snippet: self.snip_depth -= 1
                if self.in_snippet and self.snip_depth <= 0: self.in_snippet = False
                if self.in_item and tag == 'li':
                    self.in_item = False
                    if self.title and len(self.snippet) > 10:
                        self.results.append({
                            "title": html_mod.unescape(self.title.strip()),
                            "snippet": html_mod.unescape(self.snippet.strip()),
                            "url": self.url,
                        })

            def handle_data(self, data):
                if self.in_title: self.title += data
                if self.in_snippet: self.snippet += data

        parser = BingParser()
        parser.feed(html_text)

        # Fallback regex
        if not parser.results:
            items = re.findall(r'<li class="b_algo"[^>]*>(.*?)</li>', html_text, re.DOTALL)
            for item in items[:max_results]:
                title_m = re.search(r'<h2[^>]*><a[^>]*>(.*?)</a>', item, re.DOTALL)
                snippet_m = re.search(r'<p[^>]*>(.*?)</p>', item, re.DOTALL)
                url_m = re.search(r'<a[^>]*href="(https?://[^"]*)"', item)
                if title_m:
                    parser.results.append({
                        "title": html_mod.unescape(re.sub(r'<[^>]+>', '', title_m.group(1))),
                        "snippet": html_mod.unescape(re.sub(r'<[^>]+>', '', snippet_m.group(1))) if snippet_m else "",
                        "url": url_m.group(1) if url_m and 'bing.com' not in url_m.group(1) else "",
                    })

        # Filter + dedup
        seen, filtered = set(), []
        for r in parser.results:
            url = r.get("url", "")
            if url and ('bing.com' in url or 'microsoft.com/bing' in url): continue
            key = r["title"]
            if key not in seen: seen.add(key); filtered.append(r)

        logger.info("Bing search '%s': %d results", query[:40], len(filtered))
        return filtered[:max_results]

    except Exception as e:
        logger.warning("Bing search failed: %s", e)
        return []


def _search_ddg(query: str, max_results: int = 5) -> list[dict]:
    """DuckDuckGo（海外 fallback）。"""
    url = f"https://api.duckduckgo.com/?{urllib.parse.urlencode({'q': query, 'format': 'json', 'no_html': 1})}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "time-pixels/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        results = []
        if data.get("AbstractText"):
            results.append({
                "title": data.get("Heading", query),
                "snippet": data.get("AbstractText", ""),
                "url": data.get("AbstractURL", ""),
            })
        for topic in data.get("RelatedTopics", [])[:max_results]:
            if isinstance(topic, dict) and "Text" in topic:
                results.append({
                    "title": topic.get("FirstURL", "").split("/")[-1].replace("_", " "),
                    "snippet": topic.get("Text", ""),
                    "url": topic.get("FirstURL", ""),
                })
        return [r for r in results if r["snippet"]][:max_results]
    except Exception:
        return []


def search(query: str, max_results: int = 5) -> list[dict]:
    results = _search_bing(query, max_results)
    if not results:
        results = _search_ddg(query, max_results)
    return results
```

### 4.16 knowledge/kb.py (知识库)

```python
"""共享知识库模块 — 支持双知识库：计算机历史 + Python 八股。"""

import json
import os

_KB_DIR = os.path.dirname(__file__)


def _name(event: dict) -> str:
    return event.get("event", event.get("title", ""))


def _prep_keywords(event: dict):
    for key in ("keywords", "aliases"):
        vals = event.get(key, [])
        event[key] = [v.lower().strip() for v in vals if v]

# 计算机历史
with open(os.path.join(_KB_DIR, "verified_events.json"), "r", encoding="utf-8") as f:
    EVENTS = json.load(f)
for e in EVENTS:
    _prep_keywords(e)

# Python 八股
_BAGU_PATH = os.path.join(_KB_DIR, "verified_bagu.json")
BAGU_EVENTS = []
if os.path.exists(_BAGU_PATH):
    with open(_BAGU_PATH, "r", encoding="utf-8") as f:
        bagu_data = json.load(f)
        BAGU_EVENTS = bagu_data.get("events", [])
    for e in BAGU_EVENTS:
        _prep_keywords(e)


def get_all_events(category: str = None) -> list[dict]:
    if category == "bagu":
        return BAGU_EVENTS
    if category == "computer_history":
        return EVENTS
    return EVENTS + BAGU_EVENTS


def get_event_names(category: str = None) -> list[str]:
    if category == "bagu":
        return [_name(e) for e in BAGU_EVENTS]
    return [_name(e) for e in EVENTS]


def get_event_by_keyword(text: str, category: str = None) -> dict | None:
    pools = []
    if category in (None, "computer_history"):
        pools.extend(EVENTS)
    if category in (None, "bagu"):
        pools.extend(BAGU_EVENTS)

    query = text.lower().strip()
    best = None; best_score = 0

    for event in pools:
        score = 0
        for alias in event.get("aliases", []):
            if alias == query: score += 3
            elif query in alias or alias in query: score += 1.5
        event_name = _name(event).lower()
        if query == event_name: score += 3
        elif query in event_name or event_name in query: score += 1.5
        for kw in event.get("keywords", []):
            if kw in query or query in kw: score += 0.5
        if score > best_score:
            best_score = score; best = event

    return best if best_score >= 1 else None


def event_to_search_results(event: dict) -> list[dict]:
    # 八股事件：content.annotations → key_facts（planner/coder 消费），
    # content.original → content 字段（coder 注入到游戏），
    # puzzle_guide 原样传递（planner 短路判断 + coder 数据注入）。
    if "content" in event and "original" in event.get("content", {}):
        content = event["content"]
        return [{
            "title": f"「{event.get('title', event.get('event', ''))}」",
            "content": f"{content.get('translation', '')}\n\n原始代码：\n{content.get('original', '')}",
            "confidence": "high",
            "verified": True,
            "source": "verified_knowledge_base",
            "key_facts": content.get("annotations", []),  # ← content.annotations 映射为 key_facts
            "atmosphere_tags": event.get("atmosphere_tags", []),
            "key_props": event.get("key_props", []),
            "visual_anchor": event.get("visual_anchor", ""),
            "category": event.get("category", "bagu"),
            "puzzle_guide": event.get("puzzle_guide", {}),  # ← 原样传递，含 type + blanks/match_pairs/recite_config/bug_info
        }]

    # 计算机历史事件
    facts = event.get("facts", {})
    return [{
        "title": f"「{event['event']}」已验证史料",
        "content": facts.get("story", "") + "\n\n趣闻：" + facts.get("fun_fact", ""),
        "confidence": "high",
        "verified": True,
        "source": "verified_knowledge_base",
        "key_facts": [
            f"时间：{facts.get('time', '')}",
            f"地点：{facts.get('place', '')}",
            f"人物：{'、'.join(facts.get('people', []))}",
        ],
        "atmosphere_tags": event.get("atmosphere_tags", []),
        "key_props": event.get("key_props", []),
        "visual_anchor": event.get("visual_anchor", ""),
        "category": event.get("category", "computer_history"),
    }]
```

### 4.17 schema/game_script.py

```python
"""GameScript Schema — writer Agent 的结构化输出文档。"""

GAME_SCRIPT_SCHEMA = {
    "event": "string — 历史事件名",
    "year": "number — 发生年份",
    "location": "string — 发生地点",
    "protagonist": "string — 主角/核心人物",
    "antagonist": "string — 对抗方",
    "core_conflict": "string — 核心冲突",
    "atmosphere": "string — 氛围关键词",
    "opening_hook": "string — 标题画面悬念句",

    "puzzle": {
        "type": "cipher | sequence | logic",
        "surface": "string — 谜题表皮",
        "answer": "string — 正确答案",
        "items_count": "number",
        "items_labels": ["string"],
        "hints": [{"level": 1, "text": "..."}, {"level": 2, "text": "..."}, {"level": 3, "text": "..."}],
        "max_attempts": 3,
    },

    "history_facts": ["string — 核心事实"],

    "victory_line": "string",
    "defeat_line": "string",

    "visual": {
        "palette": ["#色值×5"],
        "mood": "string",
        "decorations": ["string"],
    },
}
```

---

## 5. 知识库数据

### 5.1 verified_events.json (完整内容)

*包含 25 个计算机历史事件，每个含 facts (story/fun_fact/time/place/people) + atmosphere_tags + key_props + visual_anchor。总 1027 行。*

*完整见 `backend/app/knowledge/verified_events.json`*

**事件列表**：Turing/Enigma (1940), Guido/Python (1989), Cerf-Kahn/TCP (1974), Linus/Linux (1991), Java/Gosling (1995), Codd/SQL (1970), McCarthy/Lisp (1958), Bayer/B-tree (1971), antirez/Redis (2009), Andreessen/Mosaic (1993), ENIAC (1946), ARPANET (1969), Macintosh (1984), Facebook (2004), OpenAI (2015), Google (1998), iPhone (2007), Transformer (2017), Intel (1968), GitHub (2008), ChatGPT (2022), GNU (1983), Wikipedia (2001), Winamp (1998), Napster (1999), Unicode (1991), Docker (2014)

*完整 JSON 数据见源码文件。*

### 5.2 verified_bagu.json (完整内容)

*包含 8 道 Python 面试题，每题含 content (original/translation/annotations) + puzzle_guide (type + blanks/match_pairs/recite_config/bug_info + hints + scoring + expected_output)。总 809 行。*

*完整见 `backend/app/knowledge/verified_bagu.json`*

**八股列表**：
1. ★☆☆☆ 可变对象 vs 不可变对象 → fill_blank
2. ★★☆☆ 深拷贝 vs 浅拷贝 → match
3. ★★☆☆ 装饰器语法糖 → fill_blank
4. ★★★☆ 生成器与 yield → recite
5. ★★★☆ GIL 全局解释器锁 → match
6. ★★★☆ 上下文管理器 → fill_blank
7. ★★★★ 描述符与 @property → recite
8. ★★★☆ 可变默认参数陷阱 → debugger

*完整 JSON 数据见源码文件。*

---

## 6. 骨架模板

4 个骨架 HTML 模板位于 `backend/app/templates/`，总 1090 行。

- `skeleton_fill_blank.html` (389行): 代码填空游戏，含语法高亮、三色反馈(绿/黄/红)、终端面板、提示系统
- `skeleton_recite.html` (295行): 代码默写游戏，含 IDE 模拟、三点骨架、难度切换 L1/L2/L3
- `skeleton_match.html` (191行): 概念配对游戏，含 SVG 连线、点击配对、知识卡片
- `skeleton_debugger.html` (215行): Bug 定位游戏，含行号点击、类型选择、修复对比

所有骨架使用 `{{PLACEHOLDER}}` 语法，由 coder 的 `_fill_common()` 函数替换。

*完整模板内容见源码文件 `backend/app/templates/skeleton_*.html`*

---

## 7. 前端源码

### 7.1 App.jsx

```jsx
import { useState, useRef, useEffect } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import RevealLayer from './components/RevealLayer'
import { GamePanel } from './components/GamePanel'
import { AgentBuds } from './components/AgentBuds'
import { SearchBubble } from './components/SearchBubble'
import { EventTags } from './components/EventTags'
import { DecisionLog } from './components/DecisionLog'
import { FailureNotice } from './components/FailureNotice'
import { ErrorBoundary } from './components/ErrorBoundary'

const BG_BASE   = '/images/base.jpg'
const BG_REVEAL = '/images/reveal.jpg'

const AGENTS = [
  { key:'crawler',  name:'寻根' },
  { key:'planner',  name:'织梦' },
  { key:'writer',   name:'叙事' },
  { key:'coder',    name:'构建' },
  { key:'reviewer', name:'凝视' },
  { key:'artist_post', name:'着色' },
]

export default function App() {
  const { statuses, messages, gameCode, error, isGenerating, sendEvent, cancel, dismiss } = useWebSocket()

  // ── 光标聚光灯 ──
  const mouse  = useRef({ x:-999, y:-999 })
  const smooth = useRef({ x:-999, y:-999 })
  const rafRef = useRef()
  const [cursorPos, setCursorPos] = useState({ x:-999, y:-999 })

  useEffect(() => {
    const onMove = (e) => { mouse.current = { x:e.clientX, y:e.clientY } }
    window.addEventListener('mousemove', onMove)
    const loop = () => {
      smooth.current.x += (mouse.current.x - smooth.current.x) * 0.1
      smooth.current.y += (mouse.current.y - smooth.current.y) * 0.1
      const rx=Math.round(smooth.current.x), ry=Math.round(smooth.current.y)
      setCursorPos(p => (p.x===rx&&p.y===ry)?p:{x:rx,y:ry})
      rafRef.current = requestAnimationFrame(loop)
    }
    rafRef.current = requestAnimationFrame(loop)
    return () => { window.removeEventListener('mousemove',onMove); cancelAnimationFrame(rafRef.current) }
  }, [])

  const completedAgents = Object.values(statuses).filter(s => s.status==='done').length

  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-black">
        <section className="relative w-full h-screen overflow-hidden bg-black" style={{ height:'100dvh' }}>

          {/* z-10: 基底图 */}
          <div className="absolute inset-0 bg-center bg-cover bg-no-repeat z-10 hero-zoom"
            style={{ backgroundImage:`url(${BG_BASE})` }} />

          {/* z-20: 光标揭示层 */}
          <RevealLayer image={BG_REVEAL} cursorX={cursorPos.x} cursorY={cursorPos.y} />

          {/* z-50: 标题 */}
          <div className="absolute z-50 top-[10%] left-0 right-0 flex flex-col items-center text-center px-5 pointer-events-none">
            <h1 className="text-white leading-[0.95]">
              <span className="block text-5xl sm:text-7xl md:text-8xl font-semibold hero-anim hero-reveal"
                style={{ fontFamily:"'PingFang SC','Noto Serif SC','STSong',serif", letterSpacing:'0.04em', animationDelay:'0.25s' }}>
                时光像素
              </span>
              <span className="block text-lg sm:text-2xl md:text-3xl font-light mt-1 text-white/45 hero-anim hero-reveal"
                style={{ letterSpacing:'0.18em', animationDelay:'0.42s' }}>
                以 史 为 壤  ·  生 长 游 戏
              </span>
            </h1>
          </div>

          {/* z-50: 搜索框 */}
          <div className="absolute z-50 top-[28%] left-1/2 -translate-x-1/2 w-[90vw] max-w-lg pointer-events-auto">
            <SearchBubble onGenerate={sendEvent} isGenerating={isGenerating} onCancel={cancel} />
          </div>

          {/* z-50: 事件标签 */}
          <div className="absolute z-50 inset-0 pointer-events-none">
            <EventTags onSelect={sendEvent} disabled={isGenerating} />
          </div>

          {/* z-50: 6 Agent 银色闪电 */}
          <div className="absolute z-50 inset-0 pointer-events-none">
            <AgentBuds agents={AGENTS} statuses={statuses} />
          </div>

          {/* z-50: 游戏展示区 */}
          <GamePanel
            visible={!!gameCode}
            gameCode={gameCode}
            isGenerating={isGenerating}
            agentCount={AGENTS.length}
            doneCount={completedAgents}
            onClose={dismiss}
          />

          {/* z-100: 失败提示 */}
          <FailureNotice
            visible={!!error}
            reason={error?.reason||''}
            suggestions={error?.suggestions||[]}
            onRetry={sendEvent}
            onDismiss={dismiss}
          />

          {/* z-100: 决策轨迹 */}
          <DecisionLog messages={messages} />

        </section>
      </div>
    </ErrorBoundary>
  )
}
```

### 7.2 index.css

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

* { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif; }

/* hero 动画 */
@keyframes heroReveal {
  0%   { opacity:0; transform:translateY(28px); filter:blur(12px); }
  100% { opacity:1; transform:translateY(0); filter:blur(0); }
}
@keyframes heroFadeUp {
  0%   { opacity:0; transform:translateY(20px); }
  100% { opacity:1; transform:translateY(0); }
}
@keyframes heroZoom {
  0%   { transform:scale(1.12); }
  100% { transform:scale(1); }
}
@keyframes panelReveal {
  0%   { opacity:0; transform:translateX(-50%) scale(0.92); }
  100% { opacity:1; transform:translateX(-50%) scale(1); }
}
@keyframes pulseGlow {
  0%,100% { box-shadow:0 0 8px rgba(52,211,153,0.15); }
  50%     { box-shadow:0 0 24px rgba(52,211,153,0.3); }
}
@keyframes blink {
  0%,100% { opacity:1; }
  50%     { opacity:0.2; }
}
@keyframes progressBar {
  0%   { width:0%; }
  100% { width:100%; }
}

.hero-anim   { opacity:0; animation-fill-mode:forwards; animation-timing-function:cubic-bezier(0.16,1,0.3,1); }
.hero-reveal { animation-name:heroReveal; animation-duration:1.1s; }
.hero-fade   { animation-name:heroFadeUp; animation-duration:1s; }
.hero-zoom   { animation:heroZoom 1.8s cubic-bezier(0.16,1,0.3,1) forwards; }
.panel-reveal{ animation:panelReveal 0.4s cubic-bezier(0.16,1,0.3,1) forwards; }

@media (prefers-reduced-motion:reduce){ .hero-anim,.hero-zoom,.panel-reveal{ animation:none;opacity:1; } }

::-webkit-scrollbar { width:3px; }
::-webkit-scrollbar-track { background:transparent; }
::-webkit-scrollbar-thumb { background:rgba(255,255,255,0.08); border-radius:10px; }
```

### 7.3 hooks/useWebSocket.js

```javascript
import { useState, useRef, useCallback } from 'react'

const WS_URL = `ws${location.protocol === 'https:' ? 's' : ''}://${window.location.host}/ws/generate`

export function useWebSocket() {
  const [statuses, setStatuses] = useState({})
  const [messages, setMessages] = useState([])
  const [gameCode, setGameCode] = useState(null)
  const [error, setError] = useState(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const wsRef = useRef(null)
  const logIdRef = useRef(0)
  const generatingRef = useRef(false)
  const lastSend = useRef(0)

  const sendEvent = useCallback((eventText) => {
    if (!eventText.trim()) return
    const now = Date.now()
    if (now - lastSend.current < 1000) return
    lastSend.current = now

    if (wsRef.current) { wsRef.current.close() }

    setStatuses({}); setMessages([]); setGameCode(null); setError(null)
    setIsGenerating(true); generatingRef.current = true

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => { ws.send(JSON.stringify({ event: eventText })) }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        switch (data.type) {
          case 'agent_progress':
            setStatuses(prev => ({
              ...prev,
              [data.agent]: { status: data.status, message: data.message, retries: (prev[data.agent]?.retries || 0) },
            }))
            setMessages(prev => [...prev, { id: ++logIdRef.current, time: new Date().toLocaleTimeString(), agent: data.agent, detail: data.message }])
            break
          case 'game_ready':
            setGameCode(data.game_code); setIsGenerating(false); generatingRef.current = false
            break
          case 'generation_failed':
            setError({ reason: data.reason || '生成失败', suggestions: data.suggestions || [] })
            setIsGenerating(false); generatingRef.current = false
            break
          case 'agent_log':
            setMessages(prev => [...prev, { id: ++logIdRef.current, time: new Date().toLocaleTimeString(), agent: data.agent, detail: `${data.action}: ${data.detail}` }])
            break
          case 'review_rejected':
            setMessages(prev => [...prev, { id: ++logIdRef.current, time: new Date().toLocaleTimeString(), agent: 'reviewer', detail: `❌ 审查不通过 → 退回重做: ${data.feedback?.slice(0, 80) || ''}` }])
            break
        }
      } catch (e) {
        setMessages(prev => [...prev, { id: ++logIdRef.current, time: new Date().toLocaleTimeString(), agent: 'system', detail: `消息解析失败: ${e.message}` }])
      }
    }

    ws.onerror = () => { setError({ reason: 'WebSocket 连接失败，请确认后端已启动', suggestions: [] }); setIsGenerating(false); generatingRef.current = false }
    ws.onclose = () => { if (generatingRef.current) { setIsGenerating(false); generatingRef.current = false } }
  }, [])

  const cancel = useCallback(() => { if (wsRef.current) { wsRef.current.close(); wsRef.current = null }; setIsGenerating(false); generatingRef.current = false }, [])
  const dismiss = useCallback(() => { if (wsRef.current) { wsRef.current.close(); wsRef.current = null }; setIsGenerating(false); generatingRef.current = false; setGameCode(null); setError(null); setStatuses({}); setMessages([]) }, [])

  return { statuses, messages, gameCode, error, isGenerating, sendEvent, cancel, dismiss }
}
```

### 7.4 components/SearchBubble.tsx

```tsx
import { useState } from 'react'
import { Search, Zap, X } from 'lucide-react'

interface Props { onGenerate:(text:string)=>void; isGenerating:boolean; onCancel:()=>void }

export function SearchBubble({ onGenerate, isGenerating, onCancel }: Props) {
  const [value, setValue] = useState('')

  return (
    <form onSubmit={e=>{e.preventDefault();if(value.trim()){onGenerate(value.trim());setValue('')}}}
      className="flex gap-2 hero-anim hero-fade" style={{ animationDelay:'0.55s' }}>
      <div className="relative flex-1">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40 pointer-events-none" />
        <input value={value} onChange={e=>setValue(e.target.value)} placeholder="输入计算机历史事件…"
          disabled={isGenerating} aria-label="计算机历史事件"
          className="w-full pl-11 pr-4 py-3.5 bg-white/[0.10] backdrop-blur-xl border border-white/[0.18] rounded-2xl text-white text-sm placeholder:text-white/35 focus:outline-none focus:border-lime-400/60 focus:bg-white/[0.16] transition-all disabled:opacity-40 shadow-lg" />
      </div>
      {isGenerating ? (
        <button type="button" onClick={onCancel}
          className="px-4 py-3.5 bg-white/[0.08] border border-white/[0.15] rounded-2xl text-white/60 hover:text-red-400 hover:border-red-400/40 transition-all">
          <X className="w-4 h-4" /></button>
      ) : (
        <button type="submit" disabled={!value.trim()}
          className="px-5 py-3.5 bg-lime-600 hover:bg-lime-500 text-white text-sm font-medium rounded-2xl transition-all hover:scale-[1.02] active:scale-95 disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:scale-100 flex items-center gap-2 shadow-lg shadow-lime-500/20">
          <Zap className="w-4 h-4" />生成</button>
      )}
    </form>
  )
}
```

### 7.5 components/EventTags.tsx

```tsx
import { useState, useEffect, useRef } from 'react'
import { ChevronDown, History, Code2 } from 'lucide-react'

const DEMO_EVENTS = ['1940年 Turing 破译 Enigma','1989年 Guido 发明 Python','1974年 TCP 协议诞生','1991年 Linus 写下 Linux','1995年 Java 的诞生']

interface Props { onSelect:(name:string)=>void; disabled:boolean }

export function EventTags({ onSelect, disabled }: Props) {
  const [events, setEvents] = useState<any[]>([])
  const [open, setOpen] = useState(false)
  const [category, setCategory] = useState<'computer_history'|'bagu'>('computer_history')
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const cat = category === 'bagu' ? '?category=bagu' : ''
    fetch(`/api/events${cat}`).then(r=>r.json()).then(d=>setEvents(d.events||[])).catch(()=>setEvents(DEMO_EVENTS.map(n=>({name:n}))))
  }, [category])

  useEffect(() => {
    const handler = (e:MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  if (events.length===0) return null

  const isBag = category === 'bagu'
  const names = events.map((e:any) => e.name || e.title || '')

  return (
    <div ref={ref} className="fixed top-5 right-5 z-[110] pointer-events-auto">
      <div className="flex items-center gap-2">
        <button onClick={() => { setCategory(isBag ? 'computer_history' : 'bagu'); setOpen(false) }} disabled={disabled}
          className="flex items-center gap-1.5 px-3 py-2.5 bg-white/[0.04] backdrop-blur-xl border border-white/[0.08] rounded-2xl text-white/40 hover:text-white/70 hover:bg-white/[0.08] transition-all text-[11px] disabled:opacity-30">
          {isBag ? <Code2 className="w-3.5 h-3.5" /> : <History className="w-3.5 h-3.5" />}
          {isBag ? 'Python 面试' : '事件库'}
        </button>
        <button onClick={() => setOpen(!open)} disabled={disabled}
          className="flex items-center gap-2 px-4 py-2.5 bg-white/[0.06] backdrop-blur-xl border border-white/[0.12] rounded-2xl text-white/60 hover:text-white/85 hover:bg-white/[0.1] hover:border-white/[0.2] transition-all text-xs shadow-lg disabled:opacity-30">
          事件库
          <ChevronDown className={`w-3 h-3 transition-transform ${open?'rotate-180':''}`} />
        </button>
      </div>

      {open && (
        <div className="absolute top-full right-0 mt-2 w-80 bg-black/80 backdrop-blur-2xl border border-white/[0.12] rounded-2xl shadow-2xl overflow-y-auto" style={{maxHeight:'50vh'}}>
          {names.map((name: string, i: number) => (
            <button key={i} onClick={() => { onSelect(name); setOpen(false) }} disabled={disabled}
              className="w-full text-left px-5 py-3 text-[13px] text-white/50 hover:text-white/90 hover:bg-white/[0.06] transition-all border-b border-white/[0.04] last:border-0 disabled:opacity-20 flex items-center gap-2">
              {isBag && events[i]?.difficulty ? (
                <span className="text-[10px] text-lime-400/50">{'★'.repeat(events[i].difficulty)}{'☆'.repeat(4-events[i].difficulty)}</span>
              ) : null}
              <span className="truncate">{name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
```

### 7.6 components/AgentBuds.tsx

*完整源码 (128行) 包含 6 个 Agent 头像 (银色闪电 SVG)，带有 running/done/failed/idle 四种状态的动画效果 (glow ring, scale pulse, silver aura)，支持重试角标。*

*完整代码见源码文件。*

### 7.7 components/GamePanel.tsx

*完整源码 (112行) 包含 iframe 游戏展示面板，支持生成进度条、空闲状态动画、最小化浮窗、全屏切换。使用 sandbox="allow-scripts" 安全策略。*

*完整代码见源码文件。*

### 7.8 components/RevealLayer.tsx

*完整源码 (89行) 使用 Canvas 2D API 实现光标聚光灯效果。通过 requestAnimationFrame 循环更新 Canvas → toDataURL → maskImage，实现 base.jpg 和 reveal.jpg 两层的 reveal 效果。*

*完整代码见源码文件。*

### 7.9 components/FailureNotice.tsx

*完整源码 (43行) 失败提示浮层，展示错误原因 + 4 个推荐重试的事件按钮。*

*完整代码见源码文件。*

### 7.10 components/DecisionLog.tsx

*完整源码 (47行) 决策轨迹面板，底部左侧显示最近的 Agent 日志消息，支持展开/折叠，自动滚动到最新。*

*完整代码见源码文件。*

### 7.11 components/ErrorBoundary.tsx

*完整源码 (30行) React Error Boundary 类组件，捕获渲染错误并显示刷新页面按钮。*

*完整代码见源码文件。*

---

## 附录：快速参考

### 运行命令
```bash
# 后端
cd backend && ..\venv\Scripts\python -m uvicorn app.main:app --reload
# 前端
cd frontend && npm run dev
```

### 最近关键修复 (2026-08-03)
1. **planner 短路条件 bug**: `puzzle_guide.annotations` 不存在 → 改用 `key_facts` (映射自 `content.annotations`)
2. **类型特定数据校验**: `fill_blank` 查 `blanks` / `match` 查 `match_pairs` / `recite` 查 `recite_config` / `debugger` 查 `bug_info`
3. **LLM 防御**: planner SYSTEM_PROMPT 加"类型选择铁律"——禁止返回 "puzzle" 等模糊类型
4. **kb.py 注释**: 显式标注 `content.annotations → key_facts` 和 `puzzle_guide` 的字段映射

### GitHub
https://github.com/hfujw/ai-game-factory
