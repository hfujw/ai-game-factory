"""artist_pre Agent — 零 LLM 调用，用条件模板生成 CSS 视觉契约。

在 coder 之前运行，输出一份 CSS 文本块。
Coder 将其插入 <style> 最前面，按契约书写 HTML 和交互。
"""

from app.graph.state import GameFactoryState

# 基础 CSS 契约（所有谜题共用）
BASE_CSS = """\
:root{
  --bg-void:#0a0a0a;--bg-panel:rgba(20,16,12,0.92);--text-ember:#e8ddd0;
  --text-dim:rgba(232,221,208,0.5);--accent-flame:#e8702a;
  --accent-flame-glow:rgba(232,112,42,0.3);--accent-life:#34d399;
  --accent-life-glow:rgba(52,211,153,0.3);--accent-ash:#5a4a3a;
  --accent-danger:#dc2626;--font-title:'Press Start 2P','Courier New',monospace;
  --font-body:'Courier New',monospace;--font-size-title:24px;
  --font-size-body:16px;--font-size-small:12px
}
body{
  background:radial-gradient(ellipse at 50% 30%,#1a1410,#0a0a0a);
  color:var(--text-ember);font-family:var(--font-body);
  font-size:var(--font-size-body);margin:0;overflow:hidden;
  box-shadow:inset 0 0 40px rgba(0,0,0,0.8)
}
::selection{background:rgba(232,112,42,0.3);color:#fff}
.rune{
  display:inline-block;background:transparent;
  border:1px solid var(--accent-flame);color:var(--accent-flame);
  padding:12px 28px;font-family:var(--font-body);font-size:14px;
  letter-spacing:2px;text-transform:uppercase;cursor:pointer;
  transition:all .3s cubic-bezier(0.16,1,0.3,1)
}
.rune:hover{background:rgba(232,112,42,0.1);box-shadow:0 0 20px var(--accent-flame-glow);transform:translateY(-2px)}
.rune:active{transform:translateY(0) scale(0.98)}
.rune:disabled{opacity:.3;border-color:var(--accent-ash);color:var(--accent-ash);cursor:not-allowed}
.panel{
  background:var(--bg-panel);border:1px solid rgba(232,112,42,0.12);
  border-radius:4px;padding:24px;position:relative
}
.panel::before,.panel::after{content:"◈";position:absolute;color:var(--accent-flame);opacity:.2;font-size:10px}
.panel::before{top:8px;left:8px}.panel::after{bottom:8px;right:8px}
.glyph-input{
  background:rgba(255,255,255,0.04);border:1px solid var(--accent-ash);
  color:var(--text-ember);padding:12px 16px;font-family:var(--font-body);
  font-size:16px;outline:none;transition:all .3s
}
.glyph-input:focus{border-color:var(--accent-flame);box-shadow:0 0 0 2px rgba(232,112,42,0.15)}
.screen{
  position:fixed;inset:0;display:flex;flex-direction:column;
  align-items:center;justify-content:center;padding:24px
}
@keyframes shake{0%,100%{transform:translateX(0)}20%{transform:translateX(-4px)}40%{transform:translateX(4px)}60%{transform:translateX(-2px)}80%{transform:translateX(2px)}}
.feedback-error{animation:shake .4s ease;border-color:var(--accent-danger)!important}
.feedback-success{box-shadow:0 0 20px var(--accent-life-glow);border-color:var(--accent-life)!important}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
@keyframes crt-flicker{0%,100%{opacity:1}50%{opacity:.98}}
"""

# 谜题类型微调
PUZZLE_OVERRIDES = {
    "cipher":   ".rune{border-width:2px}",           # 密码机按键感
    "sequence": ".panel{border-radius:8px}",          # 卷轴感
    "logic":    ".glyph-input{clip-path:polygon(50% 0%,100% 50%,50% 100%,0% 50%)}",  # 菱形符文
}


def artist_pre_node(state: GameFactoryState) -> dict:
    """基于 puzzle_type 输出 CSS 视觉契约。零 LLM 调用。"""
    puzzle_type = state.get("puzzle_type", "cipher")

    css = BASE_CSS
    if puzzle_type in PUZZLE_OVERRIDES:
        css += PUZZLE_OVERRIDES[puzzle_type]

    return {
        "visual_css": css,
        "agent_logs": [{"agent": "artist_pre", "action": "designed",
                       "detail": f"{puzzle_type} theme (template, {len(css)} chars)"}],
    }
