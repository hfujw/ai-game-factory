"""程序 Agent — 从结构化 GameScript 生成 HTML 游戏（全LLM版）"""

import json
from app.graph.state import GameFactoryState
from app.llm_client import agent_log, chat, _strip_markdown_fence

SYSTEM_PROMPT = """你是一个"时间工匠"——将主题素材转化为可交互的 HTML 解谜游戏。

=== 视觉契约 ===
你的 HTML 必须包含以下 artist_pre 提供的 CSS（直接插入 <style> 最前面，不要修改）：
{visual_css}

【画面切换】5个画面div都加 class="screen"。显示/隐藏通过 classList.toggle('active') 实现。
【类名建议】优先使用 .rune（按钮）、.panel（面板）、.glyph-input（输入框）。颜色用 CSS 变量 var(--xxx)。

=== 新手引导与沉浸感 ===
【开场即入戏】标题画面把玩家直接扔进主题现场
【操作引导】第一轮不扣次数 + 即时反馈 + 小字提示 + 10秒自动浮现hint
【让谜题有意义】cipher=破译密电 / sequence=拼凑时间线 / logic=推理真相

=== 游戏循环 ===
1. #screen-title 2. #screen-howto 3. #screen-game 4. 反馈系统(裂纹+背景变暗+逐层提示)
5. #screen-result 6. #screen-history

=== 谜题范式 ===
【cipher — 符文破译台】中央密文 → A-Z字母盘 → 凹槽行 → "点燃符文"检查
【sequence — 时间碎片】4-6个碎片卡片，点击交换 → "重组时间线"
【logic — 星图推演】中央问题核心 → 周围线索节点 → 3-4个选项

=== 代码约束 ===
- 单文件 <!DOCTYPE html>，内嵌 <style> 和 <script>
- 600 行以内，不依赖外部库
- gameState 管理所有状态，HISTORY_FACTS 常量
- showScreen(name) 函数切换画面
- 所有屏幕 id：screen-title/howto/game/result/history
- 直接输出代码，不要 markdown 包裹"""


def get_puzzle_meaning(puzzle_type: str, event: str, protagonist: str) -> str:
    templates = {
        "cipher": f"玩家扮演{protagonist or '密码破译员'}，截获了关于「{event}」的关键密文。",
        "sequence": f"关于「{event}」的时间线被打乱了。",
        "logic": f"关于「{event}」流传着几种矛盾的说法。",
    }
    return templates.get(puzzle_type, f"玩家通过解谜，亲身体验「{event}」中的关键时刻。")


def coder_node(state: GameFactoryState) -> dict:
    puzzle_type = state["puzzle_type"]
    script_data = state.get("script_data", {})
    direction = state.get("selected_direction", {})
    review_feedback = state.get("review_feedback", "")
    orchestrator_notes = state.get("orchestrator_notes", "")

    if not script_data:
        try:
            script_data = json.loads(state.get("game_script", "{}"))
        except:
            script_data = {}

    event = script_data.get("event", state["user_input"])
    puzzle = script_data.get("puzzle", {})
    hints = puzzle.get("hints", [])
    hints_text = "\n".join(f"  L{h.get('level',1)}: {h.get('text','')}" for h in hints) if hints else "  L1: 仔细观察..."

    facts = script_data.get("history_facts", [])

    feedback_block = ""
    if review_feedback:
        feedback_block = f"\n=== 🚨 审查反馈（必须修复）===\n{review_feedback}\n"

    orchestrator_block = ""
    if orchestrator_notes:
        orchestrator_block = f"\n=== 🎬 协调器备注 ===\n{orchestrator_notes}\n"

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
"""

    prompt = f"""请按契约生成「{puzzle_type}」类型的解谜游戏。

【叙事信息】
事件：{script_data.get('event', state['user_input'])}（{script_data.get('year', '')}）
地点：{script_data.get('location', '')}
主角：{script_data.get('protagonist', '')}
氛围：{script_data.get('atmosphere', '像素复古')}
开场悬念：{script_data.get('opening_hook', '')}

【玩家动机】{get_puzzle_meaning(puzzle_type, event, script_data.get('protagonist', ''))}

【谜题参数】类型：{puzzle_type} | 表皮：{puzzle.get('surface', '')}
答案：{puzzle.get('answer', '')} | 最大尝试：{puzzle.get('max_attempts', 3)}

【提示层级】{hints_text}

【历史真相】{json.dumps(facts, ensure_ascii=False) if facts else ''}

【台词】通关：{script_data.get('victory_line', '')} | 失败：{script_data.get('defeat_line', '')}

{feedback_block}{orchestrator_block}直接输出完整 HTML。"""

    try:
        final_prompt = prompt + direction_block
        code = chat(final_prompt, system=SYSTEM_PROMPT, temperature=0.3)
        code = _strip_markdown_fence(code)
        if not code.lower().startswith("<!doctype"):
            code = f"<!DOCTYPE html>\n{code}"
        return {
            "game_code": code,
            "agent_logs": [agent_log("coder", "code_generated", f"{len(code)} chars")]
        }
    except Exception as e:
        return {
            "game_code": f"<!DOCTYPE html><html lang=zh><head><meta charset=UTF-8><title>Error</title></head><body style=background:#0d0a08;color:#e8ddd0;font-family:monospace;display:flex;justify-content:center;align-items:center;height:100vh><div><h1 style=color:#e8702a>生成失败</h1><p>{e}</p></div></body></html>",
            "agent_logs": [agent_log("coder", "error", str(e))]
        }
