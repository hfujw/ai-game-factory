"""程序 Agent — 从结构化 GameScript 生成有质感的 HTML 游戏。

升级要点：
1. 视觉系统：预置 CSS 变量 + 组件类名，LLM 填空
2. 谜题范式：cipher=符文破译台 / sequence=时间碎片 / logic=星图推演
3. 游戏循环：张力曲线（裂纹递增 + 背景变暗 + 逐层提示）
4. 历史真相：分层展示，石板碎裂动画
"""

import json
from app.graph.state import GameFactoryState
from app.llm_client import agent_log, chat, _strip_markdown_fence
from app.agents.coder_templates_bagu import (
    FILL_BLANK_TEMPLATE, RECITE_TEMPLATE, MATCH_TEMPLATE, DEBUGGER_TEMPLATE
)

BAGU_TEMPLATES = {
    "fill_blank": FILL_BLANK_TEMPLATE,
    "recite": RECITE_TEMPLATE,
    "match": MATCH_TEMPLATE,
    "debugger": DEBUGGER_TEMPLATE,
}

SYSTEM_PROMPT = """你是一个"时间工匠"——将历史事件转化为可交互的 HTML 解谜游戏。

=== 视觉契约 ===
你的 HTML 必须包含以下 artist_pre 提供的 CSS（直接插入 <style> 最前面，不要修改）：
{visual_css}

【画面切换】5个画面div都加 class="screen"。显示/隐藏通过 classList.toggle('active') 实现。
不要直接操作 element.style.display——artist_post 会注入 opacity/scale transition。

【类名建议】优先使用 .rune（按钮）、.panel（面板）、.glyph-input（输入框）。
用不了就用你自己写的，artist_post 会尝试映射。颜色用 CSS 变量 var(--xxx)。

=== 新手引导与沉浸感（⚠️ 最重要——决定玩家会不会玩）===

【开场即入戏】
- 标题画面不是"欢迎来到XX游戏"，而是把玩家直接扔进历史现场
  例："1940年，布莱切利园。一封纳粹密电刚刚被截获。桌上的电报机还在滴答作响。"
- opening_hook 要让人产生"我想知道后面发生了什么"的冲动

【操作引导——让玩家无痛上手】
- 永远不要让玩家"读说明书"。用以下方式替代：
  1. 游戏开始时，第一个可交互元素自动高亮（发光脉冲），暗示"点这里"
  2. 操作反馈即时且明显——点了什么，立刻有颜色/大小/位置变化
  3. 第一轮尝试不扣次数，作为"试玩轮"——让玩家在安全环境里摸索
  4. 关键操作旁边始终有一行小字提示（如"点击字母填入凹槽"），字号小而灰，不干扰但可读
- 玩家卡住 10 秒后，自动浮现第一条 hint（用淡入动画，不要弹窗）

【让谜题有意义——不只是"排顺序"】
- 每个谜题必须回答一个问题："玩家为什么要做这件事？"
- 把答案写进游戏的 narrative 里：
  - cipher：不是"破译这段密码"，而是"这封密电里藏着德军明天的进攻坐标，破解它就能拯救一个城市"
  - sequence：不是"排列事件顺序"，而是"拼凑出 Python 诞生的完整时间线，你才能理解为什么它叫 Python"
  - logic：不是"选出正确答案"，而是"从三条矛盾的史料中推理出真相，揭穿一个被误传 30 年的计算机传说"
- 通关后不只显示"胜利"，要告诉玩家"因为你的破译，盟军成功拦截了补给线，战争缩短了 2 年"——让玩家觉得自己做的事有意义

=== 游戏循环（必须有张力曲线）===
1. #screen-title：显示年份+地点+悬念句（opening_hook），一枚发光的"开始"runes
2. #screen-howto：一句话操作说明 + "开始挑战"按钮
3. #screen-game：谜题交互（按puzzle_type选择范式，见下方）
4. 反馈系统：
   - 每次错误 → 屏幕边框出现裂纹（box-shadow变化）
   - 尝试剩余2次 → 背景变暗（body opacity过渡）
   - 尝试剩余1次 → 自动显示hint[1]（中等提示）
   - 最后1次失败 → 显示正确答案 + 进入结果
5. #screen-result：胜利→石板裂开光芒动画；失败→暗红余烬
6. #screen-history：分层展示history_facts（核心事实/关键细节/延伸思考），铭文风格

=== 谜题范式（根据puzzle.type三选一）===

【cipher — 符文破译台】
布局：中央密文大字(▓符号或乱码) → 下方A-Z字母盘(点击填入) → 凹槽行显示进度(已填=橙色) → "点燃符文"检查按钮
交互：
- 点击字母→填入当前空槽，该字母变暗不可再用
- 检查逐位高亮：正确位=绿色脉冲，错误位=红色闪烁+重置
- 每次提交后，石碑边缘box-shadow变化模拟裂纹
- 3次错误后自动揭示答案

【sequence — 时间碎片】
布局：4-6个"碎片"卡片（不规则圆角+轻微旋转±2deg），可点击交换顺序 → "重组时间线"按钮
交互：
- 点击两个碎片→它们交换位置（transform动画）
- 选中碎片微微浮起(scale 1.05+阴影)
- 提交后：相邻正确碎片之间显示绿色连线；错误碎片泛红弹回
- 全部正确→碎片拼合成完整卷轴（max-height展开）

【logic — 星图推演】
布局：中央问题核心(发光圆点) → 周围线索节点(3-4个小圆点+连线) → 下方3-4个选项(罗盘式菱形)
交互：
- 点击线索节点→展开显示文字(翻卡动画)
- 点击选项→从问题核心到该选项绘制光线(SVG stroke-dashoffset动画)
- 错误→光线变红+断裂；正确→光线变绿
- 每次错误自动显示一条hint

=== 代码约束 ===
- 单文件 <!DOCTYPE html>，内嵌 <style> 和 <script>
- 600 行以内（视觉和动画不能省）
- 不依赖外部库
- gameState 管理所有状态
- history_facts 存为 HISTORY_FACTS 常量
- showScreen(name) 函数切换画面
- 所有屏幕 id：screen-title, screen-howto, screen-game, screen-result, screen-history
- 直接输出代码，不要 markdown 包裹"""


def get_puzzle_meaning(puzzle_type: str, event: str, protagonist: str) -> str:
    """为每种谜题类型生成'为什么这个谜题有意义'的叙事框架。"""
    templates = {
        "cipher": f"玩家扮演{protagonist or '密码破译员'}，截获了关于「{event}」的关键密文。破译它不是为了通关——而是因为密文背后藏着真实的历史转折。",
        "sequence": f"关于「{event}」的时间线被打乱了。玩家需要拼凑出完整的历史顺序，才能理解这件事为什么以这种方式发生。",
        "logic": f"关于「{event}」流传着几种矛盾的说法。玩家需要从史料线索中推理出真相，揭穿被误传的信息。",
    }
    return templates.get(puzzle_type, f"玩家通过解谜，亲身体验「{event}」中的关键历史时刻。")


def coder_node(state: GameFactoryState) -> dict:
    """从结构化 GameScript 生成游戏。支持计算机历史 + 八股两种模式。"""
    puzzle_type = state["puzzle_type"]
    script_data = state.get("script_data", {})
    direction = state.get("selected_direction", {})
    review_feedback = state.get("review_feedback", "")
    search_results = state.get("search_results", [])

    # 八股类型 → 使用对应交互模板
    is_bagu = puzzle_type in BAGU_TEMPLATES
    if is_bagu:
        # 从 search_results 中提取 puzzle_guide（KB 直传）
        puzzle_guide = {}
        for r in search_results:
            if r.get("puzzle_guide"):
                puzzle_guide = r["puzzle_guide"]
                break
        bagu_data_block = f"""
=== Python 面试题数据（注入到 window.__PUZZLE_DATA__）===
{json.dumps(puzzle_guide, ensure_ascii=False)}

=== 原始代码 ===
{script_data.get('original_code', '') or (script_data.get('content', {}) or {}).get('original', '')}

=== 知识点 ===
{json.dumps(script_data.get('annotations', []), ensure_ascii=False)}
"""
        bagu_system = SYSTEM_PROMPT + "\n\n" + BAGU_TEMPLATES[puzzle_type]

    # 如果 writer 给了结构化数据，用它；否则 fallback
    if not script_data:
        try:
            script_data = json.loads(state.get("game_script", "{}"))
        except (json.JSONDecodeError, TypeError):
            script_data = {}

    # 组装 prompt
    event = script_data.get("event", state["user_input"])
    year = script_data.get("year", "")
    location = script_data.get("location", "")
    opening = script_data.get("opening_hook", f"你能解开{event}的秘密吗？")
    protagonist = script_data.get("protagonist", "")
    core_conflict = script_data.get("core_conflict", "")

    puzzle = script_data.get("puzzle", {})
    hints = puzzle.get("hints", [])
    hints_text = "\n".join(f"  L{h.get('level',1)}: {h.get('text','')}" for h in hints) if hints else "  L1: 仔细观察..."

    items = puzzle.get("items_labels", [])
    items_text = ", ".join(f'"{x}"' for x in items) if items else ""

    facts = script_data.get("history_facts", [])
    facts_text = "\n".join(f'  "{f}"' for f in facts) if facts else "（使用剧本中的历史信息）"

    victory = script_data.get("victory_line", "你成功了！")
    defeat = script_data.get("defeat_line", "再试一次。")

    visual = script_data.get("visual", {})
    mood = visual.get("mood", "像素复古")
    atmosphere = script_data.get("atmosphere", mood)

    feedback_block = ""
    if review_feedback:
        feedback_block = f"""
=== 🚨 审查反馈（必须修复）===
{review_feedback}
"""

    # 组装方向信息块
    direction_block = ""
    if direction:
        direction_block = f"""
=== 选定的视觉方向 ===
名称：{direction.get('name', '默认')}
色板：{', '.join(direction.get('palette', []))}
UI风格：{direction.get('ui', '')}
动画节奏：{direction.get('animation', '')}
参考CSS：
{direction.get('reference_css', '')}

请基于上述视觉方向编写游戏。用色板的颜色，遵循UI风格和动画节奏。可以自由发挥，不必逐字复制参考CSS。"""

    prompt = f"""请按契约生成「{puzzle_type}」类型的时间解谜游戏。

⚠️ 最重要的设计原则：
1. 让玩家第一秒就知道该做什么（高亮第一个可交互元素 + 小字提示 + 第一轮不扣次数）
2. 让谜题有意义——玩家破译密码=拯救城市/拼凑时间线=理解历史/推理真相=揭穿传说
3. 通关后告诉玩家"你的行动改变了什么"

【叙事信息——造氛围用】
事件：{event}（{year}）
地点：{location}
主角：{protagonist}
冲突：{core_conflict}
氛围：{atmosphere}
开场悬念：{opening}

【玩家动机——谜题的意义】
{get_puzzle_meaning(puzzle_type, event, protagonist)}

【谜题参数】
类型：{puzzle_type}
表皮：{puzzle.get('surface', '')}
答案：{puzzle.get('answer', '')}
元素数量：{puzzle.get('items_count', len(items))}
元素标签：{items_text}
最大尝试：{puzzle.get('max_attempts', 3)}

【提示层级】
{hints_text}

【历史真相（渲染为故事面板，不是列表）】
标题：{facts.get('title', '') if isinstance(facts, dict) else ''}
故事：{facts.get('story', '') if isinstance(facts, dict) else ''}
核心收获：{facts.get('key_point', '') if isinstance(facts, dict) else ''}
趣闻：{facts.get('fun_fact', '') if isinstance(facts, dict) else ''}
{facts_text if not isinstance(facts, dict) else ''}

⚠️ #screen-history 必须做成故事面板：先显示标题（大字），再显示故事正文（小字、行距大、像在读卷轴），底部标注核心收获和趣闻。不要用 <ul><li> 列表。用 <p> 段落 + 装饰符号（▸ 或 ◈）分隔。

【台词】
通关：{victory}
失败：{defeat}

{feedback_block}
直接输出完整 HTML。"""

    try:
        final_prompt = prompt + direction_block + (bagu_data_block if is_bagu else "")
        final_system = bagu_system if is_bagu else SYSTEM_PROMPT
        # 八股温度更低——要准确，不要惊喜
        temp = 0.1 if is_bagu else 0.3
        code = chat(final_prompt, system=final_system, temperature=temp)
        code = _strip_markdown_fence(code)
        if not code.lower().startswith("<!doctype"):
            code = f"<!DOCTYPE html>\n{code}"

        return {
            "game_code": code,
            "agent_logs": [agent_log("coder", "code_generated", f"{len(code)} chars")],
        }
    except Exception as e:
        fallback = f"""<!DOCTYPE html>
<html lang="zh">
<head><meta charset="UTF-8"><title>生成失败</title></head>
<body style="background:#0d0a08;color:#e8ddd0;font-family:monospace;display:flex;justify-content:center;align-items:center;height:100vh;margin:0">
<div style="text-align:center"><h1 style="color:#e8702a">生成失败</h1><p>{str(e)}</p></div>
</body></html>"""
        return {
            "game_code": fallback,
            "agent_logs": [agent_log("coder", "error", str(e))],
        }
