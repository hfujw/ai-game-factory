# 时光像素 — 后端 + 知识库 + 模板 完整源码

> 给 Kimi 看 · 文件 1/2 · 2026-08-03

---

## 目录

1. main.py (FastAPI入口)
2. ws_manager.py (WebSocket管理器)
3. llm_client.py (DeepSeek封装)
4. config.py
5. graph/state.py (状态定义)
6. graph/workflow.py (LangGraph编排)
7. agents/crawler.py (搜史料)
8. agents/planner.py (策划)
9. agents/writer.py (编剧)
10. agents/coder.py (施工)
11. agents/reviewer.py (审查)
12. agents/artist_pre.py (美术设计)
13. agents/artist_post.py (美术渲染)
14. agents/coder_templates_bagu.py (八股交互模板)
15. mcp/web_search.py (网页搜索)
16. knowledge/kb.py (知识库)
17. knowledge/verified_events.json (计算机历史知识库)
18. knowledge/verified_bagu.json (Python八股知识库)
19. schema/game_script.py
20. templates/skeleton_fill_blank.html
21. templates/skeleton_recite.html
22. templates/skeleton_match.html
23. templates/skeleton_debugger.html

---

## 项目架构

```
crawler → planner → writer → artist_pre → coder → reviewer → artist_post → END
              ↑                        ↓ 不通过
              └── 回退重试(最多3次) ──┘
```

**技术栈**: LangGraph StateGraph + DeepSeek API + FastAPI + WebSocket

**State**: GameFactoryState (TypedDict, 25字段), agent_logs 使用 Annotated[List[dict], operator.add]

**八股 vs 历史路径**:
- 八股 (fill_blank/recite/match/debugger): KB完整数据 → planner短路 → coder骨架模板(零LLM)
- 历史 (cipher/sequence/logic): 全链路LLM

---

## 源码

### 1. main.py

```python
"""AI 游戏工坊 — FastAPI 入口。"""

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

workflow = build_workflow()

from app.knowledge.kb import get_all_events


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "AI 游戏工坊"}


@app.get("/api/cost")
async def get_cost():
    return get_cost_summary()


@app.get("/api/events")
async def list_events(category: str = None):
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
    session_id = str(uuid.uuid4())[:8]
    await ws_manager.connect(session_id, websocket)

    try:
        data = await websocket.receive_json()
        user_input = data.get("event", "").strip()

        if not user_input:
            await ws_manager.send_failed(session_id, "请输入一个计算机历史事件", [])
            return

        await ws_manager.send_progress(session_id, "system", "running", f"收到事件：「{user_input}」")

        state = initial_state(user_input)

        prev_node = None
        prev_node_output = {}
        final_output = {}

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
                    if isinstance(output, dict):
                        final_output.update(output)

        cost = get_cost_summary()
        logger.info(f"生成完成，本次花费: ¥{cost['estimated_cost_rmb']} ({cost['calls']}次LLM调用)")

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

### 2. ws_manager.py

```python
"""WebSocket 连接管理器。"""

from fastapi import WebSocket
from typing import Dict
import json


class WSManager:
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


ws_manager = WSManager()
```

### 3. llm_client.py

```python
"""LLM 客户端 — 统一封装 DeepSeek API 调用。"""

import os
import logging
import time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 120
MAX_RETRIES = 2

_api_key = os.getenv("DEEPSEEK_API_KEY")
if not _api_key:
    raise RuntimeError("DEEPSEEK_API_KEY 环境变量未设置")

client = OpenAI(
    api_key=_api_key,
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    timeout=DEFAULT_TIMEOUT,
)

DEFAULT_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
_cost_records: list[dict] = []


def get_cost_summary() -> dict:
    total_input = sum(r["input_tokens"] for r in _cost_records)
    total_output = sum(r["output_tokens"] for r in _cost_records)
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
    _cost_records.clear()


def _strip_markdown_fence(text: str) -> str:
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
    return {"agent": agent, "action": action, "detail": detail}


def chat(prompt: str, system: str = "", model: str = None, temperature: float = 0.7) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=model or DEFAULT_MODEL,
                messages=messages,
                temperature=temperature,
            )

            content = response.choices[0].message.content
            if content is None:
                logger.warning("LLM returned None content, retrying...")
                continue

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
    return chat(prompt, system=system, model=model, temperature=0.1)
```

### 4. config.py

```python
"""项目配置常量。"""
MAX_REVIEW_RETRIES = 3
```

### 5. graph/state.py

```python
"""LangGraph State — 6 个 Agent 共享的全局状态。"""

from typing import TypedDict, List, Optional, Annotated
import operator
from pydantic import BaseModel, Field


class PuzzleSpec(BaseModel):
    type: str = ""
    answer: str = ""
    hints: list[dict] = Field(default_factory=list)
    max_attempts: int = 3
    items_count: int = 0
    items_labels: list[str] = Field(default_factory=list)


class GameDesignDoc(BaseModel):
    puzzle_spec: PuzzleSpec = Field(default_factory=PuzzleSpec)
    screens: list[dict] = Field(default_factory=list)
    content_map: dict = Field(default_factory=dict)
    visual_spec: dict = Field(default_factory=dict)


class GameFactoryState(TypedDict):
    user_input: str
    search_results: List[dict]
    material_score: float
    material_sufficient: bool
    puzzle_type: str
    puzzle_design: dict
    game_script: str
    script_data: dict
    game_design_doc: Optional[dict]
    script_keywords: List[str]
    game_code: str
    review_passed: bool
    review_feedback: str
    review_details: dict
    retry_count: int
    directions: list
    selected_direction: dict
    styled_code: str
    status: str
    error_message: str
    suggestions: List[str]
    agent_logs: Annotated[List[dict], operator.add]


def initial_state(user_input: str) -> GameFactoryState:
    return GameFactoryState(
        user_input=user_input, puzzle_type="", puzzle_design={},
        search_results=[], material_score=0.0, material_sufficient=False,
        game_script="", script_data={}, game_design_doc=None, script_keywords=[],
        game_code="", review_passed=False, review_feedback="", review_details={},
        retry_count=0, directions=[], selected_direction={}, styled_code="",
        status="running", error_message="", suggestions=[], agent_logs=[],
    )
```

### 6. graph/workflow.py

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

### 7. agents/crawler.py

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

    # Step 3: DeepSeek 兜底
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

### 8. agents/planner.py

```python
"""策划 Agent — CoT 推理选择谜题类型与设计机制。"""

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
  "reasoning_chain": ["步骤1...", "步骤2...", ...],
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

### 9. agents/writer.py

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
  "opening_hook": "标题画面显示的悬念句",

  "puzzle": {
    "type": "cipher|sequence|logic",
    "surface": "谜题表皮",
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
    "title": "小标题",
    "story": "200-300字口语化故事",
    "key_point": "一句话核心收获",
    "fun_fact": "趣闻"
  },

  "victory_line": "通关台词",
  "defeat_line": "失败台词",

  "visual": {
    "palette": ["#0d0a08","#e8702a","#34d399","#e8ddd0","#5a4a3a"],
    "mood": "视觉情绪描述",
    "decorations": ["装饰元素"]
  }
}

【铁律】
- 必须输出合法 JSON，不要 markdown 包裹，不要注释
- puzzle.hints 必须 3 条
- history_facts.story 必须 200-300 字，口语化有画面感
- victory_line 和 defeat_line 各不超过 20 字
- atmosphere 字段优先使用史料中提供的 atmosphere_tags
- visual.decorations 优先使用史料中提供的 key_props
- 所有内容必须基于史料，不编造"""

BAGU_SYSTEM_PROMPT = """你是一个 Python 面试教学游戏的编剧。

【输出格式——Python 八股专用】
{
  "event": "题目名",
  "year": 难度数字(1-4),
  "protagonist": "考点",
  "antagonist": "常见误区",
  "atmosphere": "终端,代码,IDE",
  "opening_hook": "面试场景描述",

  "puzzle": {
    "type": "fill_blank|recite|match|debugger",
    "surface": "代码场景描述",
    "answer": "（从数据中获取）",
    "hints": [{"level":1,"text":"..."}, {"level":2,"text":"..."}, {"level":3,"text":"..."}],
    "max_attempts": 3
  },

  "history_facts": {
    "title": "知识点讲解",
    "story": "200-300字口语化讲解",
    "key_point": "一句话核心考点",
    "fun_fact": "面试官追问"
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
}"""


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
                "story": "（史料解析失败）",
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

### 10. agents/coder.py

```python
"""程序 Agent — 从结构化 GameScript 生成 HTML 游戏。
三路径：骨架模板(零LLM) / 八股LLM / 计算机历史LLM
"""

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
【类名建议】优先使用 .rune（按钮）、.panel（面板）、.glyph-input（输入框）。颜色用 CSS 变量 var(--xxx)。

=== 新手引导与沉浸感 ===
【开场即入戏】标题画面把玩家直接扔进历史现场
【操作引导】第一轮不扣次数 + 即时反馈 + 小字提示 + 10秒自动浮现hint
【让谜题有意义】cipher=破译密电拯救城市 / sequence=拼凑时间线理解历史 / logic=推理真相揭穿传说

=== 游戏循环 ===
1. #screen-title 2. #screen-howto 3. #screen-game 4. 反馈系统(裂纹+背景变暗+逐层提示)
5. #screen-result 6. #screen-history

=== 谜题范式 ===
【cipher — 符文破译台】中央密文 → A-Z字母盘 → 凹槽行 → "点燃符文"检查
【sequence — 时间碎片】4-6个碎片卡片，点击交换 → "重组时间线"
【logic — 星图推演】中央问题核心 → 周围线索节点 → 3-4个选项

=== 代码约束 ===
- 单文件 <!DOCTYPE html>，内嵌 <style> 和 <script>
- 600 行以内，不依赖外部库
- gameState 管理所有状态，HISTORY_FACTS 常量
- showScreen(name) 函数切换画面
- 所有屏幕 id：screen-title/howto/game/result/history
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
    return {"game_code": html, "agent_logs": [agent_log("coder", "skeleton_filled", f"fill_blank, {len(html)} chars")]}

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
    return {"game_code": html, "agent_logs": [agent_log("coder", "skeleton_filled", f"recite, {len(html)} chars")]}

def _match_from_skeleton(state, search_results, script_data) -> dict:
    import json
    skeleton = _load_skeleton("match")
    pg = _extract_puzzle_guide(search_results)
    facts = script_data.get("history_facts", {}) or {}
    html = _fill_common(skeleton, script_data, pg, facts)
    html = html.replace("{{MATCH_PAIRS_JSON}}", json.dumps(pg.get("match_pairs", []), ensure_ascii=False))
    html = html.replace("{{HISTORY_JSON}}", json.dumps(facts, ensure_ascii=False))
    return {"game_code": html, "agent_logs": [agent_log("coder", "skeleton_filled", f"match, {len(html)} chars")]}

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
    return {"game_code": html, "agent_logs": [agent_log("coder", "skeleton_filled", f"debugger, {len(html)} chars")]}


def get_puzzle_meaning(puzzle_type: str, event: str, protagonist: str) -> str:
    templates = {
        "cipher": f"玩家扮演{protagonist or '密码破译员'}，截获了关于「{event}」的关键密文。",
        "sequence": f"关于「{event}」的时间线被打乱了。",
        "logic": f"关于「{event}」流传着几种矛盾的说法。",
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
        puzzle_guide = _extract_puzzle_guide(search_results)
        bagu_data_block = f"""
=== Python 面试题数据 ===
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
        except: script_data = {}

    event = script_data.get("event", state["user_input"])
    puzzle = script_data.get("puzzle", {})
    hints = puzzle.get("hints", [])
    hints_text = "\n".join(f"  L{h.get('level',1)}: {h.get('text','')}" for h in hints) if hints else "  L1: 仔细观察..."

    facts = script_data.get("history_facts", [])

    feedback_block = ""
    if review_feedback:
        feedback_block = f"\n=== 🚨 审查反馈（必须修复）===\n{review_feedback}\n"

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
"""

    prompt = f"""请按契约生成「{puzzle_type}」类型的时间解谜游戏。

【叙事信息】
事件：{script_data.get('event', state['user_input'])}（{script_data.get('year', '')}）
地点：{script_data.get('location', '')}
主角：{script_data.get('protagonist', '')}
氛围：{script_data.get('atmosphere', '像素复古')}
开场悬念：{script_data.get('opening_hook', '')}

【玩家动机】{get_puzzle_meaning(puzzle_type, event, script_data.get('protagonist', ''))}

【谜题参数】类型：{puzzle_type} | 表皮：{puzzle.get('surface', '')}
答案：{puzzle.get('answer', '')} | 最大尝试：{puzzle.get('max_attempts', 3)}

【提示层级】{hints_text}

【历史真相】{json.dumps(facts, ensure_ascii=False) if facts else ''}

【台词】通关：{script_data.get('victory_line', '')} | 失败：{script_data.get('defeat_line', '')}

{feedback_block}直接输出完整 HTML。"""

    try:
        final_prompt = prompt + direction_block + (bagu_data_block if is_bagu else "")
        final_system = bagu_system if is_bagu else SYSTEM_PROMPT
        temp = 0.1 if is_bagu else 0.3
        code = chat(final_prompt, system=final_system, temperature=temp)
        code = _strip_markdown_fence(code)
        if not code.lower().startswith("<!doctype"):
            code = f"<!DOCTYPE html>\n{code}"
        return {"game_code": code, "agent_logs": [agent_log("coder", "code_generated", f"{len(code)} chars")]}
    except Exception as e:
        return {"game_code": f"<!DOCTYPE html><html lang=zh><head><meta charset=UTF-8><title>Error</title></head><body style=background:#0d0a08;color:#e8ddd0;font-family:monospace;display:flex;justify-content:center;align-items:center;height:100vh><div><h1 style=color:#e8702a>生成失败</h1><p>{e}</p></div></body></html>",
            "agent_logs": [agent_log("coder", "error", str(e))]}
```

### 11. agents/reviewer.py

```python
"""审查 Agent — 两阶段验证 + LLM 深度审查 + 反思层。"""

import json, re, logging
from app.graph.state import GameFactoryState
from app.llm_client import agent_log, chat_json, _strip_markdown_fence
from app.config import MAX_REVIEW_RETRIES
from app.knowledge.kb import get_event_names

logger = logging.getLogger("reviewer")

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
1. 可运行性 2. 谜题一致性 3. 历史准确性 4. 完整性 5. 可玩性

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
⚠️ 不要因为'不够好看'拒绝。"""


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
            "agent_logs": [agent_log("reviewer", "mechanical_critical", f"CRITICAL: {len(p1['missing'])} 项")]}
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

### 12. agents/artist_pre.py

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

JSON格式：
{
  "directions": [
    {"name":"...","mood_tags":["..."],"palette":[...],"ui":"...","animation":"...","reference_css":"...","post":{"crt":bool,"particles":"...","atmosphere":"..."}}
  ],
  "selected_index": 0,
  "selection_reasoning": "为什么选这个（引用剧本细节）"
}

要求：3个方向，在交互隐喻/动画节奏/UI形状上明显不同。"""


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
                f"生成{len(directions)}个方向，选择「{selected['name']}」")]
        }
    except Exception as e:
        return {
            "directions": [DEFAULT_FALLBACK], "selected_direction": DEFAULT_FALLBACK,
            "agent_logs": [agent_log("artist_pre", "error_fallback", str(e))]
        }
```

### 13. agents/artist_post.py

```python
"""Artist Post-Processing — BS4 注入 + LLM 补充 CSS。"""

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

    # Step 1: BS4 注入
    styled = inject_palette_vars(styled, direction)
    styled = inject_reference_css(styled, direction)
    styled = inject_screen_transition(styled)
    styled = inject_fonts(styled, direction)
    styled = inject_atmosphere(styled, direction)

    # Step 2: 可选 LLM 微调
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

### 14. agents/coder_templates_bagu.py

*241行，包含 4 个 LLM 提示词模板：DEBUGGER_TEMPLATE, MATCH_TEMPLATE, FILL_BLANK_TEMPLATE, RECITE_TEMPLATE。*
*每个模板详细描述了交互元素、视觉风格、代码结构要求。*
*完整代码见 `backend/app/agents/coder_templates_bagu.py`*

### 15. mcp/web_search.py

```python
"""MCP 工具 — Bing → DuckDuckGo 网页搜索。"""

import urllib.request, urllib.parse, json, html as html_mod, logging
from html.parser import HTMLParser
import re

logger = logging.getLogger("mcp.web_search")


def _search_bing(query: str, max_results: int = 5) -> list[dict]:
    url = f"https://www.bing.com/search?{urllib.parse.urlencode({'q': query})}"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html_text = resp.read().decode("utf-8", errors="ignore")

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

        # Regex fallback
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
    url = f"https://api.duckduckgo.com/?{urllib.parse.urlencode({'q': query, 'format': 'json', 'no_html': 1})}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "time-pixels/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        results = []
        if data.get("AbstractText"):
            results.append({"title": data.get("Heading", query), "snippet": data.get("AbstractText", ""), "url": data.get("AbstractURL", "")})
        for topic in data.get("RelatedTopics", [])[:max_results]:
            if isinstance(topic, dict) and "Text" in topic:
                results.append({"title": topic.get("FirstURL", "").split("/")[-1].replace("_", " "), "snippet": topic.get("Text", ""), "url": topic.get("FirstURL", "")})
        return [r for r in results if r["snippet"]][:max_results]
    except Exception:
        return []


def search(query: str, max_results: int = 5) -> list[dict]:
    results = _search_bing(query, max_results)
    if not results:
        results = _search_ddg(query, max_results)
    return results
```

### 16. knowledge/kb.py

```python
"""共享知识库模块 — 双知识库：计算机历史 + Python 八股。"""

import json, os

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
    if category == "bagu": return BAGU_EVENTS
    if category == "computer_history": return EVENTS
    return EVENTS + BAGU_EVENTS


def get_event_names(category: str = None) -> list[str]:
    if category == "bagu": return [_name(e) for e in BAGU_EVENTS]
    return [_name(e) for e in EVENTS]


def get_event_by_keyword(text: str, category: str = None) -> dict | None:
    pools = []
    if category in (None, "computer_history"): pools.extend(EVENTS)
    if category in (None, "bagu"): pools.extend(BAGU_EVENTS)

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
        if score > best_score: best_score = score; best = event

    return best if best_score >= 1 else None


def event_to_search_results(event: dict) -> list[dict]:
    # 八股：content.annotations → key_facts; puzzle_guide 原样传递
    if "content" in event and "original" in event.get("content", {}):
        content = event["content"]
        return [{
            "title": f"「{event.get('title', event.get('event', ''))}」",
            "content": f"{content.get('translation', '')}\n\n原始代码：\n{content.get('original', '')}",
            "confidence": "high", "verified": True, "source": "verified_knowledge_base",
            "key_facts": content.get("annotations", []),  # ← content.annotations → key_facts
            "atmosphere_tags": event.get("atmosphere_tags", []),
            "key_props": event.get("key_props", []),
            "visual_anchor": event.get("visual_anchor", ""),
            "category": event.get("category", "bagu"),
            "puzzle_guide": event.get("puzzle_guide", {}),  # ← 原样传递
        }]
    # 计算机历史
    facts = event.get("facts", {})
    return [{
        "title": f"「{event['event']}」已验证史料",
        "content": facts.get("story", "") + "\n\n趣闻：" + facts.get("fun_fact", ""),
        "confidence": "high", "verified": True, "source": "verified_knowledge_base",
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

### 17. knowledge/verified_events.json

*1027行，25个计算机历史事件。每事件含 facts(story/fun_fact/time/place/people) + atmosphere_tags + key_props + visual_anchor。*
*完整 JSON 见 `backend/app/knowledge/verified_events.json`*

### 18. knowledge/verified_bagu.json

*809行，8道Python面试题。每题含 content(original/translation/annotations) + puzzle_guide(type + blanks/match_pairs/recite_config/bug_info + hints + scoring + expected_output)。*
*完整 JSON 见 `backend/app/knowledge/verified_bagu.json`*

### 19. schema/game_script.py

```python
"""GameScript Schema — writer Agent 的结构化输出文档。"""

GAME_SCRIPT_SCHEMA = {
    "event": "string", "year": "number", "location": "string",
    "protagonist": "string", "antagonist": "string",
    "core_conflict": "string", "atmosphere": "string",
    "opening_hook": "string",
    "puzzle": {
        "type": "cipher | sequence | logic",
        "surface": "string", "answer": "string",
        "items_count": "number", "items_labels": ["string"],
        "hints": [{"level": 1, "text": "..."}, ...],
        "max_attempts": 3,
    },
    "history_facts": ["string"],
    "victory_line": "string", "defeat_line": "string",
    "visual": {"palette": ["#色值×5"], "mood": "string", "decorations": ["string"]},
}
```

### 20-23. 骨架模板 (skeleton_fill_blank/recite/match/debugger.html)

*4个文件共1090行，使用 {{PLACEHOLDER}} 语法由 coder._fill_common() 替换。关键技术：CSS变量 + .screen切换 + gameState 状态管理 + JSON数据注入。*
*完整 HTML 见 `backend/app/templates/skeleton_*.html`*

---

## 运行方式

```bash
# 后端
cd backend && ..\venv\Scripts\python -m uvicorn app.main:app --reload

# GitHub
https://github.com/hfujw/ai-game-factory
```

## 最近关键修复 (2026-08-03)
1. planner短路: `puzzle_guide.annotations`(不存在)→ `key_facts`(映射自content.annotations)
2. 类型数据校验: fill_blank查blanks / match查match_pairs / recite查recite_config / debugger查bug_info
3. planner SYSTEM_PROMPT 加"类型选择铁律"——禁止返回 "puzzle" 等模糊类型
4. kb.py 显式标注字段映射: `content.annotations → key_facts`, `puzzle_guide` 原样传递
