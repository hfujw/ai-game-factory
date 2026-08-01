"""共享知识库模块 — 单例加载，所有 Agent 共用。

避免 crawler / reviewer / main 三处重复加载 verified_events.json。
"""

import json
import os

_KB_PATH = os.path.join(os.path.dirname(__file__), "verified_events.json")

with open(_KB_PATH, "r", encoding="utf-8") as f:
    EVENTS = json.load(f)


def get_all_events() -> list[dict]:
    """返回全部验证事件。"""
    return EVENTS


def get_event_names() -> list[str]:
    """返回事件名列表（用于失败推荐）。"""
    return [e["event"] for e in EVENTS]


def get_event_by_keyword(text: str) -> dict | None:
    """关键词匹配事件。返回匹配的事件或 None。"""
    text_lower = text.lower()
    best_match = None
    best_score = 0

    for event in EVENTS:
        score = 0
        for kw in event.get("keywords", []):
            if kw.lower() in text_lower:
                score += 1
        for alias in event.get("aliases", []):
            if alias.lower() in text_lower:
                score += 1
        event_lower = event["event"].lower()
        for word in text_lower.split():
            if len(word) >= 3 and word in event_lower:
                score += 0.5
        if score > best_score:
            best_score = score
            best_match = event

    return best_match if best_score >= 1 else None


def event_to_search_results(event: dict) -> list[dict]:
    """将 KB 事件转为 search_results 格式。"""
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
    }]
