"""共享知识库模块 — 支持双知识库：计算机历史 + Python 八股。"""

import json
import os

_KB_DIR = os.path.dirname(__file__)

# 计算机历史
with open(os.path.join(_KB_DIR, "verified_events.json"), "r", encoding="utf-8") as f:
    EVENTS = json.load(f)

# Python 八股
_BAGU_PATH = os.path.join(_KB_DIR, "verified_bagu.json")
BAGU_EVENTS = []
if os.path.exists(_BAGU_PATH):
    with open(_BAGU_PATH, "r", encoding="utf-8") as f:
        bagu_data = json.load(f)
        BAGU_EVENTS = bagu_data.get("events", [])


def get_all_events(category: str = None) -> list[dict]:
    """返回事件列表。category 可选 'computer_history' / 'bagu' / None(全部)。"""
    if category == "bagu":
        return BAGU_EVENTS
    if category == "computer_history":
        return EVENTS
    return EVENTS + BAGU_EVENTS


def get_event_names(category: str = None) -> list[str]:
    """返回事件名列表。"""
    if category == "bagu":
        return [e["title"] for e in BAGU_EVENTS]
    return [e["event"] for e in EVENTS]


def get_event_by_keyword(text: str, category: str = None) -> dict | None:
    """关键词匹配。category 为 None 时搜索全部。"""
    pools = []
    if category in (None, "computer_history"):
        pools.extend(EVENTS)
    if category in (None, "bagu"):
        pools.extend(BAGU_EVENTS)

    text_lower = text.lower()
    best_match = None
    best_score = 0

    for event in pools:
        score = 0
        # 匹配 keywords
        for kw in event.get("keywords", []):
            if kw.lower() in text_lower:
                score += 1
        # 匹配 aliases
        for alias in event.get("aliases", []):
            if alias.lower() in text_lower:
                score += 1
        # 匹配 title/event 名
        name = event.get("event", event.get("title", ""))
        for word in text_lower.split():
            if len(word) >= 2 and word in name.lower():
                score += 0.5
        if score > best_score:
            best_score = score
            best_match = event

    return best_match if best_score >= 1 else None


def event_to_search_results(event: dict) -> list[dict]:
    """将 KB 事件转为 search_results 格式。兼容计算机历史和八股。"""
    # 八股事件
    if "content" in event and "original" in event.get("content", {}):
        content = event["content"]
        return [{
            "title": f"「{event.get('title', event.get('event', ''))}」",
            "content": f"{content.get('translation', '')}\n\n原始代码：\n{content.get('original', '')}",
            "confidence": "high",
            "verified": True,
            "source": "verified_knowledge_base",
            "key_facts": content.get("annotations", []),
            "atmosphere_tags": event.get("atmosphere_tags", []),
            "key_props": event.get("key_props", []),
            "visual_anchor": event.get("visual_anchor", ""),
            "category": event.get("category", "bagu"),
            "puzzle_guide": event.get("puzzle_guide", {}),
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
