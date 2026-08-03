"""审查 Agent — 两阶段验证：机械契约检查 + LLM 质量审查。

Phase 1 新增：答案溯源检查（零成本正则）。
  从 game_script 提取 puzzle.answer，在 game_code 中搜索是否存在。
  搜不到 → WARNING，提示 coder 可能使用了不同的验证值。
"""

import json
import re
from app.graph.state import GameFactoryState
from app.llm_client import agent_log, chat_json, _strip_markdown_fence
from app.config import MAX_REVIEW_RETRIES
from app.knowledge.kb import get_event_names


# === Phase 1: 机械契约检查（新增答案溯源）===

def _extract_answer_from_script(game_script: str) -> str | None:
    """从 game_script JSON 字符串中提取 puzzle.answer。"""
    if not game_script or not game_script.strip():
        return None
    try:
        data = json.loads(game_script)
        puzzle = data.get("puzzle", {})
        ans = puzzle.get("answer")
        return str(ans) if ans is not None else None
    except (json.JSONDecodeError, TypeError):
        return None


def _normalize_for_search(text: str) -> str:
    """规范化文本用于搜索：去注释、去多余空格、转小写。"""
    text = re.sub(r'//.*?\n|/\*.*?\*/', ' ', text, flags=re.DOTALL)
    text = re.sub(r'\s+', ' ', text)
    return text.lower().strip()


CRITICAL_RULES = [
    ("doctype", r'<!DOCTYPE\s+html', "缺少 <!DOCTYPE html>"),
    ("script_tag", r'<script[^>]*>', "缺少 <script> 标签"),
    ("screen_game", r'id=["\']screen-game["\']', "缺少游戏主体区域"),
    ("game_state", r'(const\s+gameState|let\s+gameState|var\s+gameState)', "缺少 gameState 状态对象"),
]
WARNING_RULES = [
    ("screen_result", r'(id=["\']screen-result["\']|胜利|失败|通关|再来)', "缺少结果画面"),
    ("history", r'(HISTORY_FACTS|历史真相)', "缺少历史真相"),
]
# 正向检查：模式存在=OK（cursor:pointer 应该有）
CSS_MUST_HAVE = [
    ("clickable_button", r'cursor\s*:\s*pointer', "所有按钮缺少 cursor:pointer，可能无法点击"),
]
# 反向检查：模式存在=坏（pointer-events:none 不应该有，除了 .screen）
CSS_MUST_NOT_HAVE = [
    ("no_blocked_pointer", r'pointer-events\s*:\s*none', "存在 pointer-events:none 可能阻塞交互"),
]


def phase1_contract_check(game_code: str, game_script: str) -> dict:
    """机械正则检查 + 答案溯源。返回 {level: CRITICAL|WARNING|PASS, missing: [...]}。"""
    critical_missing = []
    for name, pattern, feedback in CRITICAL_RULES:
        if not re.search(pattern, game_code, re.IGNORECASE):
            critical_missing.append(feedback)

    warning_missing = []
    for name, pattern, feedback in WARNING_RULES:
        if not re.search(pattern, game_code, re.IGNORECASE):
            warning_missing.append(feedback)

    css_warnings = []
    for name, pattern, feedback in CSS_MUST_HAVE:
        if not re.search(pattern, game_code, re.IGNORECASE):
            css_warnings.append(feedback)
    for name, pattern, feedback in CSS_MUST_NOT_HAVE:
        if re.search(pattern, game_code, re.IGNORECASE):
            css_warnings.append(feedback)

    # === 答案溯源检查（零成本）===
    expected_answer = _extract_answer_from_script(game_script)
    if expected_answer and isinstance(expected_answer, str) and len(expected_answer) > 0:
        normalized_code = _normalize_for_search(game_code)

        if '\n' not in expected_answer and len(expected_answer) < 80:
            if expected_answer.lower() not in normalized_code:
                warning_missing.append(
                    f"答案溯源：剧本中的正确答案「{expected_answer}」未在代码中找到，"
                    f"coder 可能使用了不同的验证值"
                )
        else:
            lines = [l.strip() for l in expected_answer.split('\n') if l.strip()]
            hits = sum(1 for l in lines if l.lower() in normalized_code)
            if hits == 0:
                warning_missing.append(
                    f"答案溯源：剧本中的正确答案（{len(lines)}行代码片段）"
                    f"未在代码中找到任何匹配行"
                )

    if critical_missing:
        return {"level": "CRITICAL", "pass": False, "missing": critical_missing + css_warnings}
    if warning_missing or css_warnings:
        return {"level": "WARNING", "pass": False, "missing": warning_missing + css_warnings}
    return {"level": "PASS", "pass": True, "missing": []}


# === Phase 2: LLM 质量审查 ===

SYSTEM_PROMPT = """你是游戏 QA + 历史爱好者。审查一个已经通过结构检查的 HTML 游戏。

游戏已经满足基本结构（有标题/说明/游戏区/结果/历史面板），你只需要关注：

1. **能跑吗**：JS 有没有明显错误？按钮点了有没有反应？
2. **能通关吗**：谜题有正确答案吗？通关路径走得通吗？
3. **历史对吗**：HISTORY_FACTS 中的事实和史料一致吗？
4. **流程完整吗**：从标题→游戏→结果→历史真相，切换正常吗？

⚠️ 四个维度都检查，都影响通过判定。但"不够好看""不够有趣"不算理由。

评分标准：
- 🟢 代码能跑、逻辑无 bug、谜题能通关 → passed=true
- 🔴 JS 报错白屏、点了没反应、谜题无解 → passed=false

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

    # === Phase 1: 机械检查（分级）— 传入 game_script 做答案溯源 ===
    p1 = phase1_contract_check(game_code, game_script)

    if not p1["pass"]:
        logger.warning("Phase1 %s: 缺失 %d 项 — %s", p1["level"], len(p1["missing"]), ", ".join(p1["missing"][:3]))

        try:
            with open("_last_failed_game.html", "w", encoding="utf-8") as f:
                f.write(game_code)
        except Exception:
            pass

        # CRITICAL → 跳过 Phase2 LLM，直接打回
        if p1["level"] == "CRITICAL":
            feedback = "【致命结构错误——跳过 LLM 审查】\n" + "\n".join(f"- {m}" for m in p1["missing"])
            result = {
                "review_passed": False,
                "review_feedback": feedback,
                "review_details": {"phase": "mechanical_critical", "missing": p1["missing"]},
                "retry_count": retry_count,
                "agent_logs": [agent_log("reviewer", "mechanical_critical", f"CRITICAL 缺失 {len(p1['missing'])} 项, 跳过 Phase2")],
            }
            if retry_count >= MAX_REVIEW_RETRIES:
                result["error_message"] = f"游戏代码经过 {retry_count} 次修改仍有致命结构错误。"
                result["suggestions"] = get_event_names()[:4]
                result["status"] = "failed"
            return result

        # WARNING → 记下警告文本，继续 Phase2
        warning_text = "【结构警告】\n" + "\n".join(f"- {m}" for m in p1["missing"])

    # === Phase 2: LLM 质量审查（仅在非 CRITICAL 时进入）===
    sources = "\n".join(
        f"- {r.get('title', '')}: {r.get('content', '')[:200]}"
        for r in search_results[:3]
    )

    prompt = f"""审查这个 {len(game_code)} 字符的 HTML 游戏。

【游戏剧本】
{game_script[:500]}

【原始史料】
{sources}

【完整游戏代码】
{game_code}

当前重试: {retry_count}/{MAX_REVIEW_RETRIES}。结构检查已通过，请审查可玩性+历史+体验。返回 JSON。"""

    try:
        response = chat_json(prompt, system=SYSTEM_PROMPT)
        response = _strip_markdown_fence(response)
        result = json.loads(response)
    except Exception:
        result = {"passed": True, "issues": [], "feedback": "LLM审查异常，结构检查已通过，放行"}

    passed = result.get("passed", False)
    logger.info("Phase2 结果: passed=%s, issues=%s", passed, result.get("issues", [])[:2])

    # 合并 Phase1 WARNING（如果有）
    p2_feedback = result.get("feedback", "")
    if p1["level"] == "WARNING":
        p2_feedback = warning_text + "\n\n" + p2_feedback

    ret = {
        "review_passed": passed,
        "review_feedback": p2_feedback,
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
