"""LLM 客户端 — 统一封装 DeepSeek API 调用。

所有 Agent 通过这个模块调 LLM，不直接写 openai 调用。
方便以后切换模型（只改这里，不改每个 Agent）。
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
)

DEFAULT_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")


def chat(prompt: str, system: str = "", model: str = None, temperature: float = 0.7) -> str:
    """单轮对话——发一条 prompt，返回 LLM 的文本回复。

    Args:
        prompt: 用户消息
        system: 系统提示（设定角色和行为）
        model: 模型名，默认 deepseek-chat
        temperature: 创造性 0-1。代码生成用 0.3，创意写作用 0.7

    Returns:
        LLM 的文本回复
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=model or DEFAULT_MODEL,
        messages=messages,
        temperature=temperature,
    )
    return response.choices[0].message.content


def chat_json(prompt: str, system: str = "", model: str = None) -> str:
    """调 LLM 并尽量返回 JSON 格式。

    和 chat() 一样，但 temperature 设低（0.1），减少 JSON 外的废话。
    """
    return chat(prompt, system=system, model=model, temperature=0.1)
