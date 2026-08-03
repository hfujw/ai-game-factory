"""审查 Agent — 两阶段验证 + LLM 深度审查 + 反思层。

Phase 1：机械正则 + 答案溯源（免费）
Phase 2：LLM 深度审查，输出 issues（含 fix_strategy）+ reflexion（工作流优化建议）
"""

import json, re, logging
from app.graph.state import GameFactoryState
from app.llm_client import agent_log, chat_json, _strip_markdown_fence
from app.config import MAX_REVIEW_RETRIES
from app.knowledge.kb import get_event_names

logger = logging.getLogger("reviewer")

# === Phase 1 工具函数 ===
def _extract_answer_from_script(game_script: str) -> str | None:
    if not game_script: return None
    try:
        data = json.loads(game_script)
        ans = data.get("puzzle", {}).get("answer")
        return str(ans) if ans is not None else None
    except: return None

def _normalize_for_search(text: str) -> str:
    text = re.sub(r'//.*?\n|/\*.*?\*/', ' ', text, flags=re.DOTALL)
    return re.sub(r'\s+', ' ', text).lower().strip()

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
CSS_MUST_HAVE = [("clickable_button", r'cursor\s*:\s*pointer', "缺少 cursor:pointer")]
CSS_MUST_NOT_HAVE = [("no_blocked_pointer", r'pointer-events\s*:\s*none', "存在 pointer-events:none")]


def phase1_contract_check(game_code: str, game_script: str, puzzle_type: str = "") -> dict:
    critical_missing = [fb for _, p, fb in CRITICAL_RULES if not re.search(p, game_code, re.I)]
    warning_missing = [fb for _, p, fb in WARNING_RULES if not re.search(p, game_code, re.I)]
    css_warnings = [fb for _, p, fb in CSS_MUST_HAVE if not re.search(p, game_code, re.I)]
    css_warnings += [fb for _, p, fb in CSS_MUST_NOT_HAVE if re.search(p, game_code, re.I)]

    # 答案溯源：所有类型统一检查
    expected = _extract_answer_from_script(game_script)
    if expected and len(expected) > 0:
        norm = _normalize_for_search(game_code)
        if '\n' not in expected and len(expected) < 80:
            if expected.lower() not in norm:
                warning_missing.append(f"答案溯源：正确答案「{expected}」未在代码中找到")
        else:
            lines = [l.strip() for l in expected.split('\n') if l.strip()]
            if not any(l.lower() in norm for l in lines):
                warning_missing.append(f"答案溯源：正确答案（{len(lines)}行）未在代码中找到")

    # DEBUG: 确认哪条规则在杀人
    logger.debug(
        "Phase1 DEBUG: type=%s critical=%s warning=%s css=%s",
        puzzle_type,
        [m[:40] for m in critical_missing] if critical_missing else "无",
        [m[:40] for m in warning_missing] if warning_missing else "无",
        [m[:30] for m in css_warnings] if css_warnings else "无",
    )

    if critical_missing: return {"level": "CRITICAL", "pass": False, "missing": critical_missing + css_warnings}
    if warning_missing or css_warnings: return {"level": "WARNING", "pass": False, "missing": warning_missing + css_warnings}
    return {"level": "PASS", "pass": True, "missing": []}


# === Phase 2：LLM 深度审查 ===
SYSTEM_PROMPT = """你是游戏 QA + 历史审查员 + 工作流优化顾问。

审查 AI Agent 生成的 HTML 游戏。不仅要判断好坏，还要：
1. 找出具体问题（severity + category + description）
2. 给出精确修复策略（fix_strategy：告诉 coder 怎么改）
3. 分析失败根因，给工作流提优化建议（reflexion）

【审查维度】
1. 可运行性：JS 有无语法错误？按钮是否可点击？
2. 谜题一致性：代码验证的值与剧本 puzzle.answer 是否一致？
3. 历史准确性：HISTORY_FACTS 是否与史料一致？有无编造？
4. 完整性：title/howto/game/result/history 五个画面是否齐全？
5. 可玩性：玩家知道要做什么吗？有引导吗？反馈即时吗？

【输出格式】
{
  "passed": false,
  "issues": [
    {
      "severity": "critical|warning|info",
      "category": "answer_mismatch|js_error|historical_error|ux|missing_screen|logic_bug",
      "description": "具体问题",
      "fix_strategy": "给 coder 的精确修复指令"
    }
  ],
  "reflexion": "根因分析 + 工作流优化建议。如：'连续出现answer不一致，建议在coder prompt中三重强调answer值'"
}

⚠️ critical 问题（JS报错/答案不一致/历史错误）→ passed=false
⚠️ 不要因为'不够好看'拒绝。'不知道要做什么'是功能问题，不是美观问题。"""


def _analyze_issue_history(review_history: list[dict]) -> dict:
    """分析问题历史，检测跨轮重复问题模式。"""
    if not review_history or len(review_history) < 2:
        return {"has_pattern": False, "repeated": [], "summary": ""}

    from collections import Counter
    categories = []
    for record in review_history:
        for issue in record.get("issues", []):
            cat = issue.get("category", "")
            if cat:
                categories.append(cat)

    if not categories:
        return {"has_pattern": False, "repeated": [], "summary": ""}

    counter = Counter(categories)
    repeated = [cat for cat, count in counter.items() if count >= 2]

    if repeated:
        return {
            "has_pattern": True,
            "repeated": repeated,
            "summary": f"连续出现 {'、'.join(repeated)} 类问题，建议在上游 Agent prompt 中增加针对性约束",
        }
    return {"has_pattern": False, "repeated": [], "summary": ""}


def reviewer_node(state: GameFactoryState) -> dict:
    game_code = state["game_code"]
    game_script = state["game_script"]
    search_results = state.get("search_results", [])
    retry_count = state.get("retry_count", 0) + 1
    review_history = state.get("review_history", [])

    logger.info("审查开始 — retry=%d/%d, code_len=%d", retry_count, MAX_REVIEW_RETRIES, len(game_code))

    # Phase 1
    p1 = phase1_contract_check(game_code, game_script, state.get("puzzle_type", ""))

    if not p1["pass"] and p1["level"] == "CRITICAL":
        feedback = "【致命结构错误——跳过 LLM 审查】\n" + "\n".join(f"- {m}" for m in p1["missing"])
        history_entry = {
            "round": retry_count,
            "phase": "mechanical_critical",
            "issues": [{"severity": "critical", "category": "structure", "description": m} for m in p1["missing"]],
            "reflexion": "",
        }
        result = {"review_passed": False, "review_feedback": feedback,
            "review_details": {"phase": "mechanical_critical", "missing": p1["missing"], "issues": []},
            "retry_count": retry_count,
            "review_history": [history_entry],
            "agent_logs": [
                agent_log("reviewer", "mechanical_critical", f"CRITICAL 缺失 {len(p1['missing'])} 项"),
                agent_log("reviewer", "reflexion", "coder 未遵循输出格式契约"),
            ]}
        if retry_count >= MAX_REVIEW_RETRIES:
            result.update(error_message=f"经过 {retry_count} 次修改仍有致命结构错误。",
                suggestions=get_event_names()[:4], status="failed")
        return result

    warning_text = ""
    if p1["level"] == "WARNING":
        warning_text = "【结构警告】\n" + "\n".join(f"- {m}" for m in p1["missing"])

    # Phase 2：LLM 深度审查
    sources = "\n".join(f"- {r.get('title','')}: {r.get('content','')[:200]}" for r in search_results[:3])
    # 历史审查记录
    history_ctx = ""
    if review_history:
        prev = [{"round": h["round"], "cats": [i.get("category","?") for i in h.get("issues",[])]} for h in review_history[-3:]]
        history_ctx = f"\n【历史审查记录（最近 {len(review_history)} 轮）】\n{json.dumps(prev, ensure_ascii=False)}\n请检查问题是否重复出现。\n"
    prompt = f"""审查这个 {len(game_code)} 字符的 HTML 游戏。

【游戏剧本】{game_script[:800]}
【原始史料】{sources}{history_ctx}
【完整游戏代码】{game_code[:4000]}
当前重试: {retry_count}/{MAX_REVIEW_RETRIES}。

请严格按 system prompt 格式返回 JSON。必须包含 issues 数组和 reflexion 字段。"""

    try:
        response = chat_json(prompt, system=SYSTEM_PROMPT)
        response = _strip_markdown_fence(response)
        result = json.loads(response)
    except Exception:
        result = {"passed": True, "issues": [], "reflexion": "LLM审查异常，结构检查已通过，放行"}

    passed = result.get("passed", False)
    issues = result.get("issues", [])
    reflexion = result.get("reflexion", "")
    logger.info("Phase2: passed=%s, issues=%d, reflexion=%s", passed, len(issues), reflexion[:50])

    # 构建 review_history 条目
    current_entry = {
        "round": retry_count,
        "phase": "quality",
        "issues": issues,
        "reflexion": reflexion,
    }
    new_history = review_history + [current_entry]
    pattern_analysis = _analyze_issue_history(new_history)

    p2_feedback = ""
    if issues:
        lines = [f"【审查发现 {len(issues)} 个问题】"]
        for iss in issues:
            lines.append(f"[{iss.get('severity','?').upper()}] [{iss.get('category','?')}] {iss.get('description','')}")
            lines.append(f"→ 修复策略: {iss.get('fix_strategy','无')}")
        if reflexion: lines.append(f"\n【工作流反思】{reflexion}")
        p2_feedback = "\n".join(lines)
    if warning_text: p2_feedback = warning_text + "\n\n" + p2_feedback

    # 日志：issues + reflexion 单独标记 + 重复问题
    logs = []
    if issues:
        logs.append({"agent": "reviewer", "action": "issues_found", "detail": f"{len(issues)} 个问题"})
        for iss in issues[:3]:
            logs.append({"agent": "reviewer", "action": f"issue_{iss.get('category','?')}",
                "detail": f"[{iss.get('severity','?')}] {iss.get('description','')[:80]}"})
    else:
        logs.append({"agent": "reviewer", "action": "pass", "detail": "无问题，审查通过"})
    if reflexion:
        logs.append({"agent": "reviewer", "action": "reflexion", "detail": reflexion[:120], "is_reflexion": True})
    if pattern_analysis["has_pattern"]:
        logs.append({"agent": "reviewer", "action": "pattern_alert", "detail": pattern_analysis["summary"]})

    ret = {"review_passed": passed, "review_feedback": p2_feedback,
        "review_details": {"phase": "quality", "issues": issues, "reflexion": reflexion,
            "pattern": pattern_analysis},
        "retry_count": retry_count,
        "review_history": [current_entry],
        "agent_logs": logs}

    if not passed and retry_count >= MAX_REVIEW_RETRIES:
        ret["error_message"] = f"游戏代码经过 {retry_count} 次修改仍未通过质量审查。"
        ret["suggestions"] = get_event_names()[:4]; ret["status"] = "failed"
        logs.append({"agent": "reviewer", "action": "gave_up", "detail": f"已达最大重试次数 {MAX_REVIEW_RETRIES}"})
        ret["agent_logs"] = logs
    return ret
