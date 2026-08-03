# 时光像素 — 核心源文件汇总

---

## 1. app/llm_client.py（126行）

```python
"""LLM 客户端 — 统一封装 DeepSeek API 调用，含超时/重试/内容校验。

所有 Agent 通过这个模块调 LLM，不直接写 openai 调用。
"""

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
        "records": _cost_records[-20:],  # 最近20条
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
    """单轮对话，含自动重试和内容为空保护。

    Returns:
        LLM 文本回复，保证至少是空字符串（不会返回 None）
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            logger.debug("LLM call attempt %d/%d, model=%s, temp=%.2f",
                         attempt + 1, MAX_RETRIES + 1, model or DEFAULT_MODEL, temperature)

            response = client.chat.completions.create(
                model=model or DEFAULT_MODEL,
                messages=messages,
                temperature=temperature,
            )

            content = response.choices[0].message.content
            if content is None:
                logger.warning("LLM returned None content (finish_reason may be 'length'), retrying...")
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
                wait = 2 ** attempt  # 1s, 2s
                logger.warning("LLM call failed (attempt %d/%d): %s, retrying in %ds...",
                               attempt + 1, MAX_RETRIES + 1, e, wait)
                time.sleep(wait)
            else:
                logger.error("LLM call failed after %d attempts: %s", MAX_RETRIES + 1, e)

    raise last_error or RuntimeError("LLM call failed with unknown error")


def chat_json(prompt: str, system: str = "", model: str = None) -> str:
    """调 LLM 返回 JSON 格式文本。内部调用 chat()，temperature 固定 0.1。"""
    return chat(prompt, system=system, model=model, temperature=0.1)
```

---

## 2. app/config.py（4行）

```python
"""项目配置常量。"""

# Agent 重试次数（workflow + reviewer 共用）
MAX_REVIEW_RETRIES = 3
```

---

## 3. app/graph/state.py（76行）

```python
"""LangGraph State — 6 个 Agent 共享的全局状态。

关键修复：agent_logs 使用 Annotated + operator.add，
确保每个 Agent 的日志**追加**而不是互相覆盖。
"""

from typing import TypedDict, List, Optional, Annotated
import operator


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
    script_data: dict           # writer 产出的结构化剧本，artist_pre/coder 消费
    script_keywords: List[str]

    # === 程序 Agent 产出 ===
    game_code: str

    # === 审查 Agent 产出 ===
    review_passed: bool
    review_feedback: str
    review_details: dict
    retry_count: int

    # === 美术 Agent 产出 ===
    directions: list           # artist_pre 产出的 2 个视觉方向
    selected_direction: dict   # 关键词匹配选定的方向
    styled_code: str           # artist_post 产出的最终 HTML

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

---

## 4. app/graph/workflow.py（88行）

```python
"""LangGraph Workflow — 6 Agent 的编排逻辑。

流程：
  crawler → planner → writer → coder → reviewer
  reviewer → coder (审查不通过，回退重试，最多3次)
  reviewer → artist (审查通过)
  reviewer → END (超过重试上限，终止)
  artist → END

早停：
  - crawler 搜不到素材 → 直接返回失败
  - planner 基于史料判断做不了 → 返回失败
"""

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
    """爬虫之后——搜到素材了吗？"""
    if state["material_sufficient"]:
        return "planner"
    return "end_failed"


def should_continue_after_planner(state: GameFactoryState) -> str:
    """策划之后——史料能支撑谜题设计吗？"""
    if state["material_sufficient"]:
        return "writer"
    return "end_failed"


def should_continue_after_reviewer(state: GameFactoryState) -> str:
    """审查之后——通过了吗？要重试吗？"""
    if state["review_passed"]:
        return "artist_post"
    if state["retry_count"] < MAX_REVIEW_RETRIES:
        return "coder"  # 回退重试
    return "end_failed"


def build_workflow() -> StateGraph:
    """构建并返回编译好的 LangGraph 工作流。"""
    workflow = StateGraph(GameFactoryState)

    # 添加节点
    workflow.add_node("crawler", crawler_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("writer", writer_node)
    workflow.add_node("artist_pre", artist_pre_node)
    workflow.add_node("coder", coder_node)
    workflow.add_node("reviewer", reviewer_node)
    workflow.add_node("artist_post", artist_post_node)

    # 设置入口——先搜史料，再策划
    workflow.set_entry_point("crawler")

    # 添加边
    workflow.add_conditional_edges(
        "crawler",
        should_continue_after_crawler,
        {"planner": "planner", "end_failed": END},
    )
    workflow.add_conditional_edges(
        "planner",
        should_continue_after_planner,
        {"writer": "writer", "end_failed": END},
    )
    workflow.add_edge("writer", "artist_pre")      # 剧本 → 视觉设计
    workflow.add_edge("artist_pre", "coder")        # 视觉设计 → 施工
    workflow.add_edge("coder", "reviewer")           # 施工 → 审查
    workflow.add_conditional_edges(
        "reviewer",
        should_continue_after_reviewer,
        {"artist_post": "artist_post", "coder": "coder", "end_failed": END},
    )
    workflow.add_edge("artist_post", END)

    return workflow.compile()
```

---

## 5. app/mcp/web_search.py（84行）

```python
"""MCP 工具 — 网页搜索引擎（自动选择可用后端）。

优先 Bing（国内可访问），fallback DuckDuckGo。
零 API Key，纯 HTTP 请求。
"""

import urllib.request
import urllib.parse
import json
import logging

logger = logging.getLogger("mcp.web_search")


def _search_bing(query: str, max_results: int = 5) -> list[dict]:
    """Bing 搜索。国内可访问，免费。"""
    url = f"https://www.bing.com/search?{urllib.parse.urlencode({'q': query})}"

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        results = []
        # 从 Bing 搜索结果页提取标题和摘要
        import re
        # 匹配 Bing 的搜索结果块
        items = re.findall(r'<li class="b_algo"[^>]*>(.*?)</li>', html, re.DOTALL)
        for item in items[:max_results]:
            title_m = re.search(r'<h2[^>]*><a[^>]*>(.*?)</a>', item, re.DOTALL)
            snippet_m = re.search(r'<p[^>]*>(.*?)</p>', item, re.DOTALL)
            url_m = re.search(r'<a[^>]*href="(https?://[^"]*)"', item)
            if title_m:
                results.append({
                    "title": re.sub(r'<[^>]+>', '', title_m.group(1)),
                    "snippet": re.sub(r'<[^>]+>', '', snippet_m.group(1)) if snippet_m else "",
                    "url": url_m.group(1) if url_m else "",
                })

        logger.info("Bing search '%s': %d results", query[:40], len(results))
        return results[:max_results]

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
    """网页搜索。先 Bing，失败则 DuckDuckGo。返回 [{title, snippet, url}, ...]。"""
    results = _search_bing(query, max_results)
    if not results:
        results = _search_ddg(query, max_results)
    return results
```

---

## 6. app/ws_manager.py（72行）

```python
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
```

---

## 7. app/agents/coder_templates_bagu.py（242行）

```python
# ============================================================
# DEBUGGER_TEMPLATE
# ============================================================
DEBUGGER_TEMPLATE = """
你正在为一个 Python 面试学习游戏生成 HTML/CSS/JS 代码。

【游戏类型】debugger（Bug 定位）
【核心机制】给一段有 bug 的 Python 代码 + 控制台报错信息，玩家先点击可疑行号定位 bug，再选择 bug 类型。两步都正确才算通关。

【必须包含的交互元素】
1. 代码展示区：
   - 带行号的代码编辑器样式，左侧行号可点击
   - 语法高亮（关键字蓝、字符串绿、注释灰、数字橙）
   - 点击行号后该行高亮（蓝色边框），可多选但提示"通常只有一处"

2. 控制台面板：
   - 显示报错信息（Traceback 样式），红色文字
   - 报错信息从 window.__PUZZLE_DATA__.bug_info.traceback 读取

3. Bug 类型选择区：
   - 点击行号后弹出/展开选项卡
   - 选项从 window.__PUZZLE_DATA__.bug_info.options 读取

4. 两步验证逻辑：
   Step 1: 玩家点击行号 → 该行高亮
   Step 2: 玩家选择 bug 类型
   结果：行号正确+类型正确→绿色高亮+修复代码
        行号正确+类型错误→黄色提示
        行号错误→红色提示

5. 修复展示：通关后原代码和修复代码并排对比（diff 样式）

6. 提示系统：3 层 hint，使用一次扣分

【视觉风格】深色终端 #0d1117，VS Code 风格
【代码结构要求】原生 HTML/CSS/JS，数据从 window.__PUZZLE_DATA__ 读取
"""

# ============================================================
# MATCH_TEMPLATE
# ============================================================
MATCH_TEMPLATE = """
你正在为一个 Python 面试学习游戏生成 HTML/CSS/JS 代码。

【游戏类型】match（概念配对）
【核心机制】左侧为 Python 概念/代码片段，右侧为机制描述。玩家通过拖拽或点击将左右配对。

【必须包含的交互元素】
1. 左右两栏：概念卡片 vs 机制描述卡片
2. 连线绘制：SVG 绘制，点击左→点击右→连线
3. 配对校验：正确→绿色实线+锁定，错误→红色虚线+抖动
4. 知识卡片：配对正确后可查看详细解释
5. 完成统计：正确率+用时+连击奖励

【视觉风格】深色终端 #0d1117
【代码结构要求】原生 HTML/CSS/JS，数据从 window.__PUZZLE_DATA__ 读取
"""

# ============================================================
# FILL_BLANK_TEMPLATE
# ============================================================
FILL_BLANK_TEMPLATE = """
你正在为一个 Python 面试学习游戏生成 HTML/CSS/JS 代码。

【游戏类型】fill_blank（代码填空）
【核心机制】给一段有 ___ 的 Python 代码，玩家点击空位输入关键字/API/参数。

【必须包含的交互元素】
1. 代码展示区：带行号+语法高亮（关键字蓝#58a6ff、字符串绿#7ee787、注释灰#8b949e）
   空位用闪烁 ___ 表示

2. 输入与校验：点击空位→内联替换为<input>，Enter 提交，比对正确答案

3. 三层反馈：
   - 填错→红色+模拟 Python 报错
   - 对但非最优→黄色+warning 提示
   - 对且最优→绿色+终端输出 success+复杂度

4. 终端面板：等宽字体，#0d1117

5. 提示系统：3 层 hint，使用扣分

【视觉风格】深色终端 #0d1117，VS Code 语法高亮
【代码结构要求】原生 HTML/CSS/JS，数据从 window.__PUZZLE_DATA__ 读取
"""

# ============================================================
# RECITE_TEMPLATE
# ============================================================
RECITE_TEMPLATE = """
你正在为一个 Python 面试学习游戏生成 HTML/CSS/JS 代码。

【游戏类型】recite（代码默写 — 剥洋葱式）
【核心机制】根据需求描述在"伪 IDE"里写出代码。L1(70%骨架)/L2(30%)/L3(裸写)。

【骨架自动生成规则】前端 JS 实现：
1. 读 data.content.original 完整代码
2. 保留 Python 关键字+内置函数名
3. 抽空用户自定义名→___
4. L1 保留70% / L2 保留30% / L3 裸写

【必须包含的交互元素】
1. 需求区+伪 IDE（行号+代码行+键盘输入+Tab/Enter）
2. 实时校验：正则结构模式（def/func/for/in/yield/@）+关键字检测
3. 难度切换：L1/L2/L3 按钮
4. 得分：base_score + per_error_penalty + segment_bonus

【视觉风格】同 fill_blank
【代码结构要求】数据从 window.__PUZZLE_DATA__ 读取
"""
```
