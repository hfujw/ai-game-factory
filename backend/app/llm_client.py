"""LLM 客户端 — 统一封装 DeepSeek API 调用，含超时/重试/内容校验。

所有 Agent 通过这个模块调 LLM，不直接写 openai 调用。
"""

import os
import logging
import time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
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

# 全局花费追踪
_cost_records: list[dict] = []


def get_cost_summary() -> dict:
    """返回累计花费统计。"""
    total_input = sum(r["input_tokens"] for r in _cost_records)
    total_output = sum(r["output_tokens"] for r in _cost_records)
    # DeepSeek V4-Pro: ¥3/M input, ¥6/M output
    cost_input = total_input / 1_000_000 * 3
    cost_output = total_output / 1_000_000 * 6
    return {
        "calls": len(_cost_records),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "estimated_cost_rmb": round(cost_input + cost_output, 4),
        "records": _cost_records[-20:],  # 最近20条
    }


def reset_cost():
    """重置花费计数器。"""
    _cost_records.clear()


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

            # 记录 token 使用
            usage = response.usage
            if usage:
                _cost_records.append({
                    "input_tokens": usage.prompt_tokens,
                    "output_tokens": usage.completion_tokens,
                    "model": model or DEFAULT_MODEL,
                })
                logger.info("LLM tokens: in=%d out=%d total=%d | 累计¥%.4f",
                            usage.prompt_tokens, usage.completion_tokens,
                            usage.total_tokens, get_cost_summary()["estimated_cost_rmb"])

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
