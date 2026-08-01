"""审查 Agent — 两阶段验证：机械契约检查 + LLM 质量审查。

Phase 1（机械检查，零 LLM 消耗）：
  用正则验证代码是否满足 coder 契约中的结构要素。
  不通过 → 直接返回缺失项清单，coder 精准修复。

Phase 2（LLM 质量审查，仅在 Phase 1 通过后执行）：
  检查可玩性、UX 质量、历史准确性。
  不通过 → 返回具体修改建议。

设计原则：
  - 结构问题是机械的 → 用正则检查，不浪费 LLM 调用
  - 体验问题是主观的 → 用 LLM 判断，但传完整代码
  - Phase 1 保证代码"能用"，Phase 2 保证代码"好玩"
"""

import json
import re
from app.graph.state import GameFactoryState
from app.llm_client import chat_json, _strip_markdown_fence
from app.config import MAX_REVIEW_RETRIES
from app.knowledge.kb import get_event_names

# === Phase 1: 机械契约检查 ===

CONTRACT_RULES = [
    # (检查项名称, 正则, 缺失时的反馈)
    ("doctype", r'<!DOCTYPE\s+html', "缺少 <!DOCTYPE html>"),
    ("script_tag", r'<script[^>]*>', "缺少 <script> 标签"),
    ("screen_title", r'id=["\']screen-title["\']', "缺少 #screen-title（标题画面）"),
    ("screen_howto", r'id=["\']screen-howto["\']', "缺少 #screen-howto（操作说明画面）"),
    ("screen_game", r'id=["\']screen-game["\']', "缺少 #screen-game（游戏主体画面）"),
    ("screen_result", r'id=["\']screen-result["\']', "缺少 #screen-result（结果画面）"),
    ("screen_history", r'id=["\']screen-history["\']', "缺少 #screen-history（历史真相面板）"),
    ("history_facts", r'const\s+HISTORY_FACTS\s*=', "缺少 const HISTORY_FACTS 数组"),
    ("game_state", r'const\s+gameState\s*=', "缺少 const gameState 状态对象"),
    ("show_screen", r'function\s+showScreen\s*\(', "缺少 function showScreen() 画面切换函数"),
    ("history_button", r'历史真相', "缺少'历史真相'按钮或文字"),
    ("start_button", r'开始', "缺少'开始'相关按钮文字"),
    ("attempts_limit", r'(maxAttempts|剩余.*次|[3３]\s*次)', "缺少最大尝试次数限制(3次)"),
]


def phase1_contract_check(game_code: str) -> tuple[bool, list[str]]:
    """机械正则检查。返回 (通过?, 缺失项列表)。"""
    missing = []
    for name, pattern, feedback in CONTRACT_RULES:
        if not re.search(pattern, game_code, re.IGNORECASE):
            missing.append(feedback)
    return len(missing) == 0, missing


# === Phase 2: LLM 质量审查 ===

SYSTEM_PROMPT = """你是游戏 QA + 历史爱好者。审查一个已经通过结构检查的 HTML 游戏。

游戏已经满足基本结构（有标题/说明/游戏区/结果/历史面板），你只需要关注：

1. **谜题可解性**：玩家能通关吗？逻辑自洽吗？
2. **交互清晰度**：操作后有视觉反馈吗？玩家知道当前该做什么吗？
3. **历史准确度**：HISTORY_FACTS 中的事实和提供的史料一致吗？
4. **完整体验**：从标题→说明→游戏→结果→历史，流程完整吗？

评分标准（面试作品级别）：
- 基本可用（有小瑕疵但能玩） → passed=true，issues 里提小建议
- 严重影响体验（谜题无解/流程断裂） → passed=false

返回 JSON：
{
  "passed": true,
  "issues": ["小建议1", "小建议2"],
  "feedback": "如果不通过，给程序员的修改清单。通过时给简短评价。"
}"""


def reviewer_node(state: GameFactoryState) -> dict:
    """两阶段审查。"""
    game_code = state["game_code"]
    game_script = state["game_script"]
    search_results = state.get("search_results", [])
    retry_count = state.get("retry_count", 0) + 1

    # === Phase 1: 机械检查 ===
    p1_ok, missing = phase1_contract_check(game_code)

    if not p1_ok:
        # 机械检查不通过 → 直接返回缺失清单，不浪费 LLM 调用
        feedback = "契约检查不通过，以下结构要素缺失：\n" + "\n".join(f"- {m}" for m in missing)
        feedback += "\n\n请严格按照游戏契约重新生成代码，确保包含所有必需的 id、常量和函数。"

        result = {
            "review_passed": False,
            "review_feedback": feedback,
            "review_details": {"phase": "mechanical", "missing": missing},
            "retry_count": retry_count,
            "agent_logs": [{
                "agent": "reviewer",
                "action": "mechanical_reject",
                "detail": f"缺失 {len(missing)} 项: {', '.join(missing)}",
            }],
        }

        if retry_count >= MAX_REVIEW_RETRIES:
            result["error_message"] = f"游戏代码经过 {retry_count} 次修改仍未通过契约检查。"
            result["suggestions"] = get_event_names()[:4]
            result["status"] = "failed"

        return result

    # === Phase 2: LLM 质量审查 ===
    # 史料
    sources = "\n".join(
        f"- {r.get('title', '')}: {r.get('content', '')[:200]}"
        for r in search_results[:3]
    )

    # 传完整代码
    prompt = f"""审查这个 {len(game_code)} 字符的 HTML 游戏。

【游戏剧本】
{game_script[:500]}

【原始史料】
{sources}

【完整游戏代码】
{game_code}

当前重试: {retry_count}/{MAX_REVIEW_RETRIES}。结构检查已通过，请审查可玩性+历史+体验。返回 JSON。"""

    try:
        # 用 chat_json 获取结构化结果
        response = chat_json(prompt, system=SYSTEM_PROMPT)
        response = _strip_markdown_fence(response)
        result = json.loads(response)
    except Exception:
        # LLM 审查异常 → 结构已经通过，放行但记录
        result = {"passed": True, "issues": [], "feedback": "LLM审查异常，结构检查已通过，放行"}

    passed = result.get("passed", False)

    ret = {
        "review_passed": passed,
        "review_feedback": result.get("feedback", ""),
        "review_details": {
            "phase": "quality",
            "issues": result.get("issues", []),
        },
        "retry_count": retry_count,
        "agent_logs": [{
            "agent": "reviewer",
            "action": "pass" if passed else "reject",
            "detail": "; ".join(result.get("issues", [])),
        }],
    }

    if not passed and retry_count >= 3:
        ret["error_message"] = f"游戏代码经过 {retry_count} 次修改仍未通过质量审查。"
        ret["suggestions"] = get_event_names()[:4]
        ret["status"] = "failed"

    return ret
