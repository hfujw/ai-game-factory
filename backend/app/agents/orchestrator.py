"""Orchestrator Agent — 施工前的跨 Agent 一致性检查。

规则预检（零 LLM）：type_mismatch / feasibility
LLM 深度协调（可选）：基调/审美一致性评估
失败不阻塞——所有异常都优雅降级，直接放行。
"""

import json
from app.graph.state import GameFactoryState
from app.llm_client import agent_log, chat_json, _strip_markdown_fence

VALID_TYPES = {"cipher", "sequence", "logic"}
HISTORY_TYPES = {"cipher", "sequence", "logic"}

ORCHESTRATOR_SYSTEM_PROMPT = """你是一个多 Agent 协作的导演，检查上游产出的一致性。

【检查任务】
1. 类型/机制一致性：planner 选的谜题类型与 writer 的 puzzle.type 是否一致？与 crawler 的建议是否呼应？
2. 基调/审美一致性：writer 的剧本 atmosphere 与 artist_pre 的视觉方向 mood_tags/name/ui 是否契合？
   - 注意：中文情绪词高度依赖上下文（"紧张"在战争惊悚中是暗调，在喜剧中是明调），请基于剧本整体氛围判断，不要做机械关键词匹配
3. 施工优先级：基于以上检查，给 coder 提供 1-3 条"施工注意事项"

【输出格式】
{
  "conflicts": [
    {
      "type": "type_mismatch|tone_mismatch|feasibility",
      "severity": "warning|info",
      "description": "...",
      "resolution": "..."
    }
  ],
  "tone_assessment": "一句话评价剧本氛围与视觉方向的契合度",
  "coordinator_notes": "给 coder 的施工注意事项（1-3 条）"
}"""


def _quick_precheck(state: dict) -> tuple[list[dict], bool]:
    """纯规则预检（零 LLM）。只检 type_mismatch 和 feasibility。"""
    issues = []

    puzzle_type = state.get("puzzle_type", "")
    suggested_type = state.get("suggested_type", "")
    material_sufficient = state.get("material_sufficient", False)
    search_results = state.get("search_results", [])
    puzzle_design = state.get("puzzle_design", {})

    # type 有效性
    if not puzzle_type or puzzle_type not in VALID_TYPES:
        issues.append({
            "type": "type_mismatch",
            "severity": "warning",
            "description": f"puzzle_type 为 '{puzzle_type or '(空)'}'，不在有效类型列表中",
            "resolution": "planner 应输出 cipher/sequence/logic",
        })
    elif (puzzle_type not in HISTORY_TYPES and suggested_type
          and suggested_type in HISTORY_TYPES):
        issues.append({
            "type": "type_mismatch",
            "severity": "info",
            "description": f"crawler 建议 '{suggested_type}'，planner 选择 '{puzzle_type}'，类型不一致",
            "resolution": "以 planner 为准",
        })

    # feasibility
    if not material_sufficient:
        issues.append({
            "type": "feasibility",
            "severity": "warning",
            "description": "material_sufficient=False，素材不足",
            "resolution": "建议 coder 严格控制输出长度，确保代码完整",
        })
    if not search_results:
        issues.append({
            "type": "feasibility",
            "severity": "warning",
            "description": "search_results 为空",
            "resolution": "coder 使用默认视觉参数",
        })
    if not puzzle_design or not puzzle_design.get("mechanic"):
        issues.append({
            "type": "feasibility",
            "severity": "warning",
            "description": "puzzle_design 不完整，缺少 mechanic",
            "resolution": "coder 自行设计游戏机制",
        })

    needs_llm = len(issues) > 0
    return issues, needs_llm


def _llm_coordination(state: dict, issues: list[dict]) -> dict:
    """可选 LLM 深度协调——基调/审美一致性评估。"""
    script = state.get("script_data", {})
    direction = state.get("selected_direction", {})
    chain = state.get("reasoning_chain", [])

    prompt = f"""【Planner 决策】
谜题类型: {state.get('puzzle_type', '')}
crawler 建议: {state.get('suggested_type', '')}
推理链: {' | '.join(chain[-3:]) if chain else '(空)'}

【Writer 剧本】
事件: {script.get('event', '')}
氛围: {script.get('atmosphere', '')}
puzzle.type: {script.get('puzzle', {}).get('type', '')}
视觉情绪: {script.get('visual', {}).get('mood', '')}

【Artist_pre 视觉方向】
名称: {direction.get('name', '')}
mood_tags: {', '.join(direction.get('mood_tags', []))}
UI风格: {direction.get('ui', '')}
动画: {direction.get('animation', '')}
色板: {', '.join(direction.get('palette', []))}

【规则预检发现的问题】
{json.dumps(issues, ensure_ascii=False) if issues else '无'}

请按 system prompt 格式返回 JSON。"""

    try:
        response = chat_json(prompt, system=ORCHESTRATOR_SYSTEM_PROMPT)
        response = _strip_markdown_fence(response)
        return json.loads(response)
    except Exception as e:
        return {
            "conflicts": issues,
            "tone_assessment": "",
            "coordinator_notes": f"LLM 协调失败（{str(e)}），降级为规则预检结果",
        }


def orchestrator_node(state: GameFactoryState) -> dict:
    """协调检查：规则预检 → 有 issue 则 LLM 深度协调 → 输出备注给 coder。"""
    state_dict = dict(state)  # TypedDict → plain dict for uniform .get() access

    # 1. 规则预检
    issues, needs_llm = _quick_precheck(state_dict)

    # 2. LLM 深度协调（有 issue 时才调）
    if needs_llm:
        coord = _llm_coordination(state_dict, issues)
    else:
        coord = {
            "conflicts": [],
            "tone_assessment": "",
            "coordinator_notes": "规则预检全部通过，无需 LLM 协调",
        }

    # 3. 构建 orchestrator_notes
    notes_parts = []
    conflicts = coord.get("conflicts", [])
    if conflicts:
        notes_parts.append("【协调 Agent 备注】")
        for c in conflicts:
            tag = "⚠️" if c.get("severity") == "warning" else "ℹ️"
            notes_parts.append(
                f"{tag} [{c.get('type', '?')}] {c.get('description', '')[:100]}"
                f" → {c.get('resolution', '')[:100]}"
            )
    tone = coord.get("tone_assessment", "")
    if tone:
        notes_parts.append(f"【基调评估】{tone}")
    c_notes = coord.get("coordinator_notes", "")
    if c_notes and c_notes != "规则预检全部通过，无需 LLM 协调":
        notes_parts.append(f"【施工建议】{c_notes}")
    orchestrator_notes = "\n".join(notes_parts) if notes_parts else ""

    # 4. Agent 日志
    logs = []
    if needs_llm:
        issue_strs = [f"{i['type']}={i['severity']}" for i in issues]
        logs.append(agent_log("orchestrator", "quick_check",
            f"规则预检: {', '.join(issue_strs)}"))
        if conflicts:
            logs.append(agent_log("orchestrator", "coordination",
                coord.get("coordinator_notes", "已评估")[:80]))
    else:
        logs.append(agent_log("orchestrator", "harmony",
            "规则预检全部通过：类型有效+素材充足+设计完整"))

    return {
        "orchestrator_notes": orchestrator_notes,
        "agent_logs": logs,
    }
