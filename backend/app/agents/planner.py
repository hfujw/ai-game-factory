"""策划 Agent — 基于真实史料设计谜题机制。

输入：search_results（爬虫搜到的史料）+ user_input
输出：puzzle_type + puzzle_design

条件短路：KB 提供的 puzzle_guide 只有在 annotations >= 3 且 expected_output 存在时才直接
使用；否则把 KB 提示注入 LLM prompt，让 LLM 基于完整素材重新设计。
"""

import json
from app.graph.state import GameFactoryState
from app.llm_client import chat_json, _strip_markdown_fence, agent_log

SYSTEM_PROMPT = """你是一个游戏策划师，专门把计算机历史事件改编成解谜小游戏。

你会收到一段关于某个计算机历史事件的史料，你的任务是：

1. 判断这个事件适合哪种谜题类型：
   - "cipher"：事件涉及密码、破译、加密（如 Enigma、RSA）
   - "sequence"：事件有清晰的时间线或因果链（如语言的诞生过程）
   - "logic"：事件涉及冲突、博弈、选择（如浏览器大战、开源vs闭源）
   - "fill_blank"：Python 八股代码填空（如装饰器、上下文管理器）
   - "recite"：Python 八股代码默写（如生成器、描述符）
   - "match"：Python 八股概念配对（如深浅拷贝、GIL）
   - "debugger"：Python 八股 Bug 定位（如可变默认参数陷阱）

2. 基于史料内容设计谜题机制：
   - mechanic：谜题怎么玩（一句话描述玩法）
   - rules：具体规则（3-5条）
   - win_condition：怎么算通关

3. 如果史料内容太单薄，无法支撑一个有趣的谜题，直接返回 material_sufficient=false。

返回严格的 JSON 格式，不要加任何额外文字：
{
  "puzzle_type": "cipher",
  "material_sufficient": true,
  "puzzle_design": {
    "mechanic": "...",
    "rules": "...",
    "win_condition": "..."
  },
  "reasoning": "为什么选这个类型"
}"""


def planner_node(state: GameFactoryState) -> dict:
    """基于史料内容 → LLM 分析 → 选择谜题类型 + 设计机制。

    条件短路：只有 KB 数据完整（annotations >= 3 且 expected_output 存在）时才跳过 LLM。
    """
    user_input = state["user_input"]
    search_results = state.get("search_results", [])

    # === 步骤 1：查找 KB 是否提供了 puzzle_guide ===
    kb_guide = None
    for r in search_results:
        pg = r.get("puzzle_guide", {})
        if pg and pg.get("type"):
            kb_guide = pg
            break

    # === 步骤 2：条件短路判断 ===
    if kb_guide:
        annotations = kb_guide.get("annotations", [])
        has_expected_output = bool(kb_guide.get("expected_output"))

        if len(annotations) >= 3 and has_expected_output:
            # 数据完整，安全短路
            return {
                "puzzle_type": kb_guide["type"],
                "puzzle_design": {
                    "mechanic": f"Python 面试 - {kb_guide['type']}",
                    "rules": "；".join(annotations),
                    "win_condition": (
                        "所有空位填写正确" if kb_guide["type"] == "fill_blank"
                        else "代码通过校验" if kb_guide["type"] in ("recite", "debugger")
                        else "所有配对正确" if kb_guide["type"] == "match"
                        else "通关"
                    ),
                },
                "material_sufficient": True,
                "agent_logs": [agent_log("planner", "predefined",
                    f"type={kb_guide['type']} from KB, annotations={len(annotations)}, expected_output=ok")],
            }
        # 数据不完整：继续走 LLM，但把 KB 提示注入 prompt（见下方）

    # === 步骤 3：拼接史料文本 ===
    sources_text = "\n\n".join(
        f"[来源{i+1}] {r.get('title', '')}\n{r.get('content', '')[:500]}"
        for i, r in enumerate(search_results)
    )

    # 如果有不完整的 KB 提示，注入 prompt 帮助 LLM 决策
    kb_hint = ""
    if kb_guide:
        kb_hint = f"""
【知识库提示】该事件疑似八股题，知识库提供了初步信息：
- 建议类型：{kb_guide['type']}
- 现有 annotations：{json.dumps(kb_guide.get('annotations', []), ensure_ascii=False)}
- 但数据不够完整（annotations < 3 或缺少 expected_output），请基于以下完整史料重新设计谜题机制，类型优先选择「{kb_guide['type']}」。
"""

    prompt = f"""用户想了解的历史事件：{user_input}
{kb_hint}
以下是爬虫搜到的史料：
{sources_text if sources_text else '（使用你的知识）'}

请基于史料内容决定谜题类型和机制。如果史料太单薄，返回 material_sufficient=false。"""

    try:
        response = chat_json(prompt, system=SYSTEM_PROMPT)
        response = _strip_markdown_fence(response)
        result = json.loads(response)

        if not result.get("material_sufficient", False):
            return {
                "puzzle_type": "unknown",
                "puzzle_design": {},
                "material_sufficient": False,
                "error_message": f"关于「{user_input}」的史料不足以支撑一个有趣的谜题。",
                "suggestions": [
                    "1940年 Turing 破译德军 Enigma 密码",
                    "1989年圣诞节 Guido 发明了 Python",
                ],
                "status": "failed",
                "agent_logs": [agent_log("planner", "insufficient", result.get("reasoning", ""))],
            }

        return {
            "puzzle_type": result["puzzle_type"],
            "puzzle_design": result.get("puzzle_design", {}),
            "material_sufficient": True,
            "agent_logs": [agent_log("planner", "designed", result.get("reasoning", ""))],
        }

    except Exception as e:
        # LLM 调用失败 → 如果 KB 有数据（即使不完整），降级使用
        if kb_guide:
            return {
                "puzzle_type": kb_guide["type"],
                "puzzle_design": {
                    "mechanic": f"Python 面试 - {kb_guide['type']}",
                    "rules": "；".join(kb_guide.get("annotations", [])),
                    "win_condition": "通关",
                },
                "material_sufficient": True,
                "agent_logs": [agent_log("planner", "fallback_to_kb",
                    f"LLM failed, fallback to KB type={kb_guide['type']}, error={str(e)}")],
            }

        return {
            "puzzle_type": "unknown",
            "puzzle_design": {},
            "material_sufficient": False,
            "error_message": f"策划Agent调用LLM失败: {str(e)}",
            "status": "failed",
            "agent_logs": [agent_log("planner", "error", str(e))],
        }
