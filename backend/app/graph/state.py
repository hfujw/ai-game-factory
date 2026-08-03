"""LangGraph State — 6 个 Agent 共享的全局状态。

关键修复：agent_logs 使用 Annotated + operator.add，
确保每个 Agent 的日志**追加**而不是互相覆盖。
"""

from typing import TypedDict, List, Optional, Annotated
import operator
from pydantic import BaseModel, Field


class PuzzleSpec(BaseModel):
    """谜题规格——Pydantic 强校验"""
    type: str = ""
    answer: str = ""
    hints: list[dict] = Field(default_factory=list)
    max_attempts: int = 3
    items_count: int = 0
    items_labels: list[str] = Field(default_factory=list)


class GameDesignDoc(BaseModel):
    """游戏设计文档——writer→coder 的结构化中间层"""
    puzzle_spec: PuzzleSpec = Field(default_factory=PuzzleSpec)
    screens: list[dict] = Field(default_factory=list)
    content_map: dict = Field(default_factory=dict)
    visual_spec: dict = Field(default_factory=dict)


class GameFactoryState(TypedDict):
    # === 用户输入 ===
    user_input: str

    # === 爬虫 Agent 产出 ===
    search_results: List[dict]
    material_score: float
    material_sufficient: bool
    suggested_type: str
    reasoning_chain: List[str]

    # === 策划 Agent 产出 ===
    puzzle_type: str
    puzzle_design: dict

    # === 文案 Agent 产出 ===
    game_script: str
    script_data: dict              # writer 产出的结构化剧本，artist_pre/coder 消费
    game_design_doc: Optional[dict] # designer 产出的 GDD（中期扩展用，当前 writer 填充）
    script_keywords: List[str]

    # === 程序 Agent 产出 ===
    game_code: str

    # === 审查 Agent 产出 ===
    review_passed: bool
    review_feedback: str
    review_details: dict
    retry_count: int
    review_history: Annotated[List[dict], operator.add]

    # === 美术 Agent 产出 ===
    directions: list           # artist_pre 产出的 2 个视觉方向
    selected_direction: dict   # 关键词匹配选定的方向
    styled_code: str           # artist_post 产出的最终 HTML
    orchestrator_notes: str    # 协调 Agent 给下游的备注

    # === 元数据 ===
    status: str
    error_message: str
    suggestions: List[str]
    # 使用 Annotated + operator.add：每个 Agent 的日志追加到列表末尾
    agent_logs: Annotated[List[dict], operator.add]


def initial_state(user_input: str) -> GameFactoryState:
    """创建初始状态。"""
    return GameFactoryState(
        user_input=user_input,
        puzzle_type="",
        puzzle_design={},
        search_results=[],
        material_score=0.0,
        material_sufficient=False,
        suggested_type="",
        reasoning_chain=[],
        game_script="",
        script_data={},
        game_design_doc=None,
        script_keywords=[],
        game_code="",
        review_passed=False,
        review_feedback="",
        review_details={},
        retry_count=0,
        review_history=[],
        directions=[],
        selected_direction={},
        styled_code="",
        orchestrator_notes="",
        status="running",
        error_message="",
        suggestions=[],
        agent_logs=[],
    )
