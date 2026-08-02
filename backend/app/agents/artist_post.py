"""Artist Post-Processing Agent V4

两步走：
1. 正则注入（强制，零风险）— CSS变量/screen transition/字体/CRT/氛围
2. 可选 LLM 微调（追加模式，挂了不影响）— 只生成补充CSS，追加到</style>前
"""

import re
from app.llm_client import chat


def inject_screen_transition(html: str) -> str:
    screen_css = """
.screen{position:fixed;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:24px;opacity:0;transform:scale(0.98);transition:opacity 0.5s cubic-bezier(0.16,1,0.3,1),transform 0.5s cubic-bezier(0.16,1,0.3,1);pointer-events:none}
.screen.active{opacity:1;transform:scale(1);pointer-events:auto}
    """
    if ".screen" in html:
        html = re.sub(
            r'(\.screen\s*\{[^}]*)\}',
            r'\1;opacity:0;transform:scale(0.98);transition:opacity 0.5s,transform 0.5s;pointer-events:none}',
            html,
            count=1
        )
        if ".screen.active" not in html:
            html = html.replace("</style>", ".screen.active{opacity:1;transform:scale(1);pointer-events:auto}</style>")
    else:
        html = html.replace("</style>", f"{screen_css}</style>")
    return html


def inject_fonts(html: str) -> str:
    if "fonts.googleapis.com" not in html:
        font_link = '<link href="https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap" rel="stylesheet">'
        html = html.replace("</head>", f"{font_link}</head>")
    return html


def inject_atmosphere(html: str, direction: dict) -> str:
    post = direction.get("post", {})
    if post.get("crt") and "body::after" not in html:
        crt = "body::after{content:"";position:fixed;inset:0;background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,0.03) 2px,rgba(0,0,0,0.03) 4px);pointer-events:none;z-index:9999;}"
        html = html.replace("</style>", f"{crt}</style>")
    atmosphere = post.get("atmosphere", "")
    if atmosphere and "artist_post_atmosphere" not in html:
        html = html.replace("</style>", f"\n/* artist_post_atmosphere */\n{atmosphere}\n</style>")
    return html


def inject_palette_vars(html: str, direction: dict) -> str:
    palette = direction.get("palette", [])
    if len(palette) >= 5:
        var_css = f":root{{--bg:{palette[0]};--primary:{palette[1]};--success:{palette[2]};--text:{palette[3]};--muted:{palette[4]}}}"
        if "<style>" in html:
            html = html.replace("<style>", f"<style>\n{var_css}\n")
        else:
            html = html.replace("</head>", f"<style>{var_css}</style></head>")
    return html


def llm_generate_supplement(existing_css: str, direction: dict) -> str:
    prompt = f"""你是一位 CSS 氛围设计师。现有 CSS 如下：

{existing_css[:2000]}

请只输出"需要补充的 CSS"，包括：
1. 更精细的 @keyframes 动画（通关光芒爆发、粒子飘散）
2. 氛围粒子样式（.particle + 漂移动画）
3. 任何能让视觉更生动的微调

【要求】
- 只输出纯 CSS，不要解释
- 不要覆盖已有选择器，只补充新的
- 如果已有类似动画，跳过
- 总长度控制在 30 行以内"""
    css = chat(prompt, temperature=0.2)
    return css.replace("```css", "").replace("```", "").strip()


def artist_post_node(state: dict) -> dict:
    game_code = state.get("game_code", "")
    direction = state.get("selected_direction", {})

    styled = game_code

    # Step 1: 正则注入（强制）
    styled = inject_palette_vars(styled, direction)
    styled = inject_screen_transition(styled)
    styled = inject_fonts(styled)
    styled = inject_atmosphere(styled, direction)

    # Step 2: 可选 LLM 微调（追加模式）
    try:
        style_match = re.search(r'<style>(.*?)</style>', styled, re.DOTALL)
        if style_match:
            existing = style_match.group(1)
            supplement = llm_generate_supplement(existing, direction)
            if supplement:
                styled = styled.replace(
                    "</style>",
                    f'\n/* === artist_post supplement === */\n{supplement}\n</style>'
                )
    except Exception:
        pass

    return {
        "styled_code": styled,
        "agent_logs": [{"agent": "artist_post", "action": "styled", "detail": f"{len(styled)} chars"}]
    }
