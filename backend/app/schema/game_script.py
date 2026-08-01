"""GameScript Schema — writer Agent 的结构化输出。

每个字段标注消费方，下游 Agent 按需消费。
writer 必须输出此结构，coder 必须从此结构读取。
"""

# 剧本结构（纯 dict，不使用 pydantic 避免依赖问题）
# 但 writer 的 prompt 要求 LLM 输出以下 JSON 结构：

GAME_SCRIPT_SCHEMA = {
    "event": "string — 历史事件名",
    "year": "number — 发生年份",
    "location": "string — 发生地点",
    "protagonist": "string — 主角/核心人物",
    "antagonist": "string — 对抗方/难题（可以是抽象概念如'时间''密码'）",
    "core_conflict": "string — 核心冲突，一句悬念",
    "atmosphere": "string — 氛围描述，3-5个关键词",
    "opening_hook": "string — 标题画面显示的悬念句，玩家第一眼看到",

    # 谜题层 → coder_agent 消费
    "puzzle": {
        "type": "cipher | sequence | logic",
        "surface": "string — 谜题的'表皮'（玩家看到的场景，如'一封截获的德军密电'）",
        "answer": "string — 正确答案",
        "items_count": "number — 元素数量（sequence 类必填）",
        "items_labels": ["string — 排序/选项标签列表"],
        "hints": [
            {"level": 1, "text": "模糊提示"},
            {"level": 2, "text": "中等提示"},
            {"level": 3, "text": "直接提示"},
        ],
        "max_attempts": 3,
    },

    # 历史层 → coder_agent 消费（通关后展示）
    "history_facts": [
        "string — 核心事实1",
        "string — 核心事实2",
        "string — 延伸思考",
    ],

    # 对话层 → coder_agent 消费
    "victory_line": "string — 通关台词，像素游戏风格，简短",
    "defeat_line": "string — 失败台词，鼓励性，简短",

    # 视觉层 → artist_agent 消费
    "visual": {
        "palette": ["#0d0a08", "#e8702a", "#34d399", "#e8ddd0", "#5a4a3a"],
        "mood": "string — 视觉情绪，如'紧张的战时密码室'",
        "decorations": ["string — 装饰元素描述，如'打字机电报声''羊皮纸纹理'"],
    },
}
