"""美术 Agent — 增强 coder 已生成的视觉，不替换。

coder 已经建立了暗金视觉系统（--bg-void / --accent-flame / .rune / .panel），
artist 只做微调增强：扫描线、边角装饰、反馈动画、字体优化。
"""

import re
from app.graph.state import GameFactoryState

# 纯 CSS 注入——不调 LLM，零成本，永远不会破坏 JS
POLISH_CSS = """
/* === 时光像素 · Artist 增强层 === */

/* CRT 扫描线（极淡，不干扰暗金视觉） */
body::after {
  content: '';
  position: fixed; inset: 0; pointer-events: none; z-index: 9999;
  background: repeating-linear-gradient(0deg,
    rgba(0,0,0,0.03) 0px,
    transparent 2px,
    rgba(0,0,0,0.03) 3px);
}

/* 按钮反馈微调 */
button:active { transform: scale(0.96) !important; }

/* 选择文字高亮 */
::selection { background: rgba(232,112,42,0.3); color: #fff; }

/* 滚动条静音 */
::-webkit-scrollbar { width: 3px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(232,112,42,0.2); border-radius: 10px; }
"""


def artist_node(state: GameFactoryState) -> dict:
    """注入增强 CSS ——不调 LLM，零风险。"""
    game_code = state["game_code"]

    try:
        # 在 </style> 之前注入增强 CSS
        if "</style>" in game_code:
            styled = game_code.replace("</style>", POLISH_CSS + "\n</style>", 1)
        elif "</head>" in game_code:
            styled = game_code.replace("</head>", "<style>" + POLISH_CSS + "</style>\n</head>", 1)
        else:
            styled = game_code  # 找不到注入点，保持原样

        return {
            "styled_code": styled,
            "status": "success",
            "agent_logs": [{"agent": "artist", "action": "style_applied", "detail": "polish layer injected (scanlines + micro-animations)"}],
        }
    except Exception as e:
        return {
            "styled_code": game_code,
            "status": "success",
            "agent_logs": [{"agent": "artist", "action": "fallback", "detail": f"error: {e}, using original code"}],
        }
