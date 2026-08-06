"""5个工具 — 编排LLM按需调用。每个工具独立、无状态、可单独测试。"""

import json
import logging
import httpx
from app.llm_client import chat, chat_json, _strip_markdown_fence

logger = logging.getLogger(__name__)

# ── 素材过滤 ──
_AD_NOISE = {"广告", "推广", "促销", "优惠", "团购", "门票", "攻略", "旅游团",
             "酒店", "民宿", "租车", "代购", "加盟", "招商", "股票", "基金"}


def _filter_noise(results: list[dict]) -> list[dict]:
    return [r for r in results if not any(kw in r.get("title", "") + r.get("snippet", "") for kw in _AD_NOISE)]


# ═══════════════════════════════════════════════════════════
# 工具 1: search
# ═══════════════════════════════════════════════════════════

async def _search_tavily(query: str, max_results: int = 8) -> list[dict]:
    """Tavily Search API——国内可直连，返回 JSON 已清洗文本。没配 Key 直接返回空。"""
    from app.config import settings

    key = settings.tavily_api_key.strip()
    if not key:
        return []

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": key,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": max_results,
                    "include_answer": False,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            results = []
            for r in data.get("results", []):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", "")[:600],
                })
            logger.info("Tavily搜索 | query='%s' | 结果=%d", query[:40], len(results))
            return results
    except Exception as e:
        logger.warning("Tavily搜索失败: %s", e)
        return []


async def tool_search(query: str, reason: str = "", depth: str = "quick", existing_material: list[dict] = None) -> dict:
    """搜素材。Tavily → 空返回 → LLM 用自身知识兜底。

    Bing 已砍——国内不可用，留着只会拖慢超时。
    """
    max_results = 8 if depth == "quick" else 15

    raw = await _search_tavily(query, max_results)
    if not raw:
        logger.info("搜索=空 | query='%s' | LLM将用自身知识", query[:40])

    filtered = _filter_noise(raw) if raw else []

    # 去重
    if existing_material:
        seen = {r.get("title", "") for r in existing_material}
        filtered = [r for r in filtered if r.get("title", "") not in seen]

    # 相关性检查
    if filtered and query:
        query_words = set(query.lower().split())
        relevant = []
        for r in filtered:
            text = (r.get("title", "") + " " + r.get("snippet", "")).lower()
            if any(w in text for w in query_words if len(w) >= 2):
                relevant.append(r)
        if not relevant:
            logger.info("工具=search | query='%s' | 全部不相关，返回0条", query)
            return {"tool": "search", "query": query, "reason": reason,
                    "results": [], "count": 0, "note": "搜索结果与主题不直接相关"}
        filtered = relevant

    logger.info("工具=search | query='%s' | 结果=%d", query, len(filtered))
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


async def tool_design(
    material: list[dict],
    user_input: str = "",
    session_records: list[dict] | None = None,
) -> dict:
    """分析素材，决定用什么叙事形式。"""
    if not material:
        return {"tool": "design", "components": ["encyclopedia"], "rationale": "无素材，仅做百科式展示",
                "structure": "单列百科条目", "visual_hint": "简洁中性"}

    brief = "\n\n".join(
        f"[{i+1}] {r.get('title','')}: {r.get('snippet', r.get('content',''))[:300]}"
        for i, r in enumerate(material[:8])
    )

    topic_hint = f"\n⚠️ 用户想了解的具体主题是「{user_input}」。只围绕这个主题设计，不要扩展成更大的话题。" if user_input else ""

    try:
        result = await chat_json(
            f"素材：\n{brief}{topic_hint}",
            system=DESIGN_SYSTEM_PROMPT,
            session_records=session_records,
        )
        result = _strip_markdown_fence(result)
        design = json.loads(result)
        logger.info("工具=design | 组件=%s", design.get("components", []))
        design["tool"] = "design"
        return design
    except Exception as e:
        logger.warning("design失败: %s", e)
        return {"tool": "design", "components": ["encyclopedia"], "rationale": f"LLM异常({e})，降级为百科条目",
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


async def tool_compose(
    material: list[dict],
    design: dict,
    user_input: str = "",
    session_records: list[dict] | None = None,
) -> dict:
    """写叙事文案+来源标注。"""
    brief = "\n\n".join(
        f"[来源{i+1}] {r.get('title','')}: {r.get('snippet', r.get('content',''))[:400]}"
        for i, r in enumerate(material[:8])
    )

    topic_hint = f"\n⚠️ 用户想了解的具体主题是「{user_input}」。只围绕这个主题写内容，不要偏离。" if user_input else ""

    prompt = f"""素材：{brief}

设计：{json.dumps(design, ensure_ascii=False)}
{topic_hint}
为每个组件写内容。每个数字/年份/人名必须标注来源。"""

    try:
        result = await chat_json(prompt, system=COMPOSE_SYSTEM_PROMPT, session_records=session_records)
        result = _strip_markdown_fence(result)
        content = json.loads(result)
        logger.info("工具=compose | blocks=%d", len(content.get("blocks", [])))
        content["tool"] = "compose"
        return content
    except Exception as e:
        logger.warning("compose失败: %s", e)
        return {"tool": "compose", "title": "生成失败", "subtitle": str(e), "blocks": [], "fact_notes": ""}


# ═══════════════════════════════════════════════════════════
# 工具 4: render
# ═══════════════════════════════════════════════════════════

# 注意：使用 {{design}} 双花括号占位，避免与 JSON 中的单花括号冲突
RENDER_SYSTEM_PROMPT = """生成一个好看的交互式HTML页面。

【结构】
{{design}}

【内容】
{{content}}

【视觉方向】
{{visual}}

【规则】
- 450行以内，CSS精简，动画最多1个
- 不用外部库
- 必须有</html>
- 直接输出完成HTML，不要```包裹"""


async def tool_render(
    design: dict,
    content: dict,
    visual: dict = None,
    session_records: list[dict] | None = None,
) -> dict:
    """生成HTML。返回html字符串+完整性标记。"""
    visual = visual or {}
    visual_block = ""
    if visual.get("reference_css"):
        visual_block = f"参考CSS：\n{visual['reference_css'][:800]}"
    if visual.get("palette"):
        visual_block += f"\n色板：{', '.join(visual['palette'])}"

    # 用 replace 而不是 format，避免 JSON 字符串中的 {} 被误解析
    prompt = (
        RENDER_SYSTEM_PROMPT
        .replace("{{design}}", json.dumps(design, ensure_ascii=False, indent=2))
        .replace("{{content}}", json.dumps(content, ensure_ascii=False, indent=2))
        .replace("{{visual}}", visual_block or "由你自由发挥")
    )

    try:
        code = await chat(
            prompt,
            system="你是前端工程师。直接输出完整HTML。",
            temperature=0.3,
            session_records=session_records,
        )
        code = _strip_markdown_fence(code)
        if not code.lower().startswith("<!doctype"):
            code = f"<!DOCTYPE html>\n{code}"

        is_complete = "</html>" in code
        logger.info("工具=render | %d chars | 完整=%s", len(code), is_complete)
        return {"tool": "render", "html": code, "complete": is_complete, "length": len(code)}
    except Exception as e:
        logger.error("render失败: %s", e)
        return {"tool": "render", "html": "<!DOCTYPE html><html><body><h1>生成失败</h1><p>AI 暂时无法完成这个页面，请稍后重试。</p></body></html>",
                "complete": True, "length": 0, "error": str(e)}


async def tool_render_stream(
    design: dict,
    content: dict,
    visual: dict = None,
    session_records: list[dict] | None = None,
):
    """流式生成HTML——逐段 yield，前端 iframe 实时看到页面"长出来"。

    用法：
        async for frame in tool_render_stream(design, content):
            if frame["complete"]:
                result = frame   # 最终结果，同 tool_render 返回格式
            else:
                push({"type": "html_chunk", "html": frame["html"]})
    """
    from app.llm_client import chat_stream

    visual = visual or {}
    visual_block = ""
    if visual.get("reference_css"):
        visual_block = f"参考CSS：\n{visual['reference_css'][:800]}"
    if visual.get("palette"):
        visual_block += f"\n色板：{', '.join(visual['palette'])}"

    prompt = (
        RENDER_SYSTEM_PROMPT
        .replace("{{design}}", json.dumps(design, ensure_ascii=False, indent=2))
        .replace("{{content}}", json.dumps(content, ensure_ascii=False, indent=2))
        .replace("{{visual}}", visual_block or "由你自由发挥")
    )

    try:
        accumulated = ""
        async for chunk in chat_stream(
            prompt,
            system="你是前端工程师。直接输出完整HTML。",
            temperature=0.3,
            session_records=session_records,
            label="render",
        ):
            accumulated += chunk
            # 每积累 300 字符或遇到 > 时推送一次（保证标签完整）
            if len(accumulated) > 300 and ">" in accumulated:
                yield {"tool": "render", "html": accumulated, "complete": False}

        code = _strip_markdown_fence(accumulated)
        if not code.lower().startswith("<!doctype"):
            code = f"<!DOCTYPE html>\n{code}"

        is_complete = "</html>" in code
        logger.info("工具=render_stream | %d chars | 完整=%s", len(code), is_complete)
        yield {"tool": "render", "html": code, "complete": is_complete, "length": len(code)}

    except Exception as e:
        logger.error("render流式失败: %s", e)
        yield {"tool": "render", "html": "<!DOCTYPE html><html><body><h1>生成失败</h1><p>请稍后重试</p></body></html>",
               "complete": True, "length": 0, "error": str(e)}


# ═══════════════════════════════════════════════════════════
# 工具 5: verify
# ═══════════════════════════════════════════════════════════

async def tool_verify(html: str, content: dict) -> dict:
    """审查：硬规则(纯Python) + 可用Playwright时真执行。"""
    issues = []

    # Phase 1: 硬规则
    if "</html>" not in html:
        issues.append({"severity": "critical", "category": "incomplete",
                       "description": "HTML不完整，缺少</html>", "fix": "render时精简CSS，确保输出完整"})
    # 修复：只要 html 里不包含 "<script"（不区分大小写）就算缺 JS
    if "<script" not in html.lower():
        issues.append({"severity": "warning", "category": "no_js",
                       "description": "缺少<script>标签，页面无交互", "fix": "添加至少一个<script>标签"})
    if "{visual_css}" in html or "{{" in html:
        issues.append({"severity": "critical", "category": "placeholder",
                       "description": "HTML中包含未填充的占位符", "fix": "render时检查所有{{}}是否已替换"})

    # Phase 2: Playwright真执行（异步，不阻塞事件循环）
    playwright_ok = False
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            js_errors = []
            page.on("pageerror", lambda err: js_errors.append(str(err)))
            await page.set_content(html)
            await page.wait_for_timeout(800)
            if js_errors:
                issues.append({"severity": "warning", "category": "js_error",
                               "description": f"JS报错: {'; '.join(js_errors[:3])}",
                               "fix": "修复JS语法错误"})
            await browser.close()
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
        if any(i["category"] in ("incomplete", "placeholder") for i in critical):
            rollback_target = "render"
        else:
            rollback_target = "compose"

    logger.info("工具=verify | passed=%s | issues=%d | playwright=%s", passed, len(issues), playwright_ok)
    return {"tool": "verify", "passed": passed, "issues": issues, "rollback_target": rollback_target,
            "playwright_ok": playwright_ok}