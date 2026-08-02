"""文案 Agent — 输出结构化 GameScript JSON。

下游 coder/artist 按字段消费，不再从散文里猜信息。
"""

import json
from app.graph.state import GameFactoryState
from app.llm_client import chat, _strip_markdown_fence, agent_log

SYSTEM_PROMPT = """你是一个历史教育像素游戏的编剧。

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
  "opening_hook": "标题画面显示的悬念句，让玩家想点开始",

  "puzzle": {
    "type": "cipher|sequence|logic",
    "surface": "谜题表皮——玩家看到的场景描述，如'一封截获的德军密电'",
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
    "title": "一段吸引人的小标题，如'一台机器如何改变战争走向'",
    "story": "200-300字的历史小故事。用口语化、有画面感的语言讲述。包含具体的人物、场景、细节、趣闻。像朋友聊天一样，让人读完能随口讲给别人听。不要教科书腔。",
    "key_point": "一句话核心收获——读者读完能记住的东西",
    "fun_fact": "一条鲜为人知的趣闻"
  },

  "victory_line": "像素风通关台词，简短有力",
  "defeat_line": "像素风失败鼓励台词，简短",

  "visual": {
    "palette": ["#0d0a08","#e8702a","#34d399","#e8ddd0","#5a4a3a"],
    "mood": "视觉情绪描述",
    "decorations": ["装饰元素1","装饰元素2"]
  }
}

【铁律】
- 必须输出合法 JSON，不要 markdown 包裹，不要注释
- puzzle.hints 必须 3 条，level 1→2→3 从模糊到直接
- history_facts.story 必须 200-300 字，口语化有画面感，像朋友聊天讲故事
- victory_line 和 defeat_line 各不超过 20 字
- atmosphere 字段优先使用史料中提供的 atmosphere_tags
- visual.decorations 优先使用史料中提供的 key_props
- visual.mood 优先参考史料中提供的 visual_anchor
- 所有内容必须基于史料，不编造"""


def writer_node(state: GameFactoryState) -> dict:
    """基于史料 + 谜题机制 → LLM 输出结构化 GameScript JSON。"""
    user_input = state["user_input"]
    puzzle_type = state["puzzle_type"]
    puzzle_design = state.get("puzzle_design", {})
    search_results = state.get("search_results", [])

    # 拼史料（story + 新字段）
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
        # V4: 附加美术/氛围数据
        if r.get("atmosphere_tags"):
            block += f"\n氛围标签：{'、'.join(r['atmosphere_tags'])}"
        if r.get("key_props"):
            block += f"\n关键道具：{'、'.join(r['key_props'])}"
        if r.get("visual_anchor"):
            block += f"\n视觉锚点：{r['visual_anchor']}"
        parts.append(block)
    sources_text = "\n\n".join(parts)

    prompt = f"""历史事件：{user_input}
谜题类型：{puzzle_type}
谜题机制：{puzzle_design.get('mechanic', '')}
规则：{puzzle_design.get('rules', '')}

史料：
{sources_text if sources_text else '（使用你的知识）'}

请输出完整 GameScript JSON。puzzle.type 必须是 {puzzle_type}。"""

    try:
        raw = chat(prompt, system=SYSTEM_PROMPT, temperature=0.5)
        cleaned = _strip_markdown_fence(raw)
        script = json.loads(cleaned)

        # 确保必填字段存在
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
            "game_script": json.dumps(script, ensure_ascii=False),  # 存为 JSON 字符串，兼容 state
            "script_data": script,  # 结构化数据，coder 可以直接读
            "script_keywords": [user_input, puzzle_type],
            "agent_logs": [agent_log("writer", "script_written",
                           f"topic={script.get('event',user_input)}, chars={len(raw)}")],
        }
    except Exception as e:
        # JSON 解析失败 → 回退到纯文本，但标记给 coder
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
                "title": "关于这个事件",
                "story": "（史料解析失败，请使用剧本中的历史信息）",
                "key_point": "每个技术突破背后都有一个有趣的故事。",
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
