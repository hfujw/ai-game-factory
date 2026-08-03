"""LangGraph Workflow — 7 Agent 的编排逻辑。

流程：
  crawler → planner → writer → artist_pre → orchestrator → coder → reviewer
  reviewer → coder (审查不通过，回退重试，最多3次)
  reviewer → artist_post (审查通过)
  reviewer → END (超过重试上限，终止)
  artist_post → END

早停：
  - crawler 搜不到素材 → 直接返回失败
  - planner 基于史料判断做不了 → 返回失败
"""

from langgraph.graph import StateGraph, END
from app.graph.state import GameFactoryState
from app.agents.planner import planner_node
from app.agents.crawler import crawler_node
from app.agents.writer import writer_node
from app.agents.artist_pre import artist_pre_node
from app.agents.orchestrator import orchestrator_node
from app.agents.coder import coder_node
from app.agents.reviewer import reviewer_node
from app.agents.artist_post import artist_post_node
from app.config import MAX_REVIEW_RETRIES


def should_continue_after_crawler(state: GameFactoryState) -> str:
    """爬虫之后——搜到素材了吗？"""
    if state["material_sufficient"]:
        return "planner"
    return "end_failed"


def should_continue_after_planner(state: GameFactoryState) -> str:
    """策划之后——史料能支撑谜题设计吗？"""
    if state["material_sufficient"]:
        return "writer"
    return "end_failed"


def should_continue_after_reviewer(state: GameFactoryState) -> str:
    """审查之后——通过了吗？要重试吗？"""
    if state["review_passed"]:
        return "artist_post"
    if state["retry_count"] < MAX_REVIEW_RETRIES:
        return "coder"  # 回退重试
    return "end_failed"


def build_workflow() -> StateGraph:
    """构建并返回编译好的 LangGraph 工作流。"""
    workflow = StateGraph(GameFactoryState)

    # 添加节点
    workflow.add_node("crawler", crawler_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("writer", writer_node)
    workflow.add_node("artist_pre", artist_pre_node)
    workflow.add_node("orchestrator", orchestrator_node)
    workflow.add_node("coder", coder_node)
    workflow.add_node("reviewer", reviewer_node)
    workflow.add_node("artist_post", artist_post_node)

    # 设置入口——先搜史料，再策划
    workflow.set_entry_point("crawler")

    # 添加边
    workflow.add_conditional_edges(
        "crawler",
        should_continue_after_crawler,
        {"planner": "planner", "end_failed": END},
    )
    workflow.add_conditional_edges(
        "planner",
        should_continue_after_planner,
        {"writer": "writer", "end_failed": END},
    )
    workflow.add_edge("writer", "artist_pre")             # 剧本 → 视觉设计
    workflow.add_edge("artist_pre", "orchestrator")       # 视觉设计 → 协调检查
    workflow.add_edge("orchestrator", "coder")            # 协调 → 施工
    workflow.add_edge("coder", "reviewer")           # 施工 → 审查
    workflow.add_conditional_edges(
        "reviewer",
        should_continue_after_reviewer,
        {"artist_post": "artist_post", "coder": "coder", "end_failed": END},
    )
    workflow.add_edge("artist_post", END)

    return workflow.compile()
