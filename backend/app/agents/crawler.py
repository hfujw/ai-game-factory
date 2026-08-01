"""爬虫 Agent — 知识检索。先查已验证知识库，再调 DeepSeek 兜底。

输入：用户输入的历史事件
输出：search_results + material_score + material_sufficient + verified 标记

策略：
1. 先在本地验证知识库（verified_events.json）中匹配——100% 真实
2. 匹配不到 → 调 DeepSeek 知识检索 → 标记 verified=false
3. 两个都搜不到 → 返回失败
"""

import json
from app.graph.state import GameFactoryState
from app.llm_client import chat_json, _strip_markdown_fence
from app.knowledge.kb import get_event_by_keyword, event_to_search_results, get_event_names


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
    """知识检索——先查验证库，再调 DeepSeek。"""
    user_input = state["user_input"]

    # 第一步：查验证知识库
    verified_event = get_event_by_keyword(user_input)

    if verified_event:
        sources = event_to_search_results(verified_event)
        return {
            "search_results": sources,
            "material_score": 1.0,
            "material_sufficient": True,
            "agent_logs": [{
                "agent": "crawler",
                "action": "verified",
                "detail": f"matched '{verified_event['event']}' in verified KB",
            }],
        }

    # 第二步：验证库没找到 → DeepSeek 兜底
    try:
        response = chat_json(
            f"请检索关于以下计算机历史事件的资料：\n\n{user_input}\n\n请提供你确定知道的事实。不要编造。",
            system=DEEPSEEK_RETRIEVAL_PROMPT,
        )
        response = _strip_markdown_fence(response)

        result = json.loads(response)

        if not result.get("material_sufficient", False):
            return {
                "search_results": [],
                "material_score": 0.0,
                "material_sufficient": False,
                "error_message": f"关于「{user_input}」没有足够资料。试试更知名的计算机历史事件。",
                "suggestions": get_event_names()[:5],
                "status": "failed",
                "agent_logs": [{"agent": "crawler", "action": "insufficient", "detail": "not found in KB or LLM"}],
            }

        sources = result.get("sources", [])
        # 标记为未验证
        for s in sources:
            s["verified"] = False
            s["source"] = "deepseek_knowledge"

        total_chars = sum(len(s.get("content", "")) for s in sources)
        sufficient = len(sources) >= 1 and total_chars >= 100

        if not sufficient:
            return {
                "search_results": [],
                "material_score": 0.0,
                "material_sufficient": False,
                "error_message": f"关于「{user_input}」没有足够资料。试试更知名的计算机历史事件。",
                "suggestions": get_event_names()[:5],
                "status": "failed",
                "agent_logs": [{"agent": "crawler", "action": "insufficient", "detail": "sources empty or too few chars"}],
            }

        return {
            "search_results": sources,
            "material_score": round(min(total_chars / 3000, 0.85), 2),
            "material_sufficient": True,
            "agent_logs": [{
                "agent": "crawler",
                "action": "retrieved_unverified",
                "detail": f"{len(sources)} sources via DeepSeek (unverified), suggest adding to KB",
            }],
        }

    except Exception as e:
        return {
            "search_results": [],
            "material_score": 0.0,
            "material_sufficient": False,
            "error_message": f"知识检索失败: {str(e)}",
            "suggestions": get_event_names()[:5],
            "status": "failed",
            "agent_logs": [{"agent": "crawler", "action": "error", "detail": str(e)}],
        }
