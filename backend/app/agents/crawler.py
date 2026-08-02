"""爬虫 Agent — 三阶梯检索。

1. KB 匹配（免费）— 骨架数据
2. web_search（免费）— 血肉补充，即使 KB 命中也跑
3. DeepSeek 兜底（付费）— 前两步都没拿到足够数据时

输入：用户输入的历史事件
输出：search_results + material_score + material_sufficient
"""

import json
from app.graph.state import GameFactoryState
from app.llm_client import agent_log, chat_json, _strip_markdown_fence
from app.knowledge.kb import get_event_by_keyword, event_to_search_results, get_event_names
from app.mcp.web_search import search as web_search


def _web_results_to_search_results(results: list[dict]) -> list[dict]:
    """将 web_search 返回的原始结果转为 search_results 格式。"""
    return [{
        "title": r.get("title", ""),
        "content": r.get("snippet", ""),
        "url": r.get("url", ""),
        "confidence": "medium",
        "verified": False,
        "source": "web_search",
    } for r in results]


DEEPSEEK_RETRIEVAL_PROMPT = """你是一个计算机历史档案馆的研究员。用户给你一个计算机历史事件，
你需要检索并整理相关的事实信息。

要求：
1. 只输出你确定的事实——不确定的内容标注 confidence 为 low
2. 每条事实标注置信度（high/medium/low）
3. 尽可能提供具体的时间、地点、人物、事件经过、趣闻
4. 如果这个事件你完全不了解，返回 material_sufficient=false

返回严格的 JSON：
{
  "material_sufficient": true,
  "sources": [
    {
      "title": "条目标题",
      "content": "详细的事实描述（200-500字）",
      "confidence": "high|medium|low",
      "key_facts": ["事实1", "事实2"]
    }
  ],
  "keywords": ["关键词1", "关键词2"]
}"""


def crawler_node(state: GameFactoryState) -> dict:
    """三阶梯检索：KB → web_search → DeepSeek。"""
    user_input = state["user_input"]

    all_sources = []
    actions = []

    # === 第1步：KB 匹配（骨架） ===
    verified_event = get_event_by_keyword(user_input)
    if verified_event:
        kb_sources = event_to_search_results(verified_event)
        all_sources.extend(kb_sources)
        actions.append("kb_hit")

    # === 第2步：web_search（血肉）——即使 KB 命中也跑 ===
    web_results = web_search(user_input, max_results=5)
    if web_results:
        web_sources = _web_results_to_search_results(web_results)
        all_sources.extend(web_sources)
        actions.append("web_search")

    # === 判断：现有素材是否足够 ===
    total_chars = sum(len(s.get("content", "")) for s in all_sources)
    has_kb = verified_event is not None
    has_web = len(web_results) >= 2

    if has_kb and total_chars >= 300:
        # KB + web 数据充足，不调 DeepSeek
        return {
            "search_results": all_sources,
            "material_score": 1.0,
            "material_sufficient": True,
            "agent_logs": [{
                "agent": "crawler",
                "action": "verified",
                "detail": f"KB hit + web_search: {len(all_sources)} sources, {total_chars} chars",
            }],
        }

    if not has_kb and has_web and total_chars >= 200:
        # 无 KB 但 web 够用，不调 DeepSeek
        return {
            "search_results": all_sources,
            "material_score": 0.6,
            "material_sufficient": True,
            "agent_logs": [{
                "agent": "crawler",
                "action": "web_only",
                "detail": f"web_search only: {len(all_sources)} sources, {total_chars} chars",
            }],
        }

    # === 第3步：DeepSeek 兜底（付费） ===
    if all_sources:
        actions.append("deepseek_enrich")
    else:
        actions.append("deepseek_fallback")

    try:
        response = chat_json(
            f"请检索关于以下计算机历史事件的资料：\n\n{user_input}\n\n请提供你确定知道的事实。不要编造。",
            system=DEEPSEEK_RETRIEVAL_PROMPT,
        )
        response = _strip_markdown_fence(response)
        result = json.loads(response)

        if not result.get("material_sufficient", False):
            # DeepSeek 也不知道 → 如果前面有素材就用，没有就失败
            if all_sources:
                return {
                    "search_results": all_sources,
                    "material_score": 0.4,
                    "material_sufficient": True,
                    "agent_logs": [agent_log("crawler", "partial", f"DeepSeek insufficient, using KB+web: {len(all_sources)} sources")],
                }
            return {
                "search_results": [],
                "material_score": 0.0,
                "material_sufficient": False,
                "error_message": f"关于「{user_input}」没有足够资料。试试更知名的计算机历史事件。",
                "suggestions": get_event_names()[:5],
                "status": "failed",
                "agent_logs": [agent_log("crawler", "insufficient", "not found anywhere")],
            }

        # DeepSeek 有结果 → 追加
        deepseek_sources = result.get("sources", [])
        for s in deepseek_sources:
            s["verified"] = False
            s["source"] = "deepseek_knowledge"
        all_sources.extend(deepseek_sources)

        total = sum(len(s.get("content", "")) for s in all_sources)
        return {
            "search_results": all_sources,
            "material_score": round(min(total / 3000, 0.9), 2),
            "material_sufficient": len(all_sources) >= 1 and total >= 100,
            "agent_logs": [{
                "agent": "crawler",
                "action": "retrieved",
                "detail": f"{' + '.join(actions)}: {len(all_sources)} sources, {total} chars",
            }],
        }

    except Exception as e:
        # DeepSeek 挂了 → 前面有素材就继续，没有就失败
        if all_sources:
            return {
                "search_results": all_sources,
                "material_score": 0.3,
                "material_sufficient": True,
                "agent_logs": [agent_log("crawler", "partial", f"DeepSeek error, using KB+web: {len(all_sources)} sources")],
            }
        return {
            "search_results": [],
            "material_score": 0.0,
            "material_sufficient": False,
            "error_message": f"知识检索失败: {str(e)}",
            "suggestions": get_event_names()[:5],
            "status": "failed",
            "agent_logs": [agent_log("crawler", "error", str(e))],
        }
