"""Artist Pre-Processing Agent V4"""

import hashlib
import json
import re
from app.llm_client import chat

# 情绪同义词表
MOOD_SYNONYMS = {
    "紧张": ["紧张", "焦虑", "紧迫", "危急", "压迫", "窒息", "激烈", "惊悚", "紧绷"],
    "理智": ["理智", "冷静", "理性", "逻辑", "清晰", "沉着", "分析", "推演", "计算"],
    "悬疑": ["悬疑", "神秘", "未知", "迷雾", "阴谋", "暗涌", "诡谲", "谜团"],
    "悲壮": ["悲壮", "沉重", "牺牲", "史诗", "宏大", "苍凉", "壮烈", "挽歌"],
    "浪漫": ["浪漫", "诗意", "温暖", "怀旧", "柔情", "抒情", "感伤", "优美"],
    "机械": ["机械", "工业", "齿轮", "蒸汽", "硬核", "精密", "冰冷", "金属"],
    "自然": ["自然", "生机", "苔藓", "森林", "有机", "生长", "野性", "原始"],
}

SYSTEM_PROMPT = """你是一个像素风 HTML 游戏的视觉设计师。

基于输入的剧本，生成 2 个不同的视觉设计方向。

输出 JSON 格式（不要 markdown 代码块）：
{
  "directions": [
    {
      "name": "方向名",
      "mood_tags": ["紧张"],
      "palette": ["#0a0a0a", "#e8702a", "#34d399", "#e8ddd0", "#5a4a3a"],
      "ui": "3句话描述UI风格",
      "animation": "1句话描述动画节奏",
      "reference_css": "3-5行核心CSS",
      "post": {"crt": true, "particles": "ember", "atmosphere": "body::after{...}"}
    }
  ]
}

硬性要求：
1. 每个 puzzle_type 输出 2 个方向
2. 方向在"交互隐喻、动画节奏、UI形状"上明显不同
3. mood_tags 只写 1-2 个核心词
4. palette 5 个色值，对齐主题
5. reference_css 只要 3-5 行
6. post.atmosphere 是一段完整 CSS"""


def expand_mood_tags(tags):
    expanded = set()
    for tag in tags:
        expanded.add(tag)
        if tag in MOOD_SYNONYMS:
            expanded.update(MOOD_SYNONYMS[tag])
    return expanded


def calculate_mood_score(direction, mood_text, atmosphere_text):
    combined = (mood_text + " " + atmosphere_text).lower()
    tags = expand_mood_tags(direction.get("mood_tags", []))
    return sum(1 for tag in tags if tag.lower() in combined)


def select_direction(directions, script_data):
    mood = script_data.get("mood", "")
    atmo = script_data.get("atmosphere", "")
    event = script_data.get("event", "")
    scores = [(calculate_mood_score(d, mood, atmo), d) for d in directions]
    scores.sort(key=lambda x: x[0], reverse=True)
    if len(scores) == 1 or scores[0][0] > scores[1][0]:
        return scores[0][1]
    hash_val = int(hashlib.md5(event.encode()).hexdigest(), 16)
    return directions[hash_val % len(directions)]


def validate_directions(directions, puzzle_type):
    if len(directions) != 2:
        return False, f"期望2个方向，得到{len(directions)}个"
    required = ["name", "mood_tags", "palette", "ui", "animation", "reference_css", "post"]
    for i, d in enumerate(directions):
        for key in required:
            if key not in d:
                return False, f"方向{i+1}缺少{key}"
        if len(d.get("palette", [])) != 5:
            return False, f"方向{i+1} palette不是5个色值"
    return True, "ok"


# 默认方向（fallback）
DEFAULT_DIRECTIONS = {
    "cipher": [
        {"name": "战时密码室", "mood_tags": ["紧张"], "palette": ["#0a0a0a", "#e8702a", "#34d399", "#e8ddd0", "#5a4a3a"], "ui": "厚重2px边框方形按钮，暗角符文面板，凿刻凹槽输入框", "animation": "沉重机械感，顿挫节奏，错误时剧烈震动", "reference_css": ".rune{border:2px solid #e8702a;padding:14px 32px;font-size:13px;letter-spacing:3px}.panel{border-radius:2px;border:1px solid rgba(232,112,42,0.2)}", "post": {"crt": True, "particles": "ember", "atmosphere": "body::after{content:;position:fixed;inset:0;background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,0.04) 2px,rgba(0,0,0,0.04) 4px);pointer-events:none;z-index:9999;}"}},
        {"name": "密函工作室", "mood_tags": ["理智"], "palette": ["#0a0a0a", "#c4a574", "#34d399", "#e8ddd0", "#5a4a3a"], "ui": "不规则圆角纸张纹理按钮，火漆印面板，羽毛笔输入框", "animation": "轻柔纸张感，流畅滑动，像翻阅古老信件", "reference_css": ".rune{border:1px solid #c4a574;border-radius:12px 4px 12px 4px;padding:12px 28px}.panel{background:rgba(20,16,12,0.9);border:1px solid rgba(196,165,116,0.15)}", "post": {"crt": False, "particles": "dust", "atmosphere": "body::after{content:;position:fixed;inset:0;background:radial-gradient(circle at 80% 20%,rgba(196,165,116,0.03),transparent 50%);pointer-events:none;}"}}
    ],
    "sequence": [
        {"name": "古典卷轴", "mood_tags": ["浪漫"], "palette": ["#0a0a0a", "#c4a574", "#34d399", "#e8ddd0", "#5a4a3a"], "ui": "8px大圆角羊皮纸纹理，火漆封边，拖拽时有纸张飘动感", "animation": "轻柔展开，像古老卷轴在时间中缓缓铺陈", "reference_css": ".rune{border:1px solid #c4a574;border-radius:8px;background:rgba(196,165,116,0.05)}.panel{border-radius:8px;border:1px solid rgba(196,165,116,0.12)}", "post": {"crt": False, "particles": "none", "atmosphere": "body::after{content:;position:fixed;inset:0;background:radial-gradient(ellipse at 50% 100%,rgba(196,165,116,0.04),transparent 60%);pointer-events:none;}"}},
        {"name": "工业时间线", "mood_tags": ["机械"], "palette": ["#0a0a0a", "#e8702a", "#34d399", "#e8ddd0", "#5a4a3a"], "ui": "齿轮边框金属质感按钮，铆钉面板，咔哒作响的机械输入", "animation": "咔哒机械声，齿轮咬合感，每次操作有顿挫反馈", "reference_css": ".rune{border:1px solid #e8702a;border-radius:2px;box-shadow:inset 0 0 8px rgba(232,112,42,0.1)}.panel{border:1px solid rgba(232,112,42,0.15);background:linear-gradient(180deg,rgba(20,16,12,0.95),rgba(10,10,10,0.98))}", "post": {"crt": True, "particles": "ember", "atmosphere": "body::after{content:;position:fixed;inset:0;background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,0.04) 2px,rgba(0,0,0,0.04) 4px);pointer-events:none;z-index:9999;}"}}
    ],
    "logic": [
        {"name": "深空星图", "mood_tags": ["悬疑"], "palette": ["#0a0a1a", "#6366f1", "#34d399", "#e8ddd0", "#4a4a6a"], "ui": "菱形符文按钮，光线连线，罗盘方位选项，深空背景", "animation": "神秘缓慢，光线逐段绘制，像星图在黑暗中自显", "reference_css": ".rune{clip-path:polygon(50% 0%,100% 50%,50% 100%,0% 50%);padding:16px 24px;border:none;background:rgba(99,102,241,0.1)}.panel{border:1px solid rgba(99,102,241,0.15);background:rgba(10,10,26,0.92)}", "post": {"crt": False, "particles": "star", "atmosphere": "body::after{content:;position:fixed;inset:0;background:radial-gradient(circle at 50% 50%,rgba(99,102,241,0.05),transparent 70%);pointer-events:none;}"}},
        {"name": "推演沙盘", "mood_tags": ["理智"], "palette": ["#0a0a0a", "#e8702a", "#34d399", "#e8ddd0", "#5a4a3a"], "ui": "几何网格方块按钮，沙盘质感面板，滑动式选项", "animation": "理性干脆，方块滑动对齐，正确时有清脆咬合感", "reference_css": ".rune{border:1px solid #5a4a3a;border-radius:2px;padding:12px 24px;font-size:14px}.panel{border:1px solid rgba(90,74,58,0.2);background:rgba(20,16,12,0.95)}", "post": {"crt": False, "particles": "none", "atmosphere": "body::after{content:;position:fixed;inset:0;background:linear-gradient(90deg,transparent 49%,rgba(90,74,58,0.03) 50%,transparent 51%);background-size:40px 100%;pointer-events:none;}"}}
    ]
}


def artist_pre_node(state: dict) -> dict:
    script = state.get("script_data", {})
    puzzle_type = script.get("puzzle", {}).get("type", "cipher")

    prompt = f"""请为以下历史游戏生成 2 个视觉设计方向。

事件：{script.get("event", "")}
类型：{puzzle_type}
氛围：{script.get("atmosphere", "")}
情绪：{script.get("mood", "")}
时代：{script.get("era", "")}
道具：{", ".join(script.get("key_props", []))}

严格按 system prompt 的 JSON 格式输出。"""

    try:
        response = chat(prompt, system=SYSTEM_PROMPT, temperature=0.5)
        response = response.replace("```json", "").replace("```", "").strip()
        data = json.loads(response)
        directions = data.get("directions", [])

        valid, msg = validate_directions(directions, puzzle_type)
        if not valid:
            raise ValueError(f"验证失败: {msg}")

        selected = select_direction(directions, script)

        return {
            "directions": directions,
            "selected_direction": selected,
            "agent_logs": [{"agent": "artist_pre", "action": "designed", "detail": f"{puzzle_type}: {directions[0]['name']} vs {directions[1]['name']}, selected={selected['name']}"}]
        }

    except Exception as e:
        fallback = DEFAULT_DIRECTIONS.get(puzzle_type, DEFAULT_DIRECTIONS["cipher"])
        selected = select_direction(fallback, script)
        return {
            "directions": fallback,
            "selected_direction": selected,
            "agent_logs": [{"agent": "artist_pre", "action": "error_fallback", "detail": str(e)}]
        }
