# AI-Native Workflow · 时光像素

> 最后更新：2026-08-08
> 当前阶段：Phase 1 RenderAgent 完成，28 tests，架构分层完毕

## 项目是什么

一个 AI 原生系统。输入任意主题 → LLM 自己决定流程（搜几次、用什么形式、失败了退回哪步）→ 生成交互式 HTML 页面。**流程是 LLM 自己决定的，不被人写死。**

## 我是谁

朱子钦，衡水学院 2026 届应届生，秋招主攻 AI 应用工程岗。

## 技术栈

| 层 | 选型 | 原因 |
|----|------|------|
| LLM | DeepSeek API (deepseek-chat) | 便宜、中文好、OpenAI SDK 兼容 |
| 编排 | 自研 async while 循环（不是 LangGraph） | LLM 自主决策、全异步 |
| Web | FastAPI + WebSocket | 实时推送思考过程 |
| 前端 | React 18 + Vite 5 + Tailwind 3 | 液态玻璃 + 光标聚光灯 |
| 搜索 | Tavily（零配置） | 国内可直连，不配 Key 也能跑 |
| 验证 | Playwright 无头浏览器 | 真执行，不靠猜 |
| 向量 | ChromaDB + text2vec-base-chinese | "嬴政"→"秦始皇"语义匹配 |
| 指标 | Prometheus（10 个指标） | /metrics 端点 |
| 部署 | Docker Compose + Caddy | 自动 HTTPS |
| Python | venv Python 3.13 | 系统 3.8 不兼容 |

## 架构

```
用户输入 → RateLimiter → Orchestrator async while 循环
              │
              ├── _decide() → LLM 自主决策每一步
              │
              ├── search   Tavily + KB 关键词 + ChromaDB 向量检索
              ├── design   选叙事形式（7 种组件可选）
              ├── compose  写文案 + 来源标注 + 可信度
              ├── render   RenderAgent（自检 + 缓存 + 重试）
              └── verify   Playwright 真执行 + 硬规则 + 事实核查
              ↓
         交互式 HTML 页面
```

**硬边界**：20 步、¥1 预算、搜 ≤8 次、render 后必须 verify、verify 失败强制回退、素材不足诚实模式、搜索死循环防护。

## 目录结构

```
backend/app/
├── main.py                     🚪 FastAPI + WebSocket 入口
├── demo.py                     📦 Demo 页面管理
├── core/                       🧱 config / exceptions / metrics / idempotency
├── llm/                        🤖 client / parser / circuit_breaker
├── network/                    🌐 ws_manager / rate_limiter
├── tools/                      🔧 search / design / compose / render / verify
├── agents/                     🧠 orchestrator / render_agent / evaluate / context
├── knowledge/                  📚 kb / vector_store
├── state/                      💾 base / memory（预留 Redis）
└── schemas/                    📋 WebSocket Pydantic 模型

frontend/src/
├── App.jsx                     主布局（液态玻璃 + 光标聚光灯）
├── components/
│   ├── DecisionLog.tsx         AI 思考流程（5 步进度线）
│   ├── StoryPanel.tsx          生成页面（流式渲染 + 显影动画）
│   ├── RevealLayer.tsx         光标聚光灯 Canvas mask
│   ├── SearchBubble.tsx        搜索输入框
│   ├── EventTags.tsx           33 个示例话题标签云
│   ├── FailureNotice.tsx       失败提示 + demo 引导
│   └── ErrorBoundary.tsx       React 错误边界
└── hooks/useWebSocket.js       WebSocket + 断线重连 + 流式接收
```

## 关键设计决策

1. 不用 LangGraph——async while 循环 + LLM 决策，5 个工具不需要状态图
2. RenderAgent 内部自检——render 是 token 最大头，Agent 内部自检减少回退浪费
3. 审查外置——Playwright 真执行 + 硬规则 + 事实核查，不是 LLM 猜对错
4. 诚实模式——素材不足自动降级，标注"资料有限"，不编造
5. 搜索死循环防护——3 次上限 或 最近 2 次全空强制禁止
6. 向量语义检索——"嬴政"匹配到"秦始皇"，关键词做不到的
7. 断路器——连续 3 次 LLM 失败熔断 30s，防级联故障
8. 预算双控——虚拟 ¥1/次 + 真实 ¥5/天，公网不破产
9. DecisionLog 是核心产品——AI 思考过程全透明
10. 流式渲染——contentDocument.write 不频闪

## 当前状态

- ✅ 架构分层完毕（7 目录，单向依赖，无循环）
- ✅ Phase 1 RenderAgent 上线（自检 + 缓存 + 重试，3 轮审查修 15 问题）
- ✅ 安全加固（输入长度限制 + IP 连接限制 + 日志 30 天 + health 双探针）
- ✅ 合规补全（LICENSE MIT + PRIVACY GDPR + SECURITY STRIDE）
- ✅ 28 tests 全绿
- 📋 下一步：Phase 2 DesignerAgent（合并 design+compose）

## 运行

```bash
# 后端
cd backend && ..\venv\Scripts\python -m uvicorn app.main:app --port 8001

# 前端
cd frontend && npm run dev
```

## GitHub

https://github.com/hfujw/ai-native-workflow
