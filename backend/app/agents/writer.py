"""文案 Agent — 基于史料写游戏剧本。

输入：search_results + puzzle_type + puzzle_design
输出：game_script（背景故事 + 谜题描述 + 通关/失败台词）

使用 DeepSeek 生成有沉浸感的游戏叙事。
"""

from app.graph.state import GameFactoryState
from app.llm_client import chat

SYSTEM_PROMPT = """你是一个游戏编剧，专门为像素风解谜小游戏写剧本。

你会收到：
- 一段计算机历史事件的史料
- 谜题类型（cipher/sequence/logic）和机制设计

你的任务：写一份 300-500 字的游戏剧本，包含三部分：
1. 【背景故事】：把历史事件改写成有沉浸感的开场叙事（让玩家觉得"我在现场"）
2. 【谜题描述】：基于策划给的谜题机制，用游戏化的语言告诉玩家要做什么
3. 【通关台词】和【失败台词】：各一句，像素游戏风格的简短台词

风格要求：
- 像素风、复古感、像 Game Boy 时代的游戏文本
- 不要学术腔，要有冒险感
- 中文，加少量英文术语可以（如 Enigma、Python）"""


def writer_node(state: GameFactoryState) -> dict:
    """基于史料 + 谜题机制 → LLM 生成游戏剧本。"""
    user_input = state["user_input"]
    puzzle_type = state["puzzle_type"]
    puzzle_design = state.get("puzzle_design", {})
    search_results = state.get("search_results", [])

    # 拼史料
    sources_text = "\n".join(
        f"- {r.get('title', '')}: {r.get('snippet', '')}"
        for r in search_results[:3]
    )

    prompt = f"""历史事件：{user_input}
谜题类型：{puzzle_type}
谜题机制：{puzzle_design.get('mechanic', '')}
规则：{puzzle_design.get('rules', '')}

史料参考：
{sources_text}

请写一份游戏剧本（300-500字），包含【背景故事】【谜题描述】【通关台词】【失败台词】四个部分。"""

    try:
        script = chat(prompt, system=SYSTEM_PROMPT, temperature=0.8)
        return {
            "game_script": script,
            "script_keywords": [user_input, puzzle_type],
            "agent_logs": [{"agent": "writer", "action": "script_written", "detail": f"{len(script)} chars"}],
        }
    except Exception as e:
        return {
            "game_script": f"[剧本生成失败: {e}]\n\n历史事件：{user_input}\n谜题类型：{puzzle_type}",
            "script_keywords": [user_input, puzzle_type],
            "agent_logs": [{"agent": "writer", "action": "error", "detail": str(e)}],
        }
