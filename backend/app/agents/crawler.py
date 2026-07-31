"""爬虫 Agent — 知识检索。先查已验证知识库，再调 DeepSeek 兜底。

输入：用户输入的历史事件
输出：search_results + material_score + material_sufficient + verified 标记

策略：
1. 先在本地验证知识库（verified_events.json）中匹配——100% 真实
2. 匹配不到 → 调 DeepSeek 知识检索 → 标记 verified=false
3. 两个都搜不到 → 返回失败
"""

import json
import os
from app.graph.state import GameFactoryState
from app.llm_client import chat_json

# 加载验证知识库
_KB_PATH = os.path.join(os.path.dirname(__file__), "..", "knowledge", "verified_events.json")
with open(_KB_PATH, "r", encoding="utf-8") as f:
    VERIFIED_KNOWLEDGE_BASE = json.load(f)


def _search_verified_kb(user_input: str) -> dict | None:
    """在验证知识库中搜索。返回匹配的事件，或 None。

    匹配策略：
    1. 关键词匹配（keywords 字段）
    2. 中文别名匹配（aliases 字段，支持"图灵"→"Turing"）
    3. 事件名字串匹配
    """
    text_lower = user_input.lower()
    best_match = None
    best_score = 0

    for event in VERIFIED_KNOWLEDGE_BASE:
        score = 0
        # 关键词匹配
        for kw in event["keywords"]:
            if kw.lower() in text_lower:
                score += 1
        # 别名匹配（中文名/俗称）——权重和关键词一样
        for alias in event.get("aliases", []):
            if alias.lower() in text_lower:
                score += 1
        # 事件名相似度（简单子串匹配）
        event_lower = event["event"].lower()
        user_words = text_lower.split()
        for word in user_words:
            if len(word) >= 3 and word in event_lower:
                score += 0.5

        if score > best_score:
            best_score = score
            best_match = event

    if best_score >= 1:
        return best_match
    return None


def _verified_to_search_results(event: dict) -> list[dict]:
    """将验证库中的事件转为 search_results 格式。"""
    facts = event["facts"]
    return [{
        "title": f"「{event['event']}」已验证史料",
        "content": facts["story"] + "\n\n趣闻：" + facts.get("fun_fact", ""),
        "confidence": "high",
        "verified": True,
        "source": "verified_knowledge_base",
        "key_facts": [
            f"时间：{facts.get('time', '')}",
            f"地点：{facts.get('place', '')}",
            f"人物：{'、'.join(facts.get('people', []))}",
        ],
    }]


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
    verified_event = _search_verified_kb(user_input)

    if verified_event:
        sources = _verified_to_search_results(verified_event)
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
        response = response.strip()
        if response.startswith("```"):
            response = response.split("\n", 1)[1]
            if response.endswith("```"):
                response = response[:-3]

        result = json.loads(response)

        if not result.get("material_sufficient", False):
            return {
                "search_results": [],
                "material_score": 0.0,
                "material_sufficient": False,
                "error_message": f"关于「{user_input}」没有足够资料。试试更知名的计算机历史事件。",
                "suggestions": [e["event"] for e in VERIFIED_KNOWLEDGE_BASE[:5]],
                "status": "failed",
                "agent_logs": [{"agent": "crawler", "action": "insufficient", "detail": "not found in KB or LLM"}],
            }

        sources = result.get("sources", [])
        # 标记为未验证
        for s in sources:
            s["verified"] = False
            s["source"] = "deepseek_knowledge"

        total_chars = sum(len(s.get("content", "")) for s in sources)
        return {
            "search_results": sources,
            "material_score": round(min(total_chars / 3000, 0.85), 2),  # 未验证，最高 0.85
            "material_sufficient": len(sources) >= 1 and total_chars >= 100,
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
            "suggestions": [e["event"] for e in VERIFIED_KNOWLEDGE_BASE[:5]],
            "status": "failed",
            "agent_logs": [{"agent": "crawler", "action": "error", "detail": str(e)}],
        }
