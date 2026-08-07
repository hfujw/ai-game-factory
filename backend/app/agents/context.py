"""AgentState — orchestrator 上下文的数据结构定义。

当前 orchestrator 用 dict（ctx）传递状态，所有 key 在此声明。
未来切 LangGraph 时，这个 TypedDict 直接映射到 StateGraph 的 State。
"""

from typing import TypedDict, NotRequired


class AgentState(TypedDict, total=False):
    """编排 Agent 的完整上下文。total=False 表示所有字段可选。"""

    # ── 输入 ──
    user_input: str                      # 用户输入的主题

    # ── 素材与知识库 ──
    material: list[dict]                 # 搜索结果 + KB 匹配
    material_level: NotRequired[dict]    # evaluate_material 的评估结果
    honest_mode: NotRequired[bool]       # 是否已进入诚实模式

    # ── 生成中间产物 ──
    design: NotRequired[dict | None]     # tool_design 输出
    content: NotRequired[dict | None]    # tool_compose 输出
    html: NotRequired[str]               # tool_render 输出
    visual: NotRequired[dict | None]     # 视觉参考（未使用，预留）

    # ── 审查与回退 ──
    passed: NotRequired[bool]            # 上次 verify 是否通过
    issues: NotRequired[list[dict]]      # verify 发现的问题列表
    render_fail_count: NotRequired[int]  # 连续 render/verify 失败计数
    force_verify: NotRequired[bool]      # 诚实模式 render 后强制 verify
    force_next_tool: NotRequired[str]    # verify 失败后强制回退的目标工具
    force_strategy_change: NotRequired[bool]  # 连续失败后强制换策略

    # ── 步数与预算 ──
    steps: NotRequired[int]              # 当前步数
    max_steps: NotRequired[int]          # 最大步数（默认 20）
    budget_spent: NotRequired[float]     # 已花费预算
    budget_total: NotRequired[float]     # 总预算（默认 ¥1）

    # ── 跟踪 ──
    tool_history: NotRequired[list[dict]]       # 每步的工具调用记录
    cost_records: NotRequired[list[dict]]       # LLM 调用记账（session 级别）
    _decide_fail_count: NotRequired[int]        # _decide 连续失败计数
