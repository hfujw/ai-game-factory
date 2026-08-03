"""文案 Agent — 输出结构化 GameScript JSON（通用版）"""

import json
from app.graph.state import GameFactoryState
from app.llm_client import chat, _strip_markdown_fence, agent_log

SYSTEM_PROMPT = """你是一个解谜小游戏的编剧。

你的唯一产出是一个严格的 JSON 对象。下游有 2 个 Agent 消费你的输出：
- coder_agent：读 puzzle、history_facts、victory_line、defeat_line、opening_hook
- artist_agent：读 visual.palette、visual.mood、visual.decorations

【输出格式】
{
  "event": "事件名",
  "year": 年份数字,
  "location": "地点",
  "protagonist": "主角名/身份",
  "antagonist": "对抗方",
  "core_conflict": "一句话冲突悬念",
  "atmosphere": "氛围关键词，逗号分隔",
  "opening_hook": "标题画面显示的悬念句",

  "puzzle": {
    "type": "cipher|sequence|logic",
    "surface": "谜题表皮",
    "answer": "正确答案",
    "items_count": 排序类元素数量,
    "items_labels": ["标签1","标签2"],
    "hints": [
      {"level":1, "text":"模糊提示"},
      {"level":2, "text":"中等提示"},
      {"level":3, "text":"直接提示"}
    ],
    "max_attempts": 3
  },

  "history_facts": {
    "title": "小标题",
    "story": "200-300字口语化故事",
    "key_point": "一句话核心收获",
    "fun_fact": "趣闻"
  },

  "victory_line": "通关台词",
  "defeat_line": "失败台词",

  "visual": {
    "palette": ["#0d0a08","#e8702a","#34d399","#e8ddd0","#5a4a3a"],
    "mood": "视觉情绪描述",
    "decorations": ["装饰元素"]
  }
}

【铁律】
- 必须输出合法 JSON，不要 markdown 包裹，不要注释
- puzzle.hints 必须 3 条
- history_facts.story 必须 200-300 字，口语化有画面感
- victory_line 和 defeat_line 各不超过 20 字
- atmosphere 字段优先使用史料中提供的 atmosphere_tags
- visual.decorations 优先使用史料中提供的 key_props
- 所有内容必须基于素材，不编造"""


def writer_node(state: GameFactoryState) -> dict:
    user_input = state["user_input"]
    puzzle_type = state["puzzle_type"]
    puzzle_design = state.get("puzzle_design", {})
    search_results = state.get("search_results", [])

    parts = []
    for r in search_results[:3]:
        title = r.get('title', '')
        story = r.get('content', '')
        facts = r.get('key_facts', [])
        block = f"【{title}】\n"
        if story and len(story) > 50:
            block += story
        elif facts:
            block += "; ".join(facts)
        if r.get("atmosphere_tags"):
            block += f"\n氛围标签：{'、'.join(r['atmosphere_tags'])}"
        if r.get("key_props"):
            block += f"\n关键道具：{'、'.join(r['key_props'])}"
        if r.get("visual_anchor"):
            block += f"\n视觉锚点：{r['visual_anchor']}"
        parts.append(block)
    sources_text = "\n\n".join(parts)

    prompt = f"""主题：{user_input}
谜题类型：{puzzle_type}
谜题机制：{puzzle_design.get('mechanic', '')}
规则：{puzzle_design.get('rules', '')}

素材：
{sources_text if sources_text else '（使用你的知识）'}

请输出完整 GameScript JSON。puzzle.type 必须是 {puzzle_type}。"""

    try:
        raw = chat(prompt, system=SYSTEM_PROMPT, temperature=0.5)
        cleaned = _strip_markdown_fence(raw)
        script = json.loads(cleaned)

        if "puzzle" not in script:
            script["puzzle"] = {}
        script["puzzle"]["type"] = puzzle_type
        if "max_attempts" not in script["puzzle"]:
            script["puzzle"]["max_attempts"] = 3
        if "hints" not in script["puzzle"] or not script["puzzle"]["hints"]:
            script["puzzle"]["hints"] = [
                {"level": 1, "text": "再仔细看看..."},
                {"level": 2, "text": "注意关键线索"},
                {"level": 3, "text": "答案就在眼前"},
            ]

        return {
            "game_script": json.dumps(script, ensure_ascii=False),
            "script_data": script,
            "script_keywords": [user_input, puzzle_type],
            "agent_logs": [agent_log("writer", "script_written",
                           f"topic={script.get('event', user_input)}, chars={len(raw)}")],
        }
    except Exception as e:
        fallback = {
            "event": user_input,
            "puzzle": {
                "type": puzzle_type,
                "surface": puzzle_design.get("mechanic", ""),
                "answer": puzzle_design.get("win_condition", ""),
                "hints": [
                    {"level": 1, "text": "仔细看看线索..."},
                    {"level": 2, "text": "也许换个思路"},
                    {"level": 3, "text": "答案可能很简单"},
                ],
                "max_attempts": 3,
            },
            "history_facts": {
                "title": "关于这个主题",
                "story": "（素材解析失败）",
                "key_point": "每个主题背后都有一个有趣的故事。",
                "fun_fact": "",
            },
            "victory_line": "你成功了！",
            "defeat_line": "没关系，再试一次。",
            "visual": {"mood": "像素复古"},
        }
        return {
            "game_script": json.dumps(fallback, ensure_ascii=False),
            "script_data": fallback,
            "script_keywords": [user_input, puzzle_type],
            "agent_logs": [agent_log("writer", "fallback", str(e))],
        }
