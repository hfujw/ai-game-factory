"""统一知识库 — 加载全部示例话题作为搜索素材。"""

import json
import os

_KB_DIR = os.path.dirname(__file__)

def _name(event: dict) -> str:
    """获取事件名。"""
    return event.get("title", "")


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
    title = event.get("title", "")
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
