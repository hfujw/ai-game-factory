"""程序 Agent — 从结构化 GameScript 生成有质感的 HTML 游戏。

升级要点：
1. 视觉系统：预置 CSS 变量 + 组件类名，LLM 填空
2. 谜题范式：cipher=符文破译台 / sequence=时间碎片 / logic=星图推演
3. 游戏循环：张力曲线（裂纹递增 + 背景变暗 + 逐层提示）
4. 历史真相：分层展示，石板碎裂动画
"""

import json
from app.graph.state import GameFactoryState
from app.llm_client import chat, _strip_markdown_fence

SYSTEM_PROMPT = """你是一个"时间工匠"——将历史事件转化为可交互的 HTML 解谜游戏。

=== 视觉系统（严格使用这些 CSS 变量，不要自创颜色）===
:root {
  --bg-void: #0d0a08;
  --bg-panel: rgba(20,16,12,0.92);
  --text-ember: #e8ddd0;
  --accent-flame: #e8702a;
  --accent-life: #34d399;
  --accent-ash: #5a4a3a;
  --border-glow: rgba(232,112,42,0.15);
}
.screen { position:fixed; inset:0; display:flex; flex-direction:column; align-items:center; justify-content:center; background:var(--bg-void); transition:opacity 0.5s; }
.panel { background:var(--bg-panel); border:1px solid var(--border-glow); border-radius:4px; padding:24px; max-width:520px; width:90%; }
.rune { background:transparent; border:1px solid var(--accent-flame); color:var(--accent-flame); padding:12px 24px; transition:all .3s; cursor:pointer; font-family:'Courier New',monospace; }
.rune:hover { box-shadow:0 0 16px rgba(232,112,42,0.3); transform:translateY(-2px); }
.rune:disabled { opacity:0.3; cursor:not-allowed; transform:none; }
.glyph { color:var(--accent-flame); }
.glyph::before { content:'▸ '; }

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


def coder_node(state: GameFactoryState) -> dict:
    """从结构化 GameScript 生成游戏。"""
    puzzle_type = state["puzzle_type"]
    script_data = state.get("script_data", {})
    review_feedback = state.get("review_feedback", "")
    search_results = state.get("search_results", [])

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

    prompt = f"""请按契约生成「{puzzle_type}」类型的时间解谜游戏。

【叙事信息】
事件：{event}（{year}）
地点：{location}
主角：{protagonist}
冲突：{core_conflict}
氛围：{atmosphere}
开场悬念：{opening}

【谜题参数】
类型：{puzzle_type}
表皮：{puzzle.get('surface', '')}
答案：{puzzle.get('answer', '')}
元素数量：{puzzle.get('items_count', len(items))}
元素标签：{items_text}
最大尝试：{puzzle.get('max_attempts', 3)}

【提示层级】
{hints_text}

【历史真相】
{facts_text}

【台词】
通关：{victory}
失败：{defeat}

{feedback_block}
直接输出完整 HTML。"""

    try:
        code = chat(prompt, system=SYSTEM_PROMPT, temperature=0.3)
        code = _strip_markdown_fence(code)
        if not code.lower().startswith("<!doctype"):
            code = f"<!DOCTYPE html>\n{code}"

        return {
            "game_code": code,
            "agent_logs": [{"agent": "coder", "action": "code_generated", "detail": f"{len(code)} chars"}],
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
            "agent_logs": [{"agent": "coder", "action": "error", "detail": str(e)}],
        }
