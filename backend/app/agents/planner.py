"""策划 Agent — 基于真实史料设计谜题机制。

输入：search_results（爬虫搜到的史料）+ user_input
输出：puzzle_type + puzzle_design

使用 DeepSeek API 分析史料内容，不是关键词匹配。
"""

from app.graph.state import GameFactoryState
from app.llm_client import chat_json

SYSTEM_PROMPT = """你是一个游戏策划师，专门把计算机历史事件改编成解谜小游戏。

你会收到一段关于某个计算机历史事件的史料，你的任务是：

1. 判断这个事件适合哪种谜题类型：
   - "cipher"：事件涉及密码、破译、加密（如 Enigma、RSA）
   - "sequence"：事件有清晰的时间线或因果链（如语言的诞生过程）
   - "logic"：事件涉及冲突、博弈、选择（如浏览器大战、开源vs闭源）

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
    """基于史料内容 → LLM 分析 → 选择谜题类型 + 设计机制。"""
    user_input = state["user_input"]
    search_results = state.get("search_results", [])

    # 拼接史料文本
    sources_text = "\n\n".join(
        f"[来源{i+1}] {r.get('title', '')}\n{r.get('snippet', '')}\n{r.get('content', '')[:500]}"
        for i, r in enumerate(search_results)
    )

    prompt = f"""用户想了解的历史事件：{user_input}

以下是爬虫搜到的史料：
{sources_text}

请基于史料内容决定谜题类型和机制。如果史料太单薄，返回 material_sufficient=false。"""

    try:
        response = chat_json(prompt, system=SYSTEM_PROMPT)
        import json

        # 清洗 LLM 返回值——去掉可能的 markdown 代码块包裹
        response = response.strip()
        if response.startswith("```"):
            response = response.split("\n", 1)[1]
            if response.endswith("```"):
                response = response[:-3]

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
                "agent_logs": [{"agent": "planner", "action": "insufficient", "detail": result.get("reasoning", "")}],
            }

        return {
            "puzzle_type": result["puzzle_type"],
            "puzzle_design": result.get("puzzle_design", {}),
            "material_sufficient": True,
            "agent_logs": [{"agent": "planner", "action": "designed", "detail": result.get("reasoning", "")}],
        }

    except Exception as e:
        # LLM 调用失败 → 返回失败，不走后续 Agent
        return {
            "puzzle_type": "unknown",
            "puzzle_design": {},
            "material_sufficient": False,
            "error_message": f"策划Agent调用LLM失败: {str(e)}",
            "status": "failed",
            "agent_logs": [{"agent": "planner", "action": "error", "detail": str(e)}],
        }
