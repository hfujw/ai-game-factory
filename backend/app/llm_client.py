"""LLM 客户端 — DeepSeek API 异步封装。"""

import os
import re
import time
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

_cost_records: list[dict] = []   # 保留全局，作为 fallback

def get_cost_summary(records: list[dict] | None = None) -> dict:
    """计算费用。传入 records 则计算该列表，否则回退到全局记录。"""
    target = records if records is not None else _cost_records
    
    total_input = sum(r["input_tokens"] for r in target)
    total_output = sum(r["output_tokens"] for r in target)
    cost_input = total_input / 1_000_000 * 3
    cost_output = total_output / 1_000_000 * 6
    return {
        "calls": len(target),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "estimated_cost_rmb": round(cost_input + cost_output, 4),
        "records": target[-20:],
    }


def _strip_markdown_fence(text: str) -> str:
    """去掉 LLM 响应中的 markdown 代码围栏。用 regex 替代硬编码长度——支持 ```json、```html、```python 等任意语言标记。"""
    text = text.strip()
    text = re.sub(r'^```[a-zA-Z]*\s*\n?', '', text)   # 开头 fence（``` 后可跟任意语言标记）
    text = re.sub(r'\n?```\s*$', '', text)              # 结尾 fence
    return text.strip()


async def chat(prompt: str, system: str = "", model: str = None, temperature: float = 0.7,
               max_tokens: int = 16384, session_records: list[dict] | None = None,
               label: str = "unknown") -> str:
    """异步单轮对话，含自动重试。

    session_records: 传入则写入该会话独立账本，不污染全局记录。
    label: Prometheus 指标的 tool 标签（如 "decide"/"render"），用于按工具统计延迟。
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    last_error = None
    t0 = time.monotonic()
    from app.circuit_breaker import llm_breaker
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await llm_breaker.call(
                client.chat.completions.create(
                model=model or DEFAULT_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                )
            )

            content = response.choices[0].message.content
            if content is None:
                logger.warning("LLM returned None content, retrying...")
                continue

            logger.debug("LLM REQUEST — system=%d chars, user=%d chars", len(system), len(prompt))
            if os.getenv("LOG_PROMPTS", "0") == "1":
                logger.debug("LLM SYSTEM:\n%s", system[:3000])
                logger.debug("LLM PROMPT:\n%s", prompt[:5000])
                logger.debug("LLM RESPONSE:\n%s", content[:5000])

            usage = response.usage
            if usage:
                entry = {
                    "input_tokens": usage.prompt_tokens,
                    "output_tokens": usage.completion_tokens,
                    "model": model or DEFAULT_MODEL,
                }
                # 有会话账本写会话账本，否则回退到全局
                if session_records is not None:
                    session_records.append(entry)
                else:
                    _cost_records.append(entry)
                # Prometheus 指标
                from app.metrics import LLM_REQUESTS, LLM_LATENCY
                LLM_LATENCY.labels(tool=label).observe(time.monotonic() - t0)
                LLM_REQUESTS.labels(status="success", tool=label).inc()

                logger.info("LLM tokens: in=%d out=%d total=%d | 累计¥%.4f",
                            usage.prompt_tokens, usage.completion_tokens,
                            usage.total_tokens,
                            get_cost_summary(session_records)["estimated_cost_rmb"])
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
                from app.metrics import LLM_REQUESTS, LLM_LATENCY
                LLM_LATENCY.labels(tool=label).observe(time.monotonic() - t0)
                LLM_REQUESTS.labels(status="error", tool=label).inc()

    raise last_error or RuntimeError("LLM call failed with unknown error")


async def chat_json(prompt: str, system: str = "", model: str = None,
                    session_records: list[dict] | None = None) -> str:
    """异步 JSON 调用。"""
    return await chat(prompt, system=system, model=model, temperature=0.1,
                      session_records=session_records)


async def chat_stream(prompt: str, system: str = "", model: str = None,
                      temperature: float = 0.3, max_tokens: int = 16384,
                      session_records: list[dict] | None = None,
                      label: str = "unknown"):
    """流式输出——逐 chunk yield 文本片段。

    不修改 chat() 签名。session_records 写入独立账本，label 用于 Prometheus。
    """
    import time as _time
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    t0 = _time.monotonic()
    try:
        response = await client.chat.completions.create(
            model=model or DEFAULT_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            stream_options={"include_usage": True},
        )

        total_tokens = 0
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
            if chunk.usage:
                total_tokens = chunk.usage.total_tokens

        # Prometheus 埋点
        from app.metrics import LLM_REQUESTS, LLM_LATENCY
        LLM_LATENCY.labels(tool=label).observe(_time.monotonic() - t0)
        LLM_REQUESTS.labels(status="success", tool=label).inc()

    except Exception:
        from app.metrics import LLM_REQUESTS, LLM_LATENCY
        LLM_LATENCY.labels(tool=label).observe(_time.monotonic() - t0)
        LLM_REQUESTS.labels(status="error", tool=label).inc()
        raise
