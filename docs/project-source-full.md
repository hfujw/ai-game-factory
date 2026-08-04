# 时光像素 — 完整源码（一字不差）

> 2026-08-04 · 最终版 · 10个后端文件 + 12个前端文件


---

## backend/requirements.txt

```
fastapi>=0.111.0
uvicorn[standard]>=0.30.1
openai>=1.35.0
python-dotenv>=1.0.1
websockets>=12.0
pytest>=8.2.0
httpx>=0.27.0
beautifulsoup4>=4.12.0
```

---

## backend/app/main.py

```
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

# 编译 LangGraph 工作流（启动时执行一次）
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
```

---

## backend/app/ws_manager.py

```
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
```

---

## backend/app/llm_client.py

```
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
                max_tokens=8192,  # 防止 HTML 代码被截断
            )

            content = response.choices[0].message.content
            if content is None:
                logger.warning("LLM returned None content (finish_reason may be 'length'), retrying...")
                continue

            # DEBUG: 完整 prompt 和 response 写到文件日志
            logger.debug("LLM REQUEST — system=%d chars, user=%d chars, temp=%.2f",
                        len(system), len(prompt), temperature)
            logger.debug("LLM SYSTEM:\n%s", system[:3000])
            logger.debug("LLM PROMPT:\n%s", prompt[:5000])
            logger.debug("LLM RESPONSE:\n%s", content[:5000])

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

## backend/app/tools.py

```
"""5个工具 — 编排LLM按需调用。每个工具独立、无状态、可单独测试。"""

import json
import logging
from app.llm_client import chat, chat_json, _strip_markdown_fence
from app.mcp.web_search import search as bing_search

logger = logging.getLogger(__name__)

# ── 素材过滤 ──
_AD_NOISE = {"广告", "推广", "促销", "优惠", "团购", "门票", "攻略", "旅游团",
             "酒店", "民宿", "租车", "代购", "加盟", "招商", "股票", "基金"}


def _filter_noise(results: list[dict]) -> list[dict]:
    return [r for r in results if not any(kw in r.get("title", "") + r.get("snippet", "") for kw in _AD_NOISE)]


# ═══════════════════════════════════════════════════════════
# 工具 1: search
# ═══════════════════════════════════════════════════════════

SEARCH_SYSTEM_PROMPT = """你是搜索query优化专家。把用户想搜的内容转成最优的搜索关键词。只输出query，不要解释。"""


def tool_search(query: str, reason: str = "", depth: str = "quick", existing_material: list[dict] = None) -> dict:
    """搜素材。AI生成的query + AI解释为什么搜。"""
    max_results = 5 if depth == "quick" else 10
    raw = bing_search(query, max_results=max_results)
    filtered = _filter_noise(raw) if raw else []

    # 去重
    if existing_material:
        seen = {r.get("title", "") for r in existing_material}
        filtered = [r for r in filtered if r.get("title", "") not in seen]

    logger.info("工具=search | query='%s' | depth=%s | 结果=%d", query, depth, len(filtered))

    return {
        "tool": "search",
        "query": query,
        "reason": reason,
        "results": filtered,
        "count": len(filtered),
    }


# ═══════════════════════════════════════════════════════════
# 工具 2: design
# ═══════════════════════════════════════════════════════════

DESIGN_SYSTEM_PROMPT = """你是信息设计师。分析素材，决定用什么视觉形式呈现。

可选组件：
- timeline（时间轴）— 有明确时间顺序
- comparison（对比表）— 两个及以上对象对比
- cards（卡片集）— 人物、概念、独立条目
- flowchart（流程图）— 因果关系、步骤过程
- portrait（人物画像）— 以人物为核心
- datapanel（数据面板）— 有具体数据
- encyclopedia（百科条目）— 概念解释

你可以单选或多选组合。一个主题通常需要2-3个组件搭配。

输出JSON：
{
  "components": ["timeline", "cards"],
  "rationale": "为什么选这些（引用素材中的具体证据）",
  "structure": "组件排列方式（如：顶部时间轴，下方2列卡片）",
  "visual_hint": "配色方向和情绪基调（如：秦汉黑红金、严肃厚重）"
}"""


def tool_design(material: list[dict]) -> dict:
    """分析素材，决定用什么叙事形式。"""
    if not material:
        return {"components": ["encyclopedia"], "rationale": "无素材，仅做百科式展示",
                "structure": "单列百科条目", "visual_hint": "简洁中性"}

    brief = "\n\n".join(
        f"[{i+1}] {r.get('title','')}: {r.get('snippet', r.get('content',''))[:300]}"
        for i, r in enumerate(material[:8])
    )

    try:
        result = chat_json(f"素材：\n{brief}", system=DESIGN_SYSTEM_PROMPT)
        result = _strip_markdown_fence(result)
        design = json.loads(result)
        logger.info("工具=design | 组件=%s", design.get("components", []))
        return design
    except Exception as e:
        logger.warning("design失败: %s", e)
        return {"components": ["encyclopedia"], "rationale": f"LLM异常({e})，降级为百科条目",
                "structure": "单列", "visual_hint": "默认"}


# ═══════════════════════════════════════════════════════════
# 工具 3: compose
# ═══════════════════════════════════════════════════════════

COMPOSE_SYSTEM_PROMPT = """你是叙事文案写手。每个事实性陈述必须标注来源和可信度。不确定的标注'据传'或'说法不一'。不编造数字/年份/人名。

输出JSON：
{
  "title": "页面标题",
  "subtitle": "副标题",
  "blocks": [
    {
      "component": "timeline",
      "position": 1,
      "html_hint": "时间轴节点，50字以内",
      "claims": [
        {"text": "秦始皇统一六国于前221年", "source": "search_1", "confidence": "high"},
        {"text": "征发民夫约百万", "source": "search_5", "confidence": "medium", "note": "单一来源，史记可能夸大"}
      ]
    }
  ],
  "fact_notes": "哪些信息确定、哪些有争议"
}"""


def tool_compose(material: list[dict], design: dict) -> dict:
    """写叙事文案+来源标注。"""
    brief = "\n\n".join(
        f"[来源{i+1}] {r.get('title','')}: {r.get('snippet', r.get('content',''))[:400]}"
        for i, r in enumerate(material[:8])
    )

    prompt = f"""素材：{brief}

设计：{json.dumps(design, ensure_ascii=False)}

为每个组件写内容。每个数字/年份/人名必须标注来源。"""

    try:
        result = chat_json(prompt, system=COMPOSE_SYSTEM_PROMPT)
        result = _strip_markdown_fence(result)
        content = json.loads(result)
        logger.info("工具=compose | blocks=%d", len(content.get("blocks", [])))
        return content
    except Exception as e:
        logger.warning("compose失败: %s", e)
        return {"title": "生成失败", "subtitle": str(e), "blocks": [], "fact_notes": ""}


# ═══════════════════════════════════════════════════════════
# 工具 4: render
# ═══════════════════════════════════════════════════════════

RENDER_SYSTEM_PROMPT = """生成一个好看的交互式HTML页面。

【结构】
{design}

【内容】
{content}

【视觉方向】
{visual}

【规则】
- 450行以内，CSS精简，动画最多1个
- 不用外部库
- 必须有</html>
- 直接输出完成HTML，不要```包裹"""


def tool_render(design: dict, content: dict, visual: dict = None) -> dict:
    """生成HTML。返回html字符串+完整性标记。"""
    visual = visual or {}
    visual_block = ""
    if visual.get("reference_css"):
        visual_block = f"参考CSS：\n{visual['reference_css'][:800]}"
    if visual.get("palette"):
        visual_block += f"\n色板：{', '.join(visual['palette'])}"

    prompt = RENDER_SYSTEM_PROMPT.format(
        design=json.dumps(design, ensure_ascii=False, indent=2),
        content=json.dumps(content, ensure_ascii=False, indent=2),
        visual=visual_block or "由你自由发挥",
    )

    try:
        code = chat(prompt, system="你是前端工程师。直接输出完整HTML。", temperature=0.3)
        code = _strip_markdown_fence(code)
        if not code.lower().startswith("<!doctype"):
            code = f"<!DOCTYPE html>\n{code}"

        is_complete = "</html>" in code
        logger.info("工具=render | %d chars | 完整=%s", len(code), is_complete)
        return {"html": code, "complete": is_complete, "length": len(code)}
    except Exception as e:
        logger.error("render失败: %s", e)
        return {"html": f"<!DOCTYPE html><html><body><h1>生成失败</h1><p>{e}</p></body></html>",
                "complete": True, "length": 0, "error": str(e)}


# ═══════════════════════════════════════════════════════════
# 工具 5: verify
# ═══════════════════════════════════════════════════════════

def tool_verify(html: str, content: dict, _design: dict = None) -> dict:
    """审查：硬规则(纯Python) + 可用Playwright时真执行。"""
    issues = []

    # Phase 1: 硬规则
    if "</html>" not in html:
        issues.append({"severity": "critical", "category": "incomplete",
                       "description": "HTML不完整，缺少</html>", "fix": "render时精简CSS，确保输出完整"})
    if "<script>" not in html.lower() and "<script " not in html.lower():
        issues.append({"severity": "warning", "category": "no_js",
                       "description": "缺少<script>标签，页面无交互", "fix": "添加至少一个<script>标签"})
    if "{visual_css}" in html or "{{" in html:
        issues.append({"severity": "critical", "category": "placeholder",
                       "description": "HTML中包含未填充的占位符", "fix": "render时检查所有{{}}是否已替换"})

    # Phase 2: Playwright真执行（尝试）
    playwright_ok = False
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            js_errors = []
            page.on("pageerror", lambda err: js_errors.append(str(err)))
            page.set_content(html)
            page.wait_for_timeout(800)
            if js_errors:
                issues.append({"severity": "warning", "category": "js_error",
                               "description": f"JS报错: {'; '.join(js_errors[:3])}",
                               "fix": "修复JS语法错误"})
            browser.close()
            playwright_ok = True
    except Exception as e:
        logger.debug("Playwright不可用: %s", e)

    # Phase 3: 事实核查（有content时）
    if content and content.get("blocks"):
        claims_with_source = 0
        total_claims = 0
        for block in content.get("blocks", []):
            for claim in block.get("claims", []):
                total_claims += 1
                if claim.get("source") and claim.get("confidence") != "unknown":
                    claims_with_source += 1
        if total_claims > 0 and claims_with_source / total_claims < 0.5:
            issues.append({"severity": "warning", "category": "fact_check",
                           "description": f"仅有{claims_with_source}/{total_claims}个claim有来源",
                           "fix": "compose时给每个数字/年份标注来源"})

    # 判决
    critical = [i for i in issues if i["severity"] == "critical"]
    passed = len(critical) == 0

    rollback_target = None
    if not passed:
        if any("incomplete" in i["category"] or "placeholder" in i["category"] for i in critical):
            rollback_target = "render"
        else:
            rollback_target = "compose"

    logger.info("工具=verify | passed=%s | issues=%d | playwright=%s", passed, len(issues), playwright_ok)
    return {"passed": passed, "issues": issues, "rollback_target": rollback_target,
            "playwright_ok": playwright_ok}
```

---

## backend/app/agents/orchestrator.py

```
"""编排 Agent — 思考→行动→反馈 主循环。

拿到用户输入后，不按固定流程。每一步都是：
1. 🤔 思考：告诉用户"我打算干什么、为什么"
2. 🔧 行动：调用工具
3. 📊 反馈：展示结果
4. 🔄 循环：根据反馈决定下一步
"""

import json
import logging
from app.llm_client import chat_json, _strip_markdown_fence, agent_log
from app.tools import tool_search, tool_design, tool_compose, tool_render, tool_verify
from app.knowledge.kb import get_event_by_keyword, event_to_search_results

logger = logging.getLogger(__name__)

# ── 预算（估算） ──
TOOL_COST = {"search": 0.03, "design": 0.05, "compose": 0.08, "render": 0.15, "verify": 0.05}

ORCHESTRATOR_SYSTEM_PROMPT = """你是一个视觉叙事引擎。用户给你一个主题，你生成一个好看的HTML页面。

【工具】
- search(query, reason) → 搜素材
- design → 分析素材，决定用什么叙事形式
- compose → 写文案，每个事实标来源
- render → 生成HTML
- verify → Playwright审查

【硬规则】
- render之后必须verify
- verify说过 → 停止，输出final
- verify说不过 → 退给render/compose/design，你来决定退给谁
- 最多15步，总预算¥1，最多搜5次
- HTML截断(缺</html>) → 自动失败，必须重render
- 同一工具连续3次失败 → 必须换策略

【决策指南】
- 先search还是先design？简单主题可以直接design，复杂主题先search
- 素材够了就别再search了
- verify说"visual不好看"→退render；"来源不足"→退compose；"形式不合适"→退design
- 预算紧张时用最简方案

输出JSON：{"thought":"当前情况+我决定做什么+为什么","tool":"search|design|compose|render|verify","params":{}}"""


async def orchestrator_node(state: dict) -> dict:
    """主循环：思考→行动→反馈→循环。思考先推到前端，用户看到后AI再行动。"""
    user_input = state.get("user_input", "")
    push = state.get("_push")

    ctx = {
        "user_input": user_input,
        "material": [],
        "design": None,
        "content": None,
        "html": "",
        "visual": None,
        "steps": 0,
        "max_steps": 15,
        "budget_spent": 0.0,
        "budget_total": 1.0,
        "passed": False,
        "issues": [],
        "tool_history": [],
    }

    kb_event = get_event_by_keyword(user_input)
    if kb_event:
        ctx["material"].extend(event_to_search_results(kb_event))

    while ctx["steps"] < ctx["max_steps"] and ctx["budget_spent"] < ctx["budget_total"]:

        # 1. 让LLM决定下一步
        decision = _decide(ctx)

        # 2. ⚡ 思考先推到前端（await 确保用户看到了）
        thought = decision.get("thought", "")
        tool_name = decision.get("tool", "search")
        if push:
            await push({"type": "thinking", "step": ctx["steps"] + 1, "thought": thought,
                        "tool": tool_name, "budget": ctx["budget_spent"]})

        # 3. 等 LLM 回复时也推一条"进行中"
        if push and tool_name in ("search", "design", "compose", "render", "verify"):
            await push({"type": "tool_result", "step": ctx["steps"] + 1, "tool": tool_name,
                        "summary": "进行中...", "budget": ctx["budget_spent"]})

        # 4. 执行工具
        result = _execute_tool(tool_name, decision.get("params", {}), ctx)

        # 5. 推送结果
        ctx["steps"] += 1
        ctx["tool_history"].append({"step": ctx["steps"], "thought": thought,
                                     "tool": tool_name, "result_summary": _summarize(result)})
        if push:
            await push({"type": "tool_result", "step": ctx["steps"], "tool": tool_name,
                        "summary": _summarize(result), "budget": ctx["budget_spent"]})

        # 5. 硬检查
        if tool_name == "render":
            if not result.get("complete"):
                ctx["issues"].append("render自动失败：HTML截断")
                result["auto_fail"] = True
            ctx["last_render"] = result

        if tool_name == "verify":
            ctx["passed"] = result.get("passed", False)
            ctx["issues"] = result.get("issues", [])
            if ctx["passed"]:
                logger.info("编排=通过！%d步 ¥%.2f", ctx["steps"], ctx["budget_spent"])
                if push:
                    await push({"type": "complete", "html": ctx.get("html", ""),
                                "steps": ctx["steps"], "budget": ctx["budget_spent"]})
                return {"status": "success", "html": ctx.get("html", ""),
                        "steps": ctx["steps"], "budget": ctx["budget_spent"],
                        "tool_history": ctx["tool_history"]}

        # 6. 连续失败检测
        recent = [h for h in ctx["tool_history"][-3:] if h["tool"] == tool_name]
        if len(recent) >= 3 and tool_name in ("render", "compose", "design"):
            logger.warning("%s连续失败3次，标记需要换策略", tool_name)
            ctx["force_strategy_change"] = True

    # 循环结束但没通过
    logger.info("编排=超限 %d步 ¥%.2f passed=%s", ctx["steps"], ctx["budget_spent"], ctx["passed"])
    if push:
        await push({"type": "failed", "reason": f"尝试{ctx['steps']}次后仍未通过" if not ctx["passed"] else "超出步数/预算",
                    "steps": ctx["steps"], "budget": ctx["budget_spent"]})
    return {"status": "failed", "steps": ctx["steps"], "budget": ctx["budget_spent"],
            "issues": ctx["issues"], "tool_history": ctx["tool_history"]}


def _decide(ctx: dict) -> dict:
    """让LLM决定：下一步干什么。"""
    # 构建简洁上下文
    summary = f"""主题：{ctx['user_input']}
步骤：{ctx['steps']}/{ctx['max_steps']} | 预算：¥{ctx['budget_spent']:.2f}/¥{ctx['budget_total']:.0f}
已有素材：{len(ctx['material'])}条 | 搜索次数：{sum(1 for h in ctx['tool_history'] if h['tool']=='search')}
已设计：{ctx['design'] is not None} | 已写文案：{ctx['content'] is not None}
HTML长度：{len(ctx.get('html',''))}字符 | 上次验证：{'通过' if ctx['passed'] else '未通过'}
最近工具：{', '.join(h['tool'] for h in ctx['tool_history'][-5:]) if ctx['tool_history'] else '无'}
最近问题：{ctx['issues'][:3] if ctx['issues'] else '无'}
"""

    if ctx.get("force_strategy_change"):
        summary += "\n⚠️ 连续失败！必须换策略，不能重试同一个工具。"

    try:
        result = chat_json(summary, system=ORCHESTRATOR_SYSTEM_PROMPT)
        result = _strip_markdown_fence(result)
        return json.loads(result)
    except Exception as e:
        logger.warning("编排决策失败: %s, 降级为search", e)
        return {"thought": f"决策异常({e})，先搜素材", "tool": "search",
                "params": {"query": ctx["user_input"], "reason": "初始搜索", "depth": "quick"}}


def _execute_tool(tool_name: str, params: dict, ctx: dict) -> dict:
    """执行工具调用，更新ctx。"""
    cost = TOOL_COST.get(tool_name, 0.05)
    ctx["budget_spent"] += cost

    if tool_name == "search":
        result = tool_search(
            query=params.get("query", ctx["user_input"]),
            reason=params.get("reason", ""),
            depth=params.get("depth", "quick"),
            existing_material=ctx["material"],
        )
        ctx["material"].extend(result.get("results", []))
        return result

    elif tool_name == "design":
        result = tool_design(ctx["material"])
        ctx["design"] = result
        return result

    elif tool_name == "compose":
        result = tool_compose(ctx["material"], ctx["design"] or {})
        ctx["content"] = result
        return result

    elif tool_name == "render":
        result = tool_render(ctx["design"] or {}, ctx["content"] or {}, ctx.get("visual"))
        if result.get("html"):
            ctx["html"] = result["html"]
        return result

    elif tool_name == "verify":
        result = tool_verify(ctx.get("html", ""), ctx.get("content") or {}, ctx.get("design"))
        return result

    return {"error": f"未知工具: {tool_name}"}


def _summarize(result: dict) -> str:
    """工具结果的一句话摘要。"""
    tool = result.get("tool", "")
    if tool == "search":
        return f"找到{result.get('count', 0)}条结果"
    elif tool == "design":
        return f"选定组件: {', '.join(result.get('components', []))}"
    elif tool == "compose":
        return f"生成{len(result.get('blocks', []))}个内容块"
    elif tool == "render":
        return f"{result.get('length', 0)}字符, 完整={'✓' if result.get('complete') else '✗'}"
    elif tool == "verify":
        return f"{'✓ 通过' if result.get('passed') else '✗ ' + str(len(result.get('issues', [])))+'个问题'}"
    return str(result.get("error", ""))
```

---

## backend/app/knowledge/kb.py

```
"""统一知识库 — 加载全部示例话题作为搜索素材。"""

import json
import os

_KB_DIR = os.path.dirname(__file__)

def _name(event: dict) -> str:
    """统一获取事件名。"""
    return event.get("event", event.get("title", ""))


def _prep_keywords(event: dict):
    """预归一化 keywords 和 aliases。"""
    for key in ("keywords", "aliases"):
        vals = event.get(key, [])
        event[key] = [v.lower().strip() for v in vals if v]

# 加载全部示例话题（文件不存在时降级为空列表）
try:
    with open(os.path.join(_KB_DIR, "verified_events.json"), "r", encoding="utf-8") as f:
        EVENTS = json.load(f)
    for e in EVENTS:
        _prep_keywords(e)
except Exception:
    EVENTS = []

_BAGU_PATH = os.path.join(_KB_DIR, "verified_bagu.json")
BAGU_EVENTS = []
if os.path.exists(_BAGU_PATH):
    try:
        with open(_BAGU_PATH, "r", encoding="utf-8") as f:
            bagu_data = json.load(f)
            BAGU_EVENTS = bagu_data.get("events", [])
        for e in BAGU_EVENTS:
            _prep_keywords(e)
    except Exception:
        pass

ALL_EVENTS = EVENTS + BAGU_EVENTS


def get_all_events(category: str = None) -> list[dict]:
    """返回示例话题列表。category 可选过滤：'computer_history' / 'bagu' / None(全部)。"""
    if category == "bagu":
        return BAGU_EVENTS
    if category == "computer_history":
        return EVENTS
    return ALL_EVENTS


def get_event_names(category: str = None) -> list[str]:
    """返回话题名列表。"""
    if category == "bagu":
        return [_name(e) for e in BAGU_EVENTS]
    if category == "computer_history":
        return [_name(e) for e in EVENTS]
    return [_name(e) for e in ALL_EVENTS]


def get_event_by_keyword(text: str, category: str = None) -> dict | None:
    """关键词匹配。先精确(别名/全名)→再子串(keywords/name)。"""
    pools = []
    if category in (None, "computer_history"):
        pools.extend(EVENTS)
    if category in (None, "bagu"):
        pools.extend(BAGU_EVENTS)

    query = text.lower().strip()
    best = None
    best_score = 0

    for event in pools:
        score = 0
        for alias in event.get("aliases", []):
            if alias == query:
                score += 3
            elif query in alias or alias in query:
                score += 1.5
        event_name = _name(event).lower()
        if query == event_name:
            score += 3
        elif query in event_name or event_name in query:
            score += 1.5
        for kw in event.get("keywords", []):
            if kw in query or query in kw:
                score += 0.5
        if score > best_score:
            best_score = score
            best = event

    return best if best_score >= 1 else None


def event_to_search_results(event: dict) -> list[dict]:
    """统一处理所有事件为 search_results 格式。"""
    title = event.get("event", event.get("title", ""))
    content_parts = []
    key_facts = []

    if "content" in event and "original" in event.get("content", {}):
        content = event["content"]
        if content.get("translation"):
            content_parts.append(content["translation"])
        content_parts.append(f"原始代码：\n{content.get('original', '')}")
        key_facts = content.get("annotations", [])
    else:
        facts = event.get("facts", {})
        if facts.get("story"):
            content_parts.append(facts["story"])
        if facts.get("fun_fact"):
            content_parts.append(f"趣闻：{facts['fun_fact']}")
        key_facts = [
            f"时间：{facts.get('time', '')}",
            f"地点：{facts.get('place', '')}",
            f"人物：{'、'.join(facts.get('people', []))}",
        ]

    return [{
        "title": f"「{title}」",
        "content": "\n\n".join(content_parts),
        "confidence": "high",
        "verified": True,
        "source": "verified_knowledge_base",
        "key_facts": key_facts,
        "atmosphere_tags": event.get("atmosphere_tags", []),
        "key_props": event.get("key_props", []),
        "visual_anchor": event.get("visual_anchor", ""),
        "category": "computer_history",
    }]
```

---

## backend/app/mcp/web_search.py

```
"""MCP 工具 — 网页搜索引擎（自动选择可用后端）。

优先 Bing（国内可访问），fallback DuckDuckGo。
零 API Key，纯 HTTP 请求。
"""

import urllib.request
import urllib.parse
import json
import html as html_mod
import logging

logger = logging.getLogger("mcp.web_search")


def _search_bing(query: str, max_results: int = 5) -> list[dict]:
    """Bing 搜索。用 html.parser 替代纯正则，更稳定。"""
    url = f"https://www.bing.com/search?{urllib.parse.urlencode({'q': query})}"

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html_text = resp.read().decode("utf-8", errors="ignore")

        results = []
        import re
        from html.parser import HTMLParser

        class BingParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.results = []
                self.in_item = False; self.in_title = False; self.in_snippet = False
                self.title = ""; self.snippet = ""; self.url = ""
                self.depth = 0; self.snip_depth = 0

            def handle_starttag(self, tag, attrs):
                attrs_dict = dict(attrs)
                cls = attrs_dict.get('class', '')
                if tag == 'li' and 'b_algo' in cls:
                    self.in_item = True; self.title = ""; self.snippet = ""; self.url = ""
                if self.in_item and tag == 'h2':
                    self.in_title = True
                if self.in_item and tag == 'p':
                    self.in_snippet = True; self.snip_depth = 0
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

        # Fallback: if parser got nothing, try regex
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

        # Filter Bing internal links, dedup
        seen = set()
        filtered = []
        for r in parser.results:
            url = r.get("url", "")
            if url and ('bing.com' in url or 'microsoft.com/bing' in url): continue
            key = r["title"]
            if key not in seen:
                seen.add(key); filtered.append(r)

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
    """网页搜索。先 Bing，失败则 DuckDuckGo。返回 [{title, snippet, url}, ...]。"""
    results = _search_bing(query, max_results)
    if not results:
        results = _search_ddg(query, max_results)
    return results
```

---

## frontend/package.json

```
{
  "name": "time-pixels",
  "private": true,
  "type": "module",
  "scripts": { "dev": "vite", "build": "vite build", "preview": "vite preview" },
  "dependencies": {
    "framer-motion": "^12.0.0",
    "lucide-react": "^0.400.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.4.0",
    "vite": "^5.4.0"
  }
}
```

---

## frontend/vite.config.js

```
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
})
```

---

## frontend/src/main.jsx

```
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

---

## frontend/src/index.css

```
@tailwind base;
@tailwind components;
@tailwind utilities;

* { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif; }

/* ── 你的 hero 动画（不动）── */
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
/* ── 游戏面板相关动画 ── */
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

/* ── 滚动条 ── */
::-webkit-scrollbar { width:3px; }
::-webkit-scrollbar-track { background:transparent; }
::-webkit-scrollbar-thumb { background:rgba(255,255,255,0.08); border-radius:10px; }
```

---

## frontend/src/App.jsx

```
import { useState, useRef, useEffect } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import RevealLayer from './components/RevealLayer'
import { GamePanel } from './components/StoryPanel'
import { AgentBuds } from './components/AgentBuds'
import { SearchBubble } from './components/SearchBubble'
import { EventTags } from './components/EventTags'
import { DecisionLog } from './components/DecisionLog'
import { FailureNotice } from './components/FailureNotice'
import { ErrorBoundary } from './components/ErrorBoundary'

const BG_BASE   = '/images/base.jpg'
const BG_REVEAL = '/images/reveal.jpg'

const TOOLS = [
  { key:'search',   name:'搜索' },
  { key:'design',   name:'设计' },
  { key:'compose',  name:'写文案' },
  { key:'render',   name:'生成' },
  { key:'verify',   name:'审查' },
]

export default function App() {
  const { statuses, messages, gameCode, error, isGenerating, sendEvent, cancel, dismiss } = useWebSocket()

  // ── 光标聚光灯（同 lithos-replica）──
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

  const completedTools = Object.values(statuses).filter(s => s.status==='done').length

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
          <div className="absolute z-50 top-[8%] left-0 right-0 flex flex-col items-center text-center px-5 pointer-events-none">
            <h1 className="text-white leading-[0.95]">
              <span className="block text-5xl sm:text-7xl md:text-8xl font-semibold hero-anim hero-reveal"
                style={{ fontFamily:"'PingFang SC','Noto Serif SC','STSong',serif", letterSpacing:'0.04em', animationDelay:'0.25s' }}>
                时光像素
              </span>
              <span className="block text-lg sm:text-2xl md:text-3xl font-light mt-3 text-white/45 hero-anim hero-reveal"
                style={{ letterSpacing:'0.22em', animationDelay:'0.42s' }}>
                以 光 为 笔  ·  以 史 为 墨
              </span>
            </h1>
          </div>

          {/* z-50: 搜索框 + 快捷标签 + 工具状态灯 */}
          <div className="absolute z-50 top-[28%] left-1/2 -translate-x-1/2 w-[90vw] max-w-lg pointer-events-auto flex flex-col items-center gap-4">
            <SearchBubble onGenerate={sendEvent} isGenerating={isGenerating} onCancel={cancel} />
            <div className="flex flex-wrap justify-center gap-2">
              {['秦始皇修长城','Turing 破译 Enigma','Python 装饰器','郑和下西洋','世界杯历届冠军'].map(t => (
                <button key={t} onClick={() => sendEvent(t)} disabled={isGenerating}
                  className="px-3 py-1 text-[11px] text-white/25 hover:text-white/55 bg-white/[0.02] hover:bg-white/[0.06] border border-white/[0.04] hover:border-white/[0.10] rounded-full transition-all disabled:opacity-20">
                  {t}
                </button>
              ))}
            </div>
            <AgentBuds agents={TOOLS} statuses={statuses} />
          </div>

          {/* z-50: 事件标签 */}
          <div className="absolute z-50 inset-0 pointer-events-none">
            <EventTags onSelect={sendEvent} disabled={isGenerating} />
          </div>

          {/* z-50: 生成结果展示 */}
          <GamePanel
            visible={!!gameCode}
            gameCode={gameCode}
            isGenerating={isGenerating}
            agentCount={TOOLS.length}
            doneCount={completedTools}
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
          <DecisionLog messages={messages} autoCollapse={!!gameCode} />

        </section>
      </div>
    </ErrorBoundary>
  )
}
```

---

## frontend/src/hooks/useWebSocket.js

```
import { useState, useRef, useCallback } from 'react'

// HTTPS 环境自动用 wss
const WS_URL = `ws${location.protocol === 'https:' ? 's' : ''}://${window.location.host}/ws/generate`

export function useWebSocket() {
  const [statuses, setStatuses] = useState({})
  const [messages, setMessages] = useState([])
  const [gameCode, setGameCode] = useState(null)
  const [error, setError] = useState(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const wsRef = useRef(null)
  const logIdRef = useRef(0)
  const generatingRef = useRef(false)  // 避免 stale closure

  const lastSend = useRef(0)

  const sendEvent = useCallback((eventText) => {
    if (!eventText.trim()) return

    // 防抖：1秒内不重复触发
    const now = Date.now()
    if (now - lastSend.current < 1000) return
    lastSend.current = now

    // 关闭旧的 socket
    if (wsRef.current) {
      wsRef.current.close()
    }

    // Reset state
    setStatuses({})
    setMessages([])
    setGameCode(null)
    setError(null)
    setIsGenerating(true)
    generatingRef.current = true

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      ws.send(JSON.stringify({ event: eventText }))
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        switch (data.type) {
          case 'agent_progress':
            setStatuses(prev => ({
              ...prev,
              [data.agent]: {
                status: data.status,
                message: data.message,
                retries: data.data?.retry ?? (prev[data.agent]?.retries || 0),
              },
            }))
            setMessages(prev => [...prev, {
              id: ++logIdRef.current,
              time: new Date().toLocaleTimeString(),
              agent: data.agent,
              detail: data.message,
            }])
            break

          case 'game_ready':
            setGameCode(data.game_code)
            setIsGenerating(false)
            generatingRef.current = false
            break

          case 'generation_failed':
            setError({
              reason: data.reason || '生成失败',
              suggestions: data.suggestions || [],
            })
            setIsGenerating(false)
            generatingRef.current = false
            break

          case 'thinking':
            setMessages(prev => [...prev, {
              id: ++logIdRef.current,
              time: new Date().toLocaleTimeString(),
              agent: data.tool || 'thinking',
              detail: data.thought || '',
              type: 'thinking',
            }])
            break

          case 'tool_result':
            setMessages(prev => [...prev, {
              id: ++logIdRef.current,
              time: new Date().toLocaleTimeString(),
              agent: data.tool || 'tool',
              detail: data.summary || '',
              type: 'tool_result',
            }])
            break

          case 'agent_log':
            setMessages(prev => [...prev, {
              id: ++logIdRef.current,
              time: new Date().toLocaleTimeString(),
              agent: data.agent,
              detail: `${data.action}: ${data.detail}`,
            }])
            break

          case 'review_rejected':
            setMessages(prev => [...prev, {
              id: ++logIdRef.current,
              time: new Date().toLocaleTimeString(),
              agent: 'verify',
              detail: `❌ 审查不通过 → ${data.feedback?.slice(0, 80) || '退回重做'}`,
            }])
            break
        }
      } catch (e) {
        // 忽略无法解析的消息帧
        setMessages(prev => [...prev, {
          id: ++logIdRef.current,
          time: new Date().toLocaleTimeString(),
          agent: 'system',
          detail: `消息解析失败: ${e.message}`,
        }])
      }
    }

    ws.onerror = () => {
      setError({ reason: 'WebSocket 连接失败，请确认后端已启动', suggestions: [] })
      setIsGenerating(false)
      generatingRef.current = false
    }

    ws.onclose = () => {
      // 用 ref 避免 stale closure
      if (generatingRef.current) {
        setIsGenerating(false)
        generatingRef.current = false
      }
    }
  }, [])

  const cancel = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setIsGenerating(false)
    generatingRef.current = false
    setGameCode(null)
    setError(null)
    setStatuses({})
    setMessages([])
  }, [])

  const dismiss = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setIsGenerating(false)
    generatingRef.current = false
    setGameCode(null)
    setError(null)
    setStatuses({})
    setMessages([])
  }, [])

  return { statuses, messages, gameCode, error, isGenerating, sendEvent, cancel, dismiss }
}
```

---

## frontend/src/components/SearchBubble.tsx

```
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
        <input value={value} onChange={e=>setValue(e.target.value)} placeholder="为你点亮一段视觉故事…"
          disabled={isGenerating} aria-label="输入主题"
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

---

## frontend/src/components/EventTags.tsx

```
import { useState, useEffect, useRef } from 'react'
import { ChevronDown, Compass } from 'lucide-react'

interface Props { onSelect:(name:string)=>void; disabled:boolean }

export function EventTags({ onSelect, disabled }: Props) {
  const [events, setEvents] = useState<any[]>([])
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    fetch('/api/events').then(r=>r.json()).then(d=>setEvents(d.events||[])).catch(()=>{})
  }, [])

  useEffect(() => {
    const handler = (e:MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  if (events.length===0) return null

  const names = events.map((e:any) => e.name || e.title || '')

  return (
    <div ref={ref} className="fixed top-5 right-5 z-[110] pointer-events-auto">
      <button
        onClick={() => setOpen(!open)}
        disabled={disabled}
        className="flex items-center gap-2 px-4 py-2.5 bg-white/[0.04] backdrop-blur-xl border border-white/[0.08] rounded-2xl text-white/45 hover:text-white/65 hover:bg-white/[0.06] hover:border-white/[0.14] transition-all text-xs disabled:opacity-30"
      >
        <Compass className="w-3.5 h-3.5" />
        探索主题
        <ChevronDown className={`w-3 h-3 transition-transform ${open?'rotate-180':''}`} />
      </button>

      {open && (
        <div className="absolute top-full right-0 mt-2 w-80 bg-black/80 backdrop-blur-2xl border border-white/[0.08] rounded-2xl shadow-2xl overflow-y-auto" style={{maxHeight:'50vh'}}>
          {names.map((name: string, i: number) => (
            <button
              key={i}
              onClick={() => { onSelect(name); setOpen(false) }}
              disabled={disabled}
              className="w-full text-left px-5 py-2.5 text-[13px] text-white/45 hover:text-white/85 hover:bg-white/[0.04] transition-all border-b border-white/[0.03] last:border-0 disabled:opacity-20"
            >
              {name}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
```

---

## frontend/src/components/AgentBuds.tsx

```
import { motion } from 'framer-motion'

interface Agent { key:string; name:string }
interface Status { status:'idle'|'running'|'done'|'failed'; message:string; retries:number }

function LightningBolt() {
  return (
    <svg width="12" height="18" viewBox="0 0 14 22" fill="none">
      <path
        d="M8 0L0 12H5L3 22L14 8H8L10 0H8Z"
        fill="rgba(220,220,240,0.9)"
        style={{ filter:'drop-shadow(0 0 4px rgba(200,200,255,0.7)) drop-shadow(0 0 8px rgba(180,180,255,0.4))' }}
      />
    </svg>
  )
}

export function AgentBuds({ agents, statuses }: { agents:Agent[]; statuses:Record<string,Status> }) {
  const anyActive = Object.values(statuses).some(s => s.status !== 'idle')

  return (
    <div className="flex items-center justify-center gap-6">
      {agents.map((agent, i) => {
        const s = statuses[agent.key]
        const isRunning = s?.status === 'running'
        const isDone    = s?.status === 'done'
        const isFailed  = s?.status === 'failed'

        return (
          <motion.div
            key={agent.key}
            className="flex flex-col items-center gap-1.5"
            initial={{ opacity:0, y:8 }}
            animate={{ opacity: anyActive ? 1 : 0.3, y:0 }}
            transition={{ delay: i * 0.06 }}
          >
            <motion.div className="relative flex items-center justify-center">
              {/* Glow ring: running */}
              {isRunning && (
                <motion.div className="absolute rounded-full"
                  style={{ width:18, height:18,
                    background:'radial-gradient(circle, rgba(200,200,240,0.25) 0%, transparent 70%)' }}
                  animate={{ scale:[1,1.4,1], opacity:[0.5,0.2,0.5] }}
                  transition={{ duration:1.8, repeat:Infinity, ease:'easeInOut' }}
                />
              )}

              {isDone && (
                <div className="absolute rounded-full"
                  style={{ width:14, height:14,
                    background:'radial-gradient(circle, rgba(200,200,240,0.12) 0%, transparent 70%)',
                    boxShadow:'0 0 8px rgba(180,180,230,0.15)' }} />
              )}

              <motion.div
                animate={isRunning ? {
                  scale:[1, 1.15, 0.95, 1.1, 1],
                  opacity:[0.6, 1, 0.8, 1, 0.6],
                } : {}}
                transition={isRunning ? { duration:1.2, repeat:Infinity, ease:'easeInOut' } : {}}
              >
                {isDone ? (
                  <LightningBolt />
                ) : isFailed ? (
                  <div style={{ width:4, height:6,
                    background:'radial-gradient(ellipse at 50% 40%, #441111, #1a0000)',
                    borderRadius:'50% 50% 50% 50% / 60% 60% 40% 40%',
                    boxShadow:'0 0 3px rgba(255,40,40,0.25)' }} />
                ) : isRunning ? (
                  <div style={{ width:5, height:7,
                    background:'radial-gradient(ellipse at 40% 30%, rgba(220,220,250,0.9), rgba(180,180,220,0.5))',
                    borderRadius:'50% 50% 50% 50% / 60% 60% 40% 40%',
                    boxShadow:'0 0 6px 2px rgba(200,200,240,0.5)' }} />
                ) : (
                  <div style={{ width:3, height:4,
                    background:'#2a2218', borderRadius:'50%', opacity:0.3 }} />
                )}
              </motion.div>
            </motion.div>

            <span className="text-[9px] tracking-[0.06em] font-medium whitespace-nowrap"
              style={{
                color: isDone ? 'rgba(240,240,255,0.85)' : isRunning ? 'rgba(230,230,255,0.65)' : isFailed ? 'rgba(255,120,120,0.45)' : 'rgba(255,255,255,0.08)',
                textShadow: isDone ? '0 0 5px rgba(200,200,240,0.4)' : isRunning ? '0 0 3px rgba(200,200,240,0.2)' : 'none',
              }}>
              {agent.name}
            </span>

            {s?.retries > 0 && (
              <span className="absolute -top-0.5 -right-0.5 w-3 h-3 rounded-full bg-red-500 text-[6px] font-bold text-white flex items-center justify-center"
                style={{ boxShadow:'0 0 4px rgba(239,68,68,0.4)' }}>
                {s.retries}
              </span>
            )}
          </motion.div>
        )
      })}
    </div>
  )
}
```

---

## frontend/src/components/StoryPanel.tsx

```
import { useState } from 'react'
import { Maximize2, Minimize2, Minus, X } from 'lucide-react'

interface Props { visible:boolean; gameCode:string|null; isGenerating:boolean; agentCount:number; doneCount:number; onClose:()=>void }

export function GamePanel({ visible, gameCode, isGenerating, agentCount, doneCount, onClose }: Props) {
  const [isFullscreen, setFullscreen] = useState(false)
  const [minimized, setMinimized] = useState(false)

  if (!visible && !isGenerating) return null
  const progress = agentCount>0 ? (doneCount/agentCount)*100 : 0

  // Minimized: show a small floating pill
  if (minimized && visible) {
    return (
      <div className="absolute z-50 left-1/2 -translate-x-1/2 pointer-events-auto"
        style={{ top:'58%' }}>
        <button onClick={() => setMinimized(false)}
          className="flex items-center gap-2 px-4 py-2 bg-black/40 backdrop-blur-xl border border-lime-400/20 rounded-full text-lime-400/70 hover:text-lime-300 hover:border-lime-400/40 transition-all text-xs shadow-lg">
          <div className="w-2 h-2 rounded-full bg-lime-400 animate-pulse" />
          游戏已就绪
        </button>
      </div>
    )
  }

  const panelStyle = (full:boolean) => ({
    position: 'absolute' as const, left:'50%', zIndex:50,
    width: full ? '100vw' : 'min(560px, 55vw)',
    height: full ? '100vh' : 'auto',
    aspectRatio: full ? undefined : '16/9',
    top: full ? 0 : '56%',
    transform: full ? 'translate(-50%,0)' : 'translate(-50%,-50%)',
    borderRadius: full ? 0 : 20,
    background: full ? 'rgba(0,0,0,0.95)'
      : visible ? 'rgba(0,0,0,0.55)'
      : 'rgba(0,0,0,0.12)',
    backdropFilter: full ? 'none' : visible ? 'blur(18px)' : 'blur(6px)',
    WebkitBackdropFilter: full ? 'none' : visible ? 'blur(18px)' : 'blur(6px)',
    border: visible ? '1px solid rgba(52,211,153,0.3)'
      : isGenerating ? '1px solid rgba(255,255,255,0.1)'
      : '1px solid rgba(255,255,255,0.06)',
    boxShadow: visible ? '0 0 40px rgba(52,211,153,0.2)'
      : isGenerating ? '0 0 0 transparent'
      : '0 4px 24px rgba(0,0,0,0.3)',
    transition:'all 0.5s cubic-bezier(0.16,1,0.3,1)',
  })

  const s = panelStyle(isFullscreen)

  return (
    <div style={s}>
      {/* Generating: 极简呼吸点，不挡画面 */}
      {isGenerating && !visible && (
        <div className="w-full h-full flex items-center justify-center">
          <div className="flex items-center gap-2.5">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-lime-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-lime-500"></span>
            </span>
            <span className="text-white/30 text-xs tracking-[0.05em]">策展中</span>
          </div>
        </div>
      )}

      {/* Empty idle */}
      {!isGenerating && !visible && (
        <div className="w-full h-full flex flex-col items-center justify-center gap-5">
          <p className="text-white/45 text-sm tracking-[0.05em]" style={{ animation:'blink 2s infinite' }}>
            等待时间裂隙开启...
          </p>
          <div className="w-4 h-4 rounded-full"
            style={{ background:'rgba(251,146,60,0.5)', boxShadow:'0 0 16px rgba(251,146,60,0.4)', animation:'blink 1.5s infinite' }} />
        </div>
      )}

      {/* Game iframe */}
      {visible && !isFullscreen && (<>
        <div className="absolute top-3 right-3 z-10 flex gap-1.5">
          <button onClick={() => setMinimized(true)}
            className="p-2 rounded-lg bg-white/[0.08] hover:bg-white/[0.18] text-white/50 hover:text-amber-400 transition-colors" title="最小化">
            <Minus size={14}/></button>
          <button onClick={()=>setFullscreen(true)}
            className="p-2 rounded-lg bg-white/[0.08] hover:bg-white/[0.18] text-white/50 hover:text-white/80 transition-colors" title="全屏">
            <Maximize2 size={14}/></button>
          <button onClick={onClose}
            className="p-2 rounded-lg bg-white/[0.08] hover:bg-red-500/20 text-white/50 hover:text-red-400 transition-colors" title="关闭">
            <X size={14}/></button>
        </div>
        <iframe srcDoc={gameCode||''} sandbox="allow-scripts" title="生成游戏"
          className="w-full h-full border-none bg-black" style={{ borderRadius:16 }} />
      </>)}

      {/* Fullscreen */}
      {visible && isFullscreen && (
        <div className="relative w-full h-full">
          <button onClick={()=>setFullscreen(false)}
            className="absolute top-4 right-4 z-20 p-2.5 rounded-lg bg-white/[0.1] hover:bg-red-500/25 text-white/50 hover:text-red-400 transition-colors" title="退出全屏">
            <Minimize2 size={16}/></button>
          <iframe srcDoc={gameCode||''} sandbox="allow-scripts" title="生成游戏-全屏"
            className="w-full h-full border-none bg-black" />
        </div>
      )}
    </div>
  )
}
```

---

## frontend/src/components/DecisionLog.tsx

```
import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Brain, Search, Palette, PenLine, Code, ShieldCheck, Sparkles, ChevronDown } from 'lucide-react'

interface Message { id:number; time:string; agent:string; detail:string; type?:string }

const TOOL_ICONS: Record<string, any> = {
  thinking: Brain, search: Search, design: Palette, compose: PenLine,
  render: Code, verify: ShieldCheck,
}
const TOOL_LABELS: Record<string, string> = {
  thinking: '思考', search: '搜索', design: '设计', compose: '文案',
  render: '生成', verify: '审查',
}

export function DecisionLog({ messages, autoCollapse }: { messages:Message[]; autoCollapse?:boolean }) {
  const [open, setOpen] = useState(true)
  const bodyRef = useRef<HTMLDivElement>(null)

  // StoryPanel 弹出时自动折叠
  useEffect(() => {
    if (autoCollapse) setOpen(false)
  }, [autoCollapse])

  useEffect(() => {
    if (bodyRef.current && open) bodyRef.current.scrollTop = bodyRef.current.scrollHeight
  }, [messages, open])

  const toolMsgs = messages.filter(m => m.type === 'thinking' || m.type === 'tool_result')

  return (
    <motion.div
      layout
      transition={{ type: "spring", stiffness: 260, damping: 28 }}
      className={`fixed bottom-6 right-6 z-[100] pointer-events-auto ${
        open
          ? 'w-[440px] max-h-[44vh]'
          : 'w-auto'
      }`}
    >
      <AnimatePresence mode="wait">
        {open ? (
          <motion.div
            key="panel"
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            className="rounded-3xl bg-black/60 backdrop-blur-2xl border border-white/10 shadow-2xl shadow-black/50 overflow-hidden"
          >
            {/* 标题栏 */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-white/[0.04] cursor-pointer"
              onClick={() => setOpen(false)}>
              <div className="flex items-center gap-2">
                <Sparkles size={14} className="text-lime-400" />
                <span className="text-xs font-medium text-white/50">AI 思考流程</span>
              </div>
              <ChevronDown size={14} className="text-white/20" />
            </div>

            {/* 日志流 */}
            <div ref={bodyRef} className="overflow-y-auto px-4 py-3 space-y-2" style={{ maxHeight: '32vh' }}>
              {toolMsgs.length === 0 ? (
                <div className="text-center py-6">
                  <span className="relative flex h-2 w-2 mx-auto mb-3">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-lime-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-lime-500"></span>
                  </span>
                  <p className="text-white/20 text-xs">正在唤醒 AI 策展人…</p>
                </div>
              ) : (
                toolMsgs.slice(-30).map((m) => {
                  const isThinking = m.type === 'thinking'
                  const Icon = TOOL_ICONS[m.agent] || Brain
                  return (
                    <motion.div
                      key={m.id}
                      initial={{ opacity: 0, x: 20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.25 }}
                      className={`flex gap-3 text-xs ${
                        isThinking
                          ? 'bg-lime-400/[0.03] rounded-xl px-3 py-2 -mx-1'
                          : 'opacity-70'
                      }`}
                    >
                      <div className={`w-4 h-4 rounded-md flex items-center justify-center shrink-0 mt-0.5 ${
                        isThinking ? 'bg-lime-400/10 text-lime-400' : 'bg-white/[0.04] text-white/25'
                      }`}>
                        <Icon size={10} />
                      </div>
                      <div className="flex-1 min-w-0">
                        {isThinking && (
                          <span className="text-white/[0.20] text-[10px]">🤔 思考</span>
                        )}
                        <p className={`mt-0.5 leading-relaxed ${
                          isThinking ? 'text-white/60 italic' : 'text-white/35'
                        }`}>
                          {m.detail}
                        </p>
                      </div>
                      <span className="text-white/[0.10] text-[10px] whitespace-nowrap self-start">
                        {m.time}
                      </span>
                    </motion.div>
                  )
                })
              )}
            </div>
          </motion.div>
        ) : (
          <motion.button
            key="btn"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            onClick={() => setOpen(true)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-full bg-black/60 backdrop-blur-xl border border-white/10 text-white/45 hover:text-white/70 hover:border-white/20 transition-all shadow-lg shadow-black/40"
          >
            <div className={`w-2 h-2 rounded-full ${toolMsgs.length > 0 ? 'bg-lime-400 animate-pulse' : 'bg-white/20'}`} />
            <Sparkles size={14} className="text-lime-400/70" />
            {toolMsgs.length > 0 && (
              <span className="text-[11px] font-medium text-white/60">
                {toolMsgs.length} 步
              </span>
            )}
          </motion.button>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
```

---

## frontend/src/components/RevealLayer.tsx

```
import { useRef, useEffect } from 'react';

interface RevealLayerProps {
  image: string;
  cursorX: number;
  cursorY: number;
}

const SPOTLIGHT_R = 260;

export default function RevealLayer({ image, cursorX, cursorY }: RevealLayerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const revealRef = useRef<HTMLDivElement>(null);
  const cursorRef = useRef({ x: cursorX, y: cursorY });

  cursorRef.current = { x: cursorX, y: cursorY };

  const draw = () => {
    const canvas = canvasRef.current;
    const revealDiv = revealRef.current;
    if (!canvas || !revealDiv) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const w = window.innerWidth;
    const h = window.innerHeight;

    if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
    }

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    const cx = cursorRef.current.x;
    const cy = cursorRef.current.y;

    if (cx >= 0 || cy >= 0) {
      const gradient = ctx.createRadialGradient(cx, cy, 0, cx, cy, SPOTLIGHT_R);
      gradient.addColorStop(0, 'rgba(255,255,255,1)');
      gradient.addColorStop(0.4, 'rgba(255,255,255,1)');
      gradient.addColorStop(0.6, 'rgba(255,255,255,0.75)');
      gradient.addColorStop(0.75, 'rgba(255,255,255,0.4)');
      gradient.addColorStop(0.88, 'rgba(255,255,255,0.12)');
      gradient.addColorStop(1, 'rgba(255,255,255,0)');

      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.arc(cx, cy, SPOTLIGHT_R, 0, Math.PI * 2);
      ctx.fill();
    }

    const dataUrl = canvas.toDataURL();
    revealDiv.style.maskImage = `url(${dataUrl})`;
    revealDiv.style.webkitMaskImage = `url(${dataUrl})`;
    revealDiv.style.maskSize = '100% 100%';
    revealDiv.style.webkitMaskSize = '100% 100%';
  };

  useEffect(() => {
    draw();
  }, [cursorX, cursorY]);

  useEffect(() => {
    const handleResize = () => draw();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <>
      <canvas
        ref={canvasRef}
        className="absolute inset-0 pointer-events-none"
        style={{ display: 'none' }}
      />
      <div
        ref={revealRef}
        className="absolute inset-0 bg-center bg-cover bg-no-repeat z-30 pointer-events-none"
        style={{ backgroundImage: `url(${image})` }}
      />
    </>
  );
}
```

---

## frontend/src/components/FailureNotice.tsx

```
import { AlertCircle, X } from 'lucide-react'

interface Props {
  visible: boolean
  reason: string
  suggestions: string[]
  onRetry: (s:string) => void
  onDismiss: () => void
}

export function FailureNotice({ visible, reason, suggestions, onRetry, onDismiss }: Props) {
  if (!visible) return null

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center pointer-events-none">
      <div className="pointer-events-auto w-[90vw] max-w-md bg-black/85 backdrop-blur-2xl border border-red-500/12 rounded-3xl p-6 shadow-2xl">
        <div className="flex items-start gap-3 mb-4">
          <div className="w-9 h-9 rounded-full bg-red-500/8 flex items-center justify-center shrink-0 mt-0.5">
            <AlertCircle className="w-4 h-4 text-red-400" />
          </div>
          <div className="flex-1">
            <h3 className="text-sm font-semibold text-red-400 mb-1">生成失败</h3>
            <p className="text-[13px] text-white/40 leading-relaxed">{reason}</p>
          </div>
          <button onClick={onDismiss} className="p-1 rounded-lg hover:bg-white/[0.05] text-white/20 hover:text-white/50 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>
        {suggestions.length > 0 && (
          <div className="flex flex-wrap gap-2 pl-12">
            <span className="text-[10px] text-white/20 self-center">建议尝试：</span>
            {suggestions.slice(0,4).map((s,i) => (
              <button key={i} onClick={() => onRetry(s)}
                className="px-3 py-1 text-[11px] bg-white/[0.03] border border-white/[0.06] rounded-full text-white/40 hover:bg-white/[0.08] hover:text-white/70 transition-all">
                {s.length>20 ? s.slice(0,20)+'…' : s}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
```

---

## frontend/src/components/ErrorBoundary.tsx

```
import { Component, ReactNode } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

export class ErrorBoundary extends Component<{ children:ReactNode }, { hasError:boolean; error:Error|null }> {
  constructor(props:{ children:ReactNode }) {
    super(props)
    this.state = { hasError:false, error:null }
  }
  static getDerivedStateFromError(error:Error) { return { hasError:true, error } }
  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-dvh bg-black flex items-center justify-center p-8">
          <div className="text-center">
            <div className="w-14 h-14 mx-auto mb-5 rounded-2xl bg-red-500/8 flex items-center justify-center">
              <AlertTriangle className="w-6 h-6 text-red-400" />
            </div>
            <h2 className="text-white/70 text-lg font-semibold mb-2">界面渲染出错</h2>
            <p className="text-white/25 text-sm mb-5">{this.state.error?.message||'未知错误'}</p>
            <button onClick={() => window.location.reload()}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-2xl text-white/50 hover:text-white hover:bg-white/[0.08] transition-all text-sm">
              <RefreshCw className="w-4 h-4" />刷新页面
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
```
