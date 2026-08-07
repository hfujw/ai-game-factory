# 时光像素 · 综合审查报告

> 2026-08-08 · 合并 api-review + architecture-review + code-review + ux-analysis

---

## 一、架构

### 依赖关系

```
core/ ← llm/ ← tools/ ← agents/ ← main.py
                              ↑
                          network/
```

**无循环依赖。** 依赖方向单向：`core → llm → tools → agents → main`。

### 目录职责

| 目录 | 职责 | 问题 |
|------|------|------|
| `core/` | 配置、异常、指标、幂等 | ✅ 底层，被所有模块依赖 |
| `llm/` | API 调用、输出清洗、熔断 | ✅ parser.py 零外部依赖，可独立测试 |
| `tools/` | 5 个工具（每文件一个） | ✅ 单向依赖 llm |
| `agents/` | 编排 + Agent 实现 | ⚠️ 依赖最重（引了 core/llm/tools/knowledge），方向正确 |
| `network/` | WebSocket + 限流 | ⚠️ rate_limiter 未接入 StateBackend |
| `state/` | 存储抽象 | ❌ 死代码——rate_limiter 和 circuit_breaker 都没用它 |
| `knowledge/` | KB + ChromaDB | ✅ 零 app 内部依赖 |

### demo.py 建议

迁到 `services/demo.py`——和未来 SQLite 历史记录放一起。

---

## 二、API 设计

### WebSocket 消息模型（已实现 `schemas/websocket.py`）

Pydantic 校验覆盖所有 event type：
- 客户端→服务端：GenerateRequest（1-500 字符、控制字符过滤、幂等键）、CancelRequest、PingRequest
- 服务端→客户端：Thinking、ThinkingStream、Heartbeat、ToolResult、HtmlChunk（max 100KB）、PageReady（max 500KB）、GenerationFailed

### SSE 降级方案

WebSocket 被防火墙拦截 → 自动降级为 SSE（Server-Sent Events）。前端 `new EventSource()` 替代 `new WebSocket()`。

### `/v1/` 路由前缀迁移

30 天过渡期：双路由并存 → 旧版返回 `Deprecation: true` 头 → 30 天后删除。

### 幂等键

客户端生成 UUID → 相同 key 1 小时内返回缓存结果。内存缓存 100 条上限，生产换 Redis。

---

## 三、代码质量

### orchestrator 圈复杂度

| 函数 | 行数 | 圈复杂度 |
|------|------|---------|
| `orchestrator_node` | 194 | **14** ⚠️ |
| `_decide` | 80 | 6 ✅ |
| `_execute_tool` | 45 | 8 ⚠️ |
| `_summarize` | 24 | 6 ✅ |

`orchestrator_node` 建议拆为 `_make_decision` + `_post_process` + `_handle_verify_result` 三个函数（Phase 4 时做）。

### 魔法数字

| 位置 | 值 | 建议常量 |
|------|-----|---------|
| `orchestrator.py:163` | `range(15)` | `HEARTBEAT_MAX_PULSES` |
| `orchestrator.py:164` | `sleep(4)` | `HEARTBEAT_INTERVAL` |
| `render_agent.py:59` | `range(2)` | `MAX_RETRY_ATTEMPTS` |
| `render_agent.py:73` | `len < 200` | `MIN_HTML_LENGTH` |

**建议**：提取到 `core/config.py`。

### try/except 审计

扫描 18 处，**5 处裸 except 缺日志**——已全部修复（加 `logger.debug`）。

### 缓存 key 改进

`_cache_key` 现在只取业务字段（`components/rationale/structure/visual_hint`），排除动态元数据（时间戳等）。

---

## 四、UX

### 推送策略

| 方案 | 用户感知 | 实现复杂度 |
|------|---------|-----------|
| A：自检后推送（当前） | 4/10 | 9/10 |
| B：先推原始→再推补丁 | 7/10 | 5/10 |
| C：流式推送+后台自检 | 8/10 | 6/10 |

**当前用 A，Phase 2 升级到 C。** 方案 A 已可靠运行。

### 移动端

- StoryPanel 宽度改为 `min(560px, calc(100vw - 32px))`
- DecisionLog 移动端从底部弹出全宽
- 输入框移动端加大触控区域 `py-4 text-base`

### 加载状态

当前**步骤进度线**（搜→定→书→绘→鉴）优于骨架屏/进度条——它告诉用户"AI 在做什么"而非"还要等多久"。
