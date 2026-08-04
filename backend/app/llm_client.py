"""LLM 客户端 — DeepSeek API 异步封装。"""

import os
import logging
import asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()
logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 120
MAX_RETRIES = 2

_api_key = os.getenv("DEEPSEEK_API_KEY")
if not _api_key:
    raise RuntimeError("DEEPSEEK_API_KEY 环境变量未设置")

client = AsyncOpenAI(
    api_key=_api_key,
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    timeout=DEFAULT_TIMEOUT,
)

DEFAULT_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
_cost_records: list[dict] = []


def get_cost_summary() -> dict:
    total_input = sum(r["input_tokens"] for r in _cost_records)
    total_output = sum(r["output_tokens"] for r in _cost_records)
    cost_input = total_input / 1_000_000 * 3
    cost_output = total_output / 1_000_000 * 6
    return {
        "calls": len(_cost_records),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "estimated_cost_rmb": round(cost_input + cost_output, 4),
        "records": _cost_records[-20:],
    }


def reset_cost():
    _cost_records.clear()


def _strip_markdown_fence(text: str) -> str:
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


async def chat(prompt: str, system: str = "", model: str = None, temperature: float = 0.7, max_tokens: int = 16384) -> str:
    """异步单轮对话，含自动重试。"""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await client.chat.completions.create(
                model=model or DEFAULT_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            content = response.choices[0].message.content
            if content is None:
                logger.warning("LLM returned None content, retrying...")
                continue

            logger.debug("LLM REQUEST — system=%d chars, user=%d chars", len(system), len(prompt))
            logger.debug("LLM SYSTEM:\n%s", system[:3000])
            logger.debug("LLM PROMPT:\n%s", prompt[:5000])
            logger.debug("LLM RESPONSE:\n%s", content[:5000])

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
                wait = 2 ** attempt
                logger.warning("LLM call failed (attempt %d/%d): %s, retrying in %ds...",
                               attempt + 1, MAX_RETRIES + 1, e, wait)
                await asyncio.sleep(wait)
            else:
                logger.error("LLM call failed after %d attempts: %s", MAX_RETRIES + 1, e)

    raise last_error or RuntimeError("LLM call failed with unknown error")


async def chat_json(prompt: str, system: str = "", model: str = None) -> str:
    """异步 JSON 调用。"""
    return await chat(prompt, system=system, model=model, temperature=0.1)
