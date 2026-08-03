"""爬虫 Agent — 三阶梯检索 + LLM 深度素材评估（AI 原生版）"""

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


MATERIAL_EVALUATION_PROMPT = """你是一位素材研究员，擅长判断素材是否足够支撑一个有趣的解谜小游戏。

评估时必须逐步思考，每一步都要有依据：

1. 【时间锚点】是否有明确的时间点？（精确到年/月？）
2. 【空间锚点】是否有具体地点？（城市/建筑/实验室？）
3. 【人物画像】是否有明确的主角和对抗方？（名字/身份/动机？）
4. 【事件脉络】是否有清晰的"起因→经过→结果"？
5. 【可视化素材】是否有可转化为游戏元素的道具/场景/符号？
6. 【谜题潜力】素材中是否天然包含某种"隐藏信息"或"逻辑结构"？

如果素材不足，明确指出缺什么、为什么缺、补充什么能挽救。
如果素材充足，建议最适合的谜题类型及理由（引用具体素材片段）。

返回严格 JSON：
{
  "sufficient": true,
  "reasoning": "详细评估过程，引用素材中的具体证据...",
  "gaps": ["缺少的具体内容1"],
  "confidence": 0.85,
  "suggested_type": "cipher",
  "visual_elements": ["可从素材中提取的视觉元素1", "元素2"],
  "puzzle_hook": "素材中最适合做成谜题核心机制的那个点"
}"""


def evaluate_material(user_input: str, sources: list[dict]) -> dict:
    if not sources:
        return {"sufficient": False, "reasoning": "未收集到任何素材。",
                "gaps": ["所有检索来源均未返回结果"], "confidence": 0.0,
                "suggested_type": "unknown", "visual_elements": [], "puzzle_hook": ""}

    sources_text = "\n\n---\n\n".join(
        f"[来源 {i+1}] {s.get('title', '未命名')}\n{s.get('content', '')[:1000]}"
        for i, s in enumerate(sources[:6])
    )

    prompt = f"""请评估以下素材是否足够支撑一个关于「{user_input}」的解谜小游戏。

素材：
{sources_text}

请按 system prompt 的 6 个维度逐步评估，返回 JSON。不要加 markdown 代码块。"""

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
            "visual_elements": result.get("visual_elements", []),
            "puzzle_hook": result.get("puzzle_hook", ""),
        }
    except Exception as e:
        total_chars = sum(len(s.get("content", "")) for s in sources)
        return {
            "sufficient": total_chars >= 300,
            "reasoning": f"LLM 评估失败（{str(e)}），降级到字符数兜底规则：共 {total_chars} 字符。",
            "gaps": ["LLM 评估异常"], "confidence": 0.3,
            "suggested_type": "unknown", "visual_elements": [], "puzzle_hook": "",
        }


def crawler_node(state: GameFactoryState) -> dict:
    user_input = state["user_input"]
    all_sources = []
    actions = []

    # Step 1: KB 匹配示例话题
    verified_event = get_event_by_keyword(user_input)
    if verified_event:
        all_sources.extend(event_to_search_results(verified_event))
        actions.append("kb_hit")

    # Step 2: web_search（始终执行，补充素材）
    web_results = web_search(user_input, max_results=5)
    if web_results:
        all_sources.extend(_web_results_to_search_results(web_results))
        actions.append("web_search")

    # LLM 深度素材评估（所有输入统一走评估）
    evaluation = evaluate_material(user_input, all_sources)

    eval_logs = []
    eval_logs.append(agent_log("crawler", "thinking",
        f"开始评估「{user_input}」— 共 {len(all_sources)} 个来源"))

    reasoning_steps = [s.strip() for s in evaluation["reasoning"].replace("。", "\n").split("\n") if s.strip()]
    for step in reasoning_steps[:6]:
        eval_logs.append(agent_log("crawler", "thinking_step", step))

    if evaluation["visual_elements"]:
        eval_logs.append(agent_log("crawler", "visual_found",
            f"发现可视化元素: {'、'.join(evaluation['visual_elements'])}"))

    if evaluation["puzzle_hook"]:
        eval_logs.append(agent_log("crawler", "puzzle_hook",
            f"谜题钩子: {evaluation['puzzle_hook']}"))

    eval_detail = (
        f"sufficient={evaluation['sufficient']}, confidence={evaluation['confidence']}, "
        f"suggested={evaluation['suggested_type']}\n"
        f"缺失: {'; '.join(evaluation['gaps']) if evaluation['gaps'] else '无'}"
    )
    eval_logs.append(agent_log("crawler", "evaluated", eval_detail))

    if evaluation["sufficient"]:
        return {
            "search_results": all_sources,
            "material_score": evaluation["confidence"],
            "material_sufficient": True,
            "suggested_type": evaluation["suggested_type"],
            "agent_logs": eval_logs + [
                agent_log("crawler", "material_ok",
                    f"{'+'.join(actions)}: {len(all_sources)} sources, LLM评估通过")
            ],
        }

    # Step 3: DeepSeek 兜底
    gaps_text = "\n".join(f"- {g}" for g in evaluation["gaps"])
    try:
        response = chat_json(
            f"请检索关于以下主题的资料，重点补充缺失信息：\n\n主题：{user_input}\n\n不足：\n{gaps_text}",
            system="你是研究员。只输出确定的事实。返回 JSON：{material_sufficient, sources, keywords}",
        )
        response = _strip_markdown_fence(response)
        result = json.loads(response)
        if result.get("material_sufficient"):
            ds = result.get("sources", [])
            for s in ds:
                s["verified"] = False
                s["source"] = "deepseek_knowledge"
            all_sources.extend(ds)
            total = sum(len(s.get("content", "")) for s in all_sources)
            return {
                "search_results": all_sources,
                "material_score": round(min(total / 3000, 0.9), 2),
                "material_sufficient": True,
                "suggested_type": evaluation["suggested_type"],
                "agent_logs": eval_logs + [
                    agent_log("crawler", "deepseek_enrich", f"补充 {len(ds)} sources")
                ]
            }
    except Exception:
        pass

    if all_sources:
        return {
            "search_results": all_sources,
            "material_score": 0.4,
            "material_sufficient": True,
            "suggested_type": evaluation["suggested_type"],
            "agent_logs": eval_logs + [
                agent_log("crawler", "partial", "DeepSeek失败，使用现有素材")
            ]
        }

    return {
        "search_results": [],
        "material_score": 0.0,
        "material_sufficient": False,
        "error_message": f"关于「{user_input}」没有足够资料。试试更知名的主题。",
        "suggestions": get_event_names()[:5],
        "status": "failed",
        "agent_logs": eval_logs + [agent_log("crawler", "insufficient", "LLM评估+DeepSeek均不足")],
    }
