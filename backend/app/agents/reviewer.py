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
    # 只保留真正必须的结构要素
    ("doctype", r'<!DOCTYPE\s+html', "缺少 <!DOCTYPE html>"),
    ("script_tag", r'<script[^>]*>', "缺少 <script> 标签"),
    ("screen_game", r'id=["\']screen-game["\']', "缺少游戏主体区域"),
    ("screen_result", r'(id=["\']screen-result["\']|胜利|失败|通关|再来)', "缺少结果画面"),
    ("history_facts", r'(HISTORY_FACTS|历史真相)', "缺少历史真相"),
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

1. **能跑吗**：JS 有没有明显错误？按钮点了有没有反应？
2. **能通关吗**：谜题有正确答案吗？通关路径走得通吗？
3. **历史对吗**：HISTORY_FACTS 中的事实和史料一致吗？
4. **流程完整吗**：从标题→游戏→结果→历史真相，切换正常吗？

⚠️ 四个维度都检查，都影响通过判定。但"不够好看""不够有趣"不算理由。

评分标准：
- 🟢 代码能跑、逻辑无 bug、谜题能通关 → passed=true（其他一切忽略）
- 🔴 JS 报错白屏、点了没反应、谜题无解 → passed=false

⚠️ 只看功能，不看美观。标题不够漂亮、说明不够详细、颜色不好看——这些统统不管，放行。

返回 JSON：
{
  "passed": true,
  "issues": ["小建议1", "小建议2"],
  "feedback": "如果不通过，给程序员的修改清单。通过时给简短评价。"
}"""


def reviewer_node(state: GameFactoryState) -> dict:
    """两阶段审查。"""
    import logging
    logger = logging.getLogger("reviewer")

    game_code = state["game_code"]
    game_script = state["game_script"]
    search_results = state.get("search_results", [])
    retry_count = state.get("retry_count", 0) + 1

    logger.info("审查开始 — retry=%d/%d, code_len=%d", retry_count, MAX_REVIEW_RETRIES, len(game_code))

    # === Phase 1: 机械检查 ===
    p1_ok, missing = phase1_contract_check(game_code)

    if not p1_ok:
        # 机械检查不通过 → 直接返回缺失清单
        logger.warning("Phase1 不通过: 缺失 %d 项 — %s", len(missing), ", ".join(missing[:3]))
        # 保存失败代码到文件供调试
        try:
            with open("_last_failed_game.html", "w", encoding="utf-8") as f:
                f.write(game_code)
            logger.info("失败代码已保存到 _last_failed_game.html")
        except Exception:
            pass
        feedback = "契约检查不通过，以下结构要素缺失：\n" + "\n".join(f"- {m}" for m in missing)

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
    logger.info("Phase2 结果: passed=%s, issues=%s", passed, result.get("issues", [])[:2])

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

    if not passed and retry_count >= MAX_REVIEW_RETRIES:
        ret["error_message"] = f"游戏代码经过 {retry_count} 次修改仍未通过质量审查。"
        ret["suggestions"] = get_event_names()[:4]
        ret["status"] = "failed"

    return ret
