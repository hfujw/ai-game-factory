"""策划 Agent — CoT 推理选择谜题类型与设计机制（AI 原生版）"""

import json
from app.graph.state import GameFactoryState
from app.llm_client import chat_json, _strip_markdown_fence, agent_log

SYSTEM_PROMPT = """你是一个游戏策划师，专门把主题素材改编成解谜小游戏。

【类型选择】
根据素材特征，选择最适合的谜题类型：
- cipher：素材涉及密码、加密、隐藏信息、秘密通信、符号破译
- sequence：素材涉及时间线、步骤顺序、因果关系链、组装过程
- logic：素材涉及逻辑推理、矛盾排除、真相还原、条件判断

分析步骤（必须全部完成）：
1. 特征提取：阅读素材，提取 3-5 个关键特征（引用原文）
2. 类型匹配：逐一评估 cipher/sequence/logic 的匹配度（0-10分，说明理由）
3. 排除论证：明确说明为什么其他类型不合适
4. 机制设计：基于素材具体内容设计 mechanic/rules/win_condition
5. 沉浸感检验：玩家解这个谜题 = 亲身体验主题的关键时刻？为什么？
6. 自检：回顾以上步骤，确认没有遗漏关键约束

【输出格式】
{
  "puzzle_type": "cipher",
  "material_sufficient": true,
  "puzzle_design": {
    "mechanic": "一句话玩法",
    "rules": "3-5条具体规则",
    "win_condition": "通关条件"
  },
  "reasoning_chain": ["步骤1...", "步骤2...", ...],
  "reasoning": "为什么选这个类型（一句话总结）"
}"""


def planner_node(state: GameFactoryState) -> dict:
    user_input = state["user_input"]
    search_results = state.get("search_results", [])
    suggested_type = state.get("suggested_type", "")

    sources_text = "\n\n".join(
        f"[来源{i+1}] {r.get('title','')}\n{r.get('content','')[:600]}"
        for i, r in enumerate(search_results)
    )

    crawler_hint = ""
    if suggested_type and suggested_type != "unknown":
        crawler_hint = f"\n【素材评估员建议】建议优先考虑「{suggested_type}」类型，但请你独立判断。\n"

    prompt = f"""用户想了解的主题：{user_input}{crawler_hint}

以下是搜集到的素材：
{sources_text if sources_text else '（使用你的知识）'}

请逐步分析并决定谜题类型和机制。如果素材太单薄，返回 material_sufficient=false。"""

    try:
        response = chat_json(prompt, system=SYSTEM_PROMPT)
        response = _strip_markdown_fence(response)
        result = json.loads(response)

        if not result.get("material_sufficient", False):
            return {
                "puzzle_type": "unknown", "puzzle_design": {}, "material_sufficient": False,
                "error_message": f"关于「{user_input}」的素材不足以支撑一个有趣的谜题。",
                "suggestions": ["1940年 Turing 破译德军 Enigma 密码", "1989年圣诞节 Guido 发明了 Python"],
                "status": "failed", "reasoning_chain": result.get("reasoning_chain", []),
                "agent_logs": [agent_log("planner", "insufficient", result.get("reasoning", ""))],
            }

        reasoning_chain = result.get("reasoning_chain", [])
        logs = []
        for i, step in enumerate(reasoning_chain):
            logs.append(agent_log("planner", f"step_{i+1}", step))

        logs.append(agent_log("planner", "designed",
            f"type={result['puzzle_type']}, {result.get('reasoning','')[:80]}"))

        return {
            "puzzle_type": result["puzzle_type"],
            "puzzle_design": result.get("puzzle_design", {}),
            "material_sufficient": True,
            "reasoning_chain": reasoning_chain,
            "agent_logs": logs,
        }

    except Exception as e:
        return {
            "puzzle_type": "unknown", "puzzle_design": {}, "material_sufficient": False,
            "error_message": f"策划Agent调用LLM失败: {str(e)}", "status": "failed",
            "reasoning_chain": [f"错误: {str(e)}"],
            "agent_logs": [agent_log("planner", "error", str(e))],
        }
