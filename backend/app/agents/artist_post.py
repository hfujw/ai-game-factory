"""artist_post Agent — 两步走：正则注入（必须成功）+ LLM 追加（可选，挂了不影响）。

在 reviewer 之后运行。输入 coder 的 game_code + artist_pre 的 visual_css。
输出最终 styled_code。
"""

import re
import logging
from app.graph.state import GameFactoryState
from app.llm_client import chat, _strip_markdown_fence

logger = logging.getLogger("artist_post")

# ── CRT 扫描线 + 氛围粒子（固定注入，不调 LLM）──
POST_CSS = """
/* === artist_post 增强层 === */
.crt-lines{position:fixed;inset:0;pointer-events:none;z-index:9999;background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,0.03) 2px,rgba(0,0,0,0.03) 4px);animation:crt-flicker .15s infinite}
.particle{position:fixed;width:2px;height:2px;background:var(--accent-flame);border-radius:50%;opacity:.2;pointer-events:none;z-index:9998}
.particle:nth-child(1){top:15%;left:10%;animation:float1 12s linear infinite}
.particle:nth-child(2){top:60%;left:85%;animation:float2 14s linear infinite}
.particle:nth-child(3){top:30%;left:70%;animation:float3 16s linear infinite}
@keyframes float1{0%{transform:translate(0,0)}25%{transform:translate(30px,-20px)}50%{transform:translate(-10px,-40px)}75%{transform:translate(-25px,10px)}100%{transform:translate(0,0)}}
@keyframes float2{0%{transform:translate(0,0)}25%{transform:translate(-25px,-15px)}50%{transform:translate(15px,-35px)}75%{transform:translate(20px,20px)}100%{transform:translate(0,0)}}
@keyframes float3{0%{transform:translate(0,0)}25%{transform:translate(20px,25px)}50%{transform:translate(-30px,15px)}75%{transform:translate(10px,-20px)}100%{transform:translate(0,0)}}
"""

# ── LLM 追加用的 system prompt（只看 CSS 文本，看不到 HTML）──
REFINE_PROMPT = """你是一个 CSS 动画专家。你会收到一份游戏已有的 CSS 代码。

请生成一段**需要追加到 </style> 之前的 CSS**。要求：
1. 补充 @keyframes 动画（通关光芒绽放、错误时边框裂纹、按钮悬浮粒子）
2. 补充视觉微调（面板内边距、文字行高、输入框圆角）
3. 不要重复定义已有选择器，只写新的或覆盖的
4. 输出纯 CSS，不要 markdown 包裹，不要解释"""


def _safe_inject(html: str, anchor: str, css: str) -> str:
    """安全的 CSS 注入：在 anchor 之前插入，如果 anchor 不存在则追加到 </head> 前。"""
    if anchor in html:
        return html.replace(anchor, css + anchor, 1)
    if "</head>" in html:
        return html.replace("</head>", "<style>" + css + "</style>\n</head>", 1)
    return html


def _inject_font(html: str) -> str:
    """注入 Press Start 2P 字体链接（如果尚未引入）。"""
    if "fonts.googleapis.com" in html:
        return html
    font_link = '<link href="https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap" rel="stylesheet">'
    return html.replace("</head>", font_link + "\n</head>", 1)


def _inject_screen_transition(html: str) -> str:
    """给 .screen 补 transition / .active 规则（如果缺失）。"""
    if ".screen.active" in html or '.screen.active' in html:
        return html  # coder 已经写了，不用注入

    screen_css = ".screen{opacity:0;transform:scale(0.98);transition:opacity .5s cubic-bezier(0.16,1,0.3,1),transform .5s cubic-bezier(0.16,1,0.3,1);pointer-events:none}.screen.active{opacity:1;transform:scale(1);pointer-events:auto}"

    if ".screen" in html:
        # .screen 存在但缺 .active → 在 .screen { 块后面追加
        html = re.sub(r'(\.screen\s*\{[^}]*\})', r'\1' + screen_css, html, count=1)
    else:
        html = _safe_inject(html, "</style>", screen_css)
    return html


def _inject_particles(html: str) -> str:
    """在 </body> 前添加 3 个氛围粒子 div（如果有 body 闭合标签）。"""
    if "</body>" not in html:
        return html
    particles = '<div class="particle"></div><div class="particle"></div><div class="particle"></div>'
    return html.replace("</body>", particles + "\n</body>", 1)


def artist_post_node(state: GameFactoryState) -> dict:
    """两步走：正则注入（必须）+ LLM 追加（可选）。"""
    game_code = state.get("game_code", "")
    visual_css = state.get("visual_css", "")

    if not game_code:
        return {
            "styled_code": game_code,
            "status": "success",
            "agent_logs": [{"agent": "artist_post", "action": "skip", "detail": "no game_code"}],
        }

    # ===== 第一步：正则注入（零风险，必须成功）=====
    styled = game_code

    # 确保有 <style> 标签
    if "<style>" not in styled:
        if "</head>" in styled:
            styled = styled.replace("</head>", "<style></style>\n</head>", 1)
        else:
            styled = "<style></style>\n" + styled

    # 1. 注入 artist_pre 的 CSS 契约（放到 <style> 最前面）
    if visual_css:
        styled = _safe_inject(styled, "</style>", visual_css)

    # 2. 注入字体
    styled = _inject_font(styled)

    # 3. 给 .screen 补 transition
    styled = _inject_screen_transition(styled)

    # 4. 注入 CRT 扫描线 + 氛围粒子 CSS
    styled = _safe_inject(styled, "</style>", POST_CSS)

    # 5. 注入 3 个粒子 div
    styled = _inject_particles(styled)

    # ===== 第二步：LLM 追加（可选，挂了不影响）=====
    try:
        # 只提取 <style> 内容给 LLM
        style_match = re.search(r"<style>(.*?)</style>", styled, re.DOTALL)
        if style_match:
            original = style_match.group(1)
            llm_css = chat(original, system=REFINE_PROMPT, temperature=0.3)
            llm_css = _strip_markdown_fence(llm_css)
            if llm_css and len(llm_css) > 20:
                # 追加到 </style> 之前，不替换原有 CSS
                styled = _safe_inject(styled, "</style>", "\n/* === LLM 补充 === */\n" + llm_css + "\n")
                logger.info("LLM 微调成功, %d chars", len(llm_css))
    except Exception as e:
        logger.warning("LLM 微调失败（正则注入结果已可用）: %s", e)

    return {
        "styled_code": styled,
        "status": "success",
        "agent_logs": [{"agent": "artist_post", "action": "styled", "detail": f"injected CSS + particles, final {len(styled)} chars"}],
    }
