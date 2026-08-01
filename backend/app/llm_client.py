"""LLM 客户端 — 统一封装 DeepSeek API 调用，含超时/重试/内容校验。

所有 Agent 通过这个模块调 LLM，不直接写 openai 调用。
"""

import os
import logging
import time
from openai import OpenAI

logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 120  # 单次 LLM 调用最长等待秒数
MAX_RETRIES = 2        # 429/5xx 自动重试次数

# API Key 启动时校验
_api_key = os.getenv("DEEPSEEK_API_KEY")
if not _api_key:
    raise RuntimeError("DEEPSEEK_API_KEY 环境变量未设置，请检查 backend/.env 文件")

client = OpenAI(
    api_key=_api_key,
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    timeout=DEFAULT_TIMEOUT,
)

DEFAULT_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")


def _strip_markdown_fence(text: str) -> str:
    """清洗 LLM 可能包裹的 markdown 代码块。所有 Agent 共用。"""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```html"):
        text = text[7:]
    elif text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def chat(prompt: str, system: str = "", model: str = None, temperature: float = 0.7) -> str:
    """单轮对话，含自动重试和内容为空保护。

    Returns:
        LLM 文本回复，保证至少是空字符串（不会返回 None）
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            logger.debug("LLM call attempt %d/%d, model=%s, temp=%.2f",
                         attempt + 1, MAX_RETRIES + 1, model or DEFAULT_MODEL, temperature)

            response = client.chat.completions.create(
                model=model or DEFAULT_MODEL,
                messages=messages,
                temperature=temperature,
            )

            content = response.choices[0].message.content
            if content is None:
                logger.warning("LLM returned None content (finish_reason may be 'length'), retrying...")
                continue

            # 打印 token 使用统计
            usage = response.usage
            if usage:
                logger.info("LLM tokens: prompt=%d completion=%d total=%d",
                            usage.prompt_tokens, usage.completion_tokens, usage.total_tokens)

            return content

        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES:
                wait = 2 ** attempt  # 1s, 2s
                logger.warning("LLM call failed (attempt %d/%d): %s, retrying in %ds...",
                               attempt + 1, MAX_RETRIES + 1, e, wait)
                time.sleep(wait)
            else:
                logger.error("LLM call failed after %d attempts: %s", MAX_RETRIES + 1, e)

    raise last_error or RuntimeError("LLM call failed with unknown error")


def chat_json(prompt: str, system: str = "", model: str = None) -> str:
    """调 LLM 返回 JSON 格式文本。内部调用 chat()，temperature 固定 0.1。"""
    return chat(prompt, system=system, model=model, temperature=0.1)
