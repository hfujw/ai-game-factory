"""美术 Agent — 注入像素风 CSS 主题。

输入：审查通过的 game_code + script_keywords
输出：styled_code（像素风增强版）

用 DeepSeek 分析游戏代码，注入像素CSS——scanline、像素字体、复古配色。
"""

from app.graph.state import GameFactoryState
from app.llm_client import chat, _strip_markdown_fence

SYSTEM_PROMPT = """你是一个像素风 CSS 艺术家，专精复古游戏视觉设计。你会收到一个 HTML 游戏代码，你的任务是增强它的视觉效果。

⚠️ 铁律：保持原游戏的 JS 逻辑**完全不变**。只改 CSS 和 HTML 结构（可加装饰元素）。

视觉增强清单（按优先级）：
1. **配色升级**：把单调的黑底绿字改为有层次的主题配色。4套可选主题：
   - 绿屏终端：背景#0a0e0a，文字#33ff33，强调色#ffcc00（复古CRT感）
   - 琥珀暖色：背景#1a1005，文字#ffb000，强调色#ff6600（80年代终端）
   - 赛博霓虹：背景#0a0a1a，文字#cc88ff，强调色#00ffff（90年代科幻）
   - GameBoy掌机：背景#9bbc0f，文字#0f380f（掌机原味）
   根据游戏主题选择最合适的一套。解谜/破译选绿屏或琥珀，编程/发明选赛博，休闲选GameBoy。

2. **像素化UI组件**：
   - 按钮：3px实色边框 + box-shadow模拟立体像素边（inset高光+外阴影）
   - 输入框：等宽字体 + 大字号 + 居中 + focus时发光边框
   - 卡片/面板：背景加深一层 + 虚线或实线边框
   - 正确/错误反馈：正确=绿色闪烁，错误=水平震动动画(steps(3))

3. **CRT扫描线效果**：body::after伪元素 + repeating-linear-gradient（每3px一条半透明黑线）

4. **像素字体**：优先用Google Fonts的'Press Start 2P'（需<link>引入），fallback到'Courier New'

5. **动画**：
   - 标题闪烁：opacity在1和0.3之间step切换(1.5s)
   - 正确反馈：边框发光 + 文字变绿
   - 错误反馈：shake动画(0.3s, steps(3), X轴±6px)
   - 按钮hover：轻微位移(1px) + 颜色变化

6. **结果画面**：必须美化胜利/失败画面，包含大标题 + 台词 + "再来一次"像素按钮 + "📜 历史真相"按钮

如果游戏已经用了这些样式就保留并增强，不要替换已有的好设计。
直接输出修改后的完整 HTML，不要加 markdown 包裹，不要解释。"""


def artist_node(state: GameFactoryState) -> dict:
    """注入像素风 CSS 主题。"""
    game_code = state["game_code"]
    puzzle_type = state.get("puzzle_type", "")

    try:
        prompt = f"""谜题类型：{puzzle_type}

原始游戏代码：
{game_code}

请增强这个游戏的视觉风格，保持 JS 逻辑不变，只改 CSS 和 HTML 结构（可加像素风装饰元素）。"""

        styled = chat(prompt, system=SYSTEM_PROMPT, temperature=0.5)
        styled = _strip_markdown_fence(styled)

        if not styled.lower().startswith("<!doctype"):
            styled = game_code  # 如果 LLM 返回不完整，回退到原代码

        return {
            "styled_code": styled,
            "status": "success",
            "agent_logs": [{"agent": "artist", "action": "style_applied", "detail": "pixel theme injected"}],
        }
    except Exception as e:
        # 美术失败不阻塞——返回原代码
        return {
            "styled_code": game_code,
            "status": "success",
            "agent_logs": [{"agent": "artist", "action": "fallback", "detail": f"error: {e}, using original code"}],
        }
