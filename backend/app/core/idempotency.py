"""幂等键中间件——相同 key 的重复请求返回缓存结果。

防止用户网络波动时重复点击"生成"导致双倍 LLM 费用。
"""

import time
import logging
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# 内存缓存（生产换成 Redis StateBackend）
_results: dict[str, dict] = {}
_ttl: dict[str, float] = {}
IDEMPOTENCY_TTL = 3600  # 1 小时


async def check_idempotency(key: str | None) -> dict | None:
    """检查幂等键是否已处理过。返回缓存结果或 None。"""
    if not key:
        return None

    now = time.monotonic()
    if key in _results:
        if now - _ttl.get(key, 0) < IDEMPOTENCY_TTL:
            logger.info("idempotency=hit | key=%s", key[:8])
            return _results[key]
        # 过期清理
        _results.pop(key, None)
        _ttl.pop(key, None)

    return None


def store_idempotency_result(key: str | None, result: dict):
    """存储幂等结果。"""
    if not key:
        return
    now = time.monotonic()
    _results[key] = result
    _ttl[key] = now

    # 清理过期项（超过 100 条时）
    if len(_results) > 100:
        stale = [k for k, t in _ttl.items() if now - t > IDEMPOTENCY_TTL]
        for k in stale:
            _results.pop(k, None)
            _ttl.pop(k, None)


def validate_idempotency_key(key: str | None) -> str | None:
    """校验幂等键格式。"""
    if key is None:
        return None
    if len(key) < 8 or len(key) > 128:
        raise HTTPException(400, "idempotency_key 长度须在 8-128 字符之间")
    if not all(c.isalnum() or c in "-_" for c in key):
        raise HTTPException(400, "idempotency_key 只能包含字母数字和连字符")
    return key
