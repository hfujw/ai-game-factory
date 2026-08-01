"""程序 Agent — 基于结构化契约生成 HTML 解谜游戏。

契约驱动：prompt 中规定了必须存在的 HTML id、JS 对象和状态机，
审查 Agent 可以直接用正则验证这些结构要素是否存在，无需 LLM 猜测。
"""

from app.graph.state import GameFactoryState
from app.llm_client import chat, _strip_markdown_fence

SYSTEM_PROMPT = """你是一个像素风 HTML 游戏开发者。你必须严格遵循下面的「游戏契约」生成代码。

=== 游戏契约（必须全部满足） ===

【HTML 结构契约】必须包含以下 id 的 div：
- #screen-title  — 标题画面：游戏名<h1> + 像素装饰框 + 一句话故事 + "开始"按钮
- #screen-howto  — 操作说明：2-3句话教玩家怎么玩 + "开始挑战"按钮
- #screen-game   — 游戏主体：谜题交互区，玩家能点/输入/拖
- #screen-result — 结果画面：胜利🎉/失败💀 + 台词 + "📜 历史真相"按钮 + "再来一次"按钮
- #screen-history — 历史真相面板：默认隐藏，点按钮展开，显示史料

【JS 状态机契约】必须包含：
- const HISTORY_FACTS = [...]  — 史料数组，至少3条
- const gameState = { phase: 'title', attempts: 0, maxAttempts: 3 }  — 状态对象
- function showScreen(name)  — 切换画面：隐藏所有 screen-* div，只显示 name 对应的
- function handleInput(action)  — 处理玩家输入的统一入口

【谜题契约】按类型实现：
- cipher：显示密文+解密线索 → 玩家输入明文 → 逐字检查 → 绿色=对/红色=错
- sequence：4-6张打乱的事件卡片 → 玩家点击排列 → 点"提交"检查顺序
- logic：3-4条线索 → 玩家从3-4个选项中选择 → 选错给提示 + 扣次数

【视觉契约】：
- 字体 'Courier New' 或 'Press Start 2P'
- 背景 #0a0a0a，主文字 #33ff33（终端绿）
- 按钮：border: 3px solid #33ff33; box-shadow: 4px 4px 0 #0a0;
- 失败/成功操作有颜色变化反馈（红/绿闪烁）

【交互契约】：
- 支持鼠标点击 + 键盘 Enter
- 最多 3 次尝试，显示剩余次数
- 3 次失败后自动显示正确答案 + 历史真相
- 胜利后必须显示"📜 历史真相"按钮，点击展开 HISTORY_FACTS

【代码约束】：
- 单文件 <!DOCTYPE html>，内嵌 <style> 和 <script>
- 400行以内
- 不依赖外部库
- 直接输出代码，不要 markdown 代码块包裹"""


def coder_node(state: GameFactoryState) -> dict:
    """基于剧本 + 谜题机制 → 按契约生成游戏代码。"""
    puzzle_type = state["puzzle_type"]
    game_script = state["game_script"]
    puzzle_design = state.get("puzzle_design", {})
    review_feedback = state.get("review_feedback", "")
    search_results = state.get("search_results", [])

    # 史料
    history_items = []
    for r in search_results[:3]:
        title = r.get("title", "")
        facts = r.get("key_facts", []) or [r.get("content", "")[:200]]
        for f in facts:
            history_items.append(f"{title}: {f}" if title else f)

    feedback_block = ""
    if review_feedback:
        feedback_block = f"""
=== 🚨 上一版审查不通过，以下问题必须修复 ===
{review_feedback}
=== 请重新生成，确保修复上述所有问题 ===
"""

    prompt = f"""请严格按照契约生成「{puzzle_type}」类型的解谜游戏。

【游戏剧本】
{game_script}

【谜题参数】
类型：{puzzle_type}
机制：{puzzle_design.get('mechanic', '')}
规则：{puzzle_design.get('rules', '')}
通关条件：{puzzle_design.get('win_condition', '')}

【史料（填入 HISTORY_FACTS 数组）】
{chr(10).join(f"- {h}" for h in history_items) if history_items else '（使用剧本中的历史信息）'}

{feedback_block}
直接输出完整 HTML，不要加解释。"""

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
<body style="background:#0a0a0a;color:#ff4444;font-family:monospace;display:flex;justify-content:center;align-items:center;height:100vh;">
<div style="text-align:center">
<h1>游戏代码生成失败</h1><p>{str(e)}</p><p>请重试或换个历史事件</p>
</div></body></html>"""
        return {
            "game_code": fallback,
            "agent_logs": [{"agent": "coder", "action": "error", "detail": str(e)}],
        }
