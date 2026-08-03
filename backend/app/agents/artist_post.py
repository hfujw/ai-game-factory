"""Artist Post-Processing Agent V4

两步走：
1. BS4 注入（强制，零风险）— CSS变量/screen transition/字体/CRT/氛围
2. 可选 LLM 微调（追加模式，挂了不影响）— 只生成补充CSS，追加到 <style> 内
"""

import re
from bs4 import BeautifulSoup
from app.llm_client import agent_log, chat, _strip_markdown_fence


def _safe_append_css(soup, css: str):
    """安全追加 CSS 到 <style> 标签末尾（自动创建 <style> 如果不存在）。"""
    if not soup.head:
        soup.insert(0, soup.new_tag('head'))
    style_tag = soup.find('style')
    if not style_tag:
        style_tag = soup.new_tag('style')
        soup.head.append(style_tag)
    if style_tag.string:
        style_tag.string += '\n' + css
    else:
        style_tag.string = css


def _safe_append_head(html: str, tag_html: str) -> str:
    """安全追加内容到 </head> 之前。"""
    soup = BeautifulSoup(html, 'html.parser')
    if not soup.head:
        soup.insert(0, soup.new_tag('head'))
    link = BeautifulSoup(tag_html, 'html.parser')
    soup.head.append(link)
    return str(soup)


def inject_screen_transition(html: str) -> str:
    """BS4 注入 .screen transition——不再用字符串 replace。"""
    screen_css = ".screen{opacity:0;transform:scale(0.98);transition:opacity 0.5s,transform 0.5s;pointer-events:none}.screen.active{opacity:1;transform:scale(1);pointer-events:auto}"
    soup = BeautifulSoup(html, 'html.parser')
    _safe_append_css(soup, screen_css)
    return str(soup)


def inject_fonts(html: str) -> str:
    """BS4 安全注入字体链接。"""
    if "fonts.googleapis.com" in html:
        return html
    return _safe_append_head(html, '<link href="https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap" rel="stylesheet">')


def inject_atmosphere(html: str, direction: dict) -> str:
    """BS4 安全注入 CRT + 氛围 CSS（不再字符串 replace）。"""
    soup = BeautifulSoup(html, 'html.parser')
    post = direction.get("post", {})
    if post.get("crt"):
        _safe_append_css(soup, "body::after{content:\"\";position:fixed;inset:0;background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,0.03) 2px,rgba(0,0,0,0.03) 4px);pointer-events:none;z-index:9999;}")
    atmosphere = post.get("atmosphere", "")
    if atmosphere:
        _safe_append_css(soup, "/* artist_post_atmosphere */\n" + atmosphere)
    return str(soup)


def inject_palette_vars(html: str, direction: dict) -> str:
    """BS4 安全注入 CSS 变量。"""
    palette = direction.get("palette", [])
    if len(palette) < 5:
        return html
    var_css = f":root{{--bg:{palette[0]};--primary:{palette[1]};--success:{palette[2]};--text:{palette[3]};--muted:{palette[4]}}}"
    soup = BeautifulSoup(html, 'html.parser')
    _safe_append_css(soup, var_css)
    return str(soup)


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
    return _strip_markdown_fence(css)


def artist_post_node(state: dict) -> dict:
    game_code = state.get("game_code", "")
    direction = state.get("selected_direction", {})

    styled = game_code

    # Step 1: 正则注入（强制）
    styled = inject_palette_vars(styled, direction)
    styled = inject_screen_transition(styled)
    styled = inject_fonts(styled)
    styled = inject_atmosphere(styled, direction)

    # Step 2: 可选 LLM 微调（追加模式，BS4 注入）
    try:
        soup = BeautifulSoup(styled, 'html.parser')
        style_tag = soup.find('style')
        if style_tag and style_tag.string:
            existing = style_tag.string
            supplement = llm_generate_supplement(existing, direction)
            if supplement and len(supplement) > 20:
                _safe_append_css(soup, '/* === artist_post supplement === */\n' + supplement)
                styled = str(soup)
    except Exception:
        pass

    return {
        "styled_code": styled,
        "status": "success",
        "agent_logs": [agent_log("artist_post", "styled", f"{len(styled)} chars")]
    }
