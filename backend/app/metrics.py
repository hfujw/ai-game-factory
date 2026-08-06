"""Prometheus 指标 — 面试时能说出"P99 渲染延迟 45s"。

3 Counter + 1 Histogram：Counter 证明"懂埋点"，Histogram 证明"懂性能"。
暴露为 /metrics 端点，Prometheus 生态直接采集。
"""

from prometheus_client import Counter, Histogram, Gauge, generate_latest

LLM_REQUESTS = Counter(
    "llm_requests_total",
    "Total LLM API calls",
    ["status", "tool"],  # status: success|timeout|error
)

LLM_LATENCY = Histogram(
    "llm_latency_seconds",
    "LLM API call latency",
    ["tool"],
    buckets=[1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0],
)

WS_CONNECTIONS = Gauge(
    "ws_connections_active",
    "Current active WebSocket connections",
)

GENERATIONS = Counter(
    "generations_total",
    "Total generation attempts",
    ["status"],  # status: success|failed|rate_limited|timeout
)


def metrics_text() -> str:
    """返回 Prometheus 文本格式的指标。"""
    return generate_latest().decode("utf-8")
