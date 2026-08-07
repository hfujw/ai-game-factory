"""5 个工具 — 编排 LLM 按需调用。每个工具独立、可单独测试。"""

from app.tools.search import tool_search, _filter_noise
from app.tools.design import tool_design
from app.tools.compose import tool_compose
from app.tools.render import tool_render, tool_render_stream
from app.tools.verify import tool_verify

# ── 预算（估算）──
TOOL_COST = {"search": 0.03, "design": 0.05, "compose": 0.08, "render": 0.15, "verify": 0.05}

# ── 工具注册表：tool_name → 函数 ──
TOOL_MAP = {
    "search": tool_search,
    "design": tool_design,
    "compose": tool_compose,
    "render": tool_render,
    "verify": tool_verify,
}

__all__ = [
    "tool_search", "tool_design", "tool_compose", "tool_render",
    "tool_render_stream", "tool_verify", "_filter_noise",
    "TOOL_COST", "TOOL_MAP",
]
