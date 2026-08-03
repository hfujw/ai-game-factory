"""Artist Pre — LLM 自主视觉设计。

删除所有硬编码方向。让 LLM 读剧本，自主生成 3 个视觉方向并论证选择。
极简 fallback 防止 LLM 崩溃。
"""

import json
from app.llm_client import agent_log, chat, _strip_markdown_fence

DEFAULT_FALLBACK = {
    "name": "默认像素", "mood_tags": ["像素", "复古"],
    "palette": ["#0a0a0a", "#e8702a", "#34d399", "#e8ddd0", "#5a4a3a"],
    "ui": "像素风格基础UI", "animation": "基础淡入淡出",
    "reference_css": "body{background:#0a0a0a;color:#e8ddd0;font-family:monospace}",
    "post": {"crt": False, "particles": "none", "atmosphere": ""}
}

SYSTEM_PROMPT = """你是一个像素风 HTML 游戏的视觉设计师。

基于剧本，自主分析氛围和情绪，生成 3 个不同的视觉设计方向。

每个方向必须说明：
1. 名称 + 与剧本氛围的关联性（引用剧本具体描述）
2. 色板（5个色值）、UI风格（3句话）、动画节奏（1句话）、参考CSS（3-5行）
3. 自评选择最佳方向，说明理由

JSON格式：
{
  "directions": [
    {"name":"...","mood_tags":["..."],"palette":[...],"ui":"...","animation":"...","reference_css":"...","post":{"crt":bool,"particles":"...","atmosphere":"..."}}
  ],
  "selected_index": 0,
  "selection_reasoning": "为什么选这个（引用剧本细节）"
}

要求：3个方向，在交互隐喻/动画节奏/UI形状上明显不同。不要markdown代码块。"""


def artist_pre_node(state: dict) -> dict:
    script = state.get("script_data", {})
    puzzle_type = script.get("puzzle", {}).get("type", "cipher")

    prompt = f"""为以下游戏生成 3 个视觉方向并选择最佳方案。

事件：{script.get('event','')}
类型：{puzzle_type}
氛围：{script.get('atmosphere','')}
情绪：{script.get('mood','')}
时代：{script.get('era','')}
道具：{', '.join(script.get('key_props',[]))}
视觉锚点：{script.get('visual',{}).get('mood','')}

按 system prompt 的 JSON 格式输出。必须包含 selection_reasoning。"""

    try:
        response = chat(prompt, system=SYSTEM_PROMPT, temperature=0.7)
        response = _strip_markdown_fence(response)
        data = json.loads(response)
        directions = data.get("directions", [])
        idx = max(0, min(data.get("selected_index", 0), len(directions) - 1)) if directions else 0
        selected = directions[idx] if directions else DEFAULT_FALLBACK

        return {
            "directions": directions or [DEFAULT_FALLBACK],
            "selected_direction": selected,
            "agent_logs": [agent_log("artist_pre", "designed",
                f"生成{len(directions)}个方向，选择「{selected['name']}」——{data.get('selection_reasoning','')[:60]}")]
        }
    except Exception as e:
        return {
            "directions": [DEFAULT_FALLBACK], "selected_direction": DEFAULT_FALLBACK,
            "agent_logs": [agent_log("artist_pre", "error_fallback", str(e))]
        }
