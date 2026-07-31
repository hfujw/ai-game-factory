"""LangGraph State — 6 个 Agent 共享的全局状态。

关键修复：agent_logs 使用 Annotated + operator.add，
确保每个 Agent 的日志**追加**而不是互相覆盖。
"""

from typing import TypedDict, List, Optional, Annotated
import operator


class GameFactoryState(TypedDict):
    # === 用户输入 ===
    user_input: str

    # === 爬虫 Agent 产出 ===
    search_results: List[dict]
    material_score: float
    material_sufficient: bool

    # === 策划 Agent 产出 ===
    puzzle_type: str
    puzzle_design: dict

    # === 文案 Agent 产出 ===
    game_script: str
    script_keywords: List[str]

    # === 程序 Agent 产出 ===
    game_code: str

    # === 审查 Agent 产出 ===
    review_passed: bool
    review_feedback: str
    review_details: dict
    retry_count: int

    # === 美术 Agent 产出 ===
    styled_code: str

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
        game_script="",
        script_keywords=[],
        game_code="",
        review_passed=False,
        review_feedback="",
        review_details={},
        retry_count=0,
        styled_code="",
        status="running",
        error_message="",
        suggestions=[],
        agent_logs=[],
    )
