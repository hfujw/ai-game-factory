# 时光像素 · 项目结构全解

> 2026-08-08 · 共 78 个文件

---

```
contract-review-agent/
│
├── CLAUDE.md                  ← Claude Code 项目指令（AI 助手的"使用说明书"）
├── README.md                  ← GitHub 仓库首页（架构图、快速开始、技术栈、设计决策）
├── SECURITY.md                ← 安全加固清单（STRIDE 威胁建模结果 + 修复状态）
├── PRIVACY.md                 ← 隐私声明（数据收集范围、GDPR 清单、依赖协议兼容性）
├── LICENSE                    ← MIT 开源协议
├── Caddyfile                  ← 生产环境反代配置（自动 HTTPS + WebSocket 代理 + Gzip）
├── docker-compose.yml         ← 一键部署（Caddy + Backend + 健康检查）
├── .gitignore                 ← Git 忽略规则（venv、API Key、日志、截图、构建产物）
│
├── .github/
│   └── workflows/
│       └── ci.yml             ← GitHub Actions（push 自动 ruff + pytest + docker build）
│
├── backend/
│   ├── .env                   ← 实际环境变量（API Key——不提交 Git）
│   ├── .env.example           ← 环境变量模板（可提交 Git，无真实 Key）
│   ├── Dockerfile             ← 后端镜像（Playwright 官方基础镜像 + 非 root 用户）
│   ├── requirements.txt       ← Python 依赖清单
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            ← 🚪 FastAPI 入口（WebSocket 端点 / 路由 / 限流 / 日志初始化 / 优雅关闭）
│   │   ├── demo.py            ← 📦 Demo 页面管理（5 个预生成 HTML 的存取 + fallback 占位页）
│   │   │
│   │   ├── core/              ← 🧱 基础设施层（最底层，不依赖任何项目内模块）
│   │   │   ├── config.py      ← 集中配置（pydantic-settings：API Key、预算、限流、超时、工具参数）
│   │   │   ├── exceptions.py  ← 统一异常体系（AppError → LLMError/RenderError/RateLimitError 等 6 子类）
│   │   │   ├── metrics.py     ← Prometheus 指标（5 Counter + 2 Histogram + 1 Gauge + /metrics 端点）
│   │   │   └── idempotency.py ← 幂等键中间件（防重复生成——内存缓存 1h + TTL 自动清理）
│   │   │
│   │   ├── llm/               ← 🤖 LLM 层（所有和 DeepSeek 打交道的东西）
│   │   │   ├── client.py      ← API 调用（chat / chat_json / chat_stream，含重试 + 断路器 + 记账）
│   │   │   ├── parser.py      ← 输出清洗（strip_fence：去 markdown 围栏 / clean_thought：截断冗余开场白）
│   │   │   └── circuit_breaker.py ← 断路器（三态状态机：CLOSED→OPEN→HALF_OPEN，连续 3 次失败熔断 30s）
│   │   │
│   │   ├── network/           ← 🌐 网络层
│   │   │   ├── ws_manager.py  ← WebSocket 连接管理（连接上限 + 单 IP 限制 + 踢旧连接 + 优雅关闭）
│   │   │   └── rate_limiter.py ← 速率限制（IP 1次/天 + 全站 ¥5/天 + 本地白名单 + 失败不扣）
│   │   │
│   │   ├── tools/             ← 🔧 5 个工具（每个独立文件，可单独替换）
│   │   │   ├── __init__.py    ← 工具注册表（TOOL_COST + TOOL_MAP + 统一导出）
│   │   │   ├── search.py      ← 搜索素材（Tavily API + 广告过滤 + 相关性检查）
│   │   │   ├── design.py      ← 叙事设计（LLM 分析素材 → 选形式：时间轴/卡片/百科等 7 种）
│   │   │   ├── compose.py     ← 文案撰写（LLM 写内容 + 每个事实标注来源和可信度）
│   │   │   ├── render.py      ← HTML 生成（LLM 流式 + 2 秒时间窗口兜底推送）
│   │   │   └── verify.py      ← 审查（硬规则：标签闭合/占位符 + Playwright 真执行 + 来源标注率）
│   │   │
│   │   ├── agents/            ← 🧠 编排层（Agent 实现 + 调度逻辑）
│   │   │   ├── __init__.py
│   │   │   ├── orchestrator.py ← ⭐ 核心：ReAct 主循环（while + _decide LLM决策 + 回退/诚实模式/搜索死循环防护）
│   │   │   ├── render_agent.py ← Phase 1：渲染 Agent（内部自检循环 + 缓存 + 修复重试）
│   │   │   ├── evaluate.py    ← 素材评估（非 LLM：统计相关条目数 → high/medium/low/none）
│   │   │   └── context.py     ← AgentState 字段定义（TypedDict，预留 LangGraph 迁移）
│   │   │
│   │   ├── knowledge/         ← 📚 知识库
│   │   │   ├── kb.py          ← 33 个示例话题加载 + 关键词匹配
│   │   │   ├── vector_store.py ← ChromaDB 语义向量检索（text2vec-base-chinese，"嬴政"→"秦始皇"）
│   │   │   ├── verified_events.json ← 25 个计算机史话题数据
│   │   │   └── verified_bagu.json   ← 8 个八股话题数据
│   │   │
│   │   ├── state/             ← 💾 存储抽象层
│   │   │   ├── __init__.py    ← 工厂（根据 STATE_BACKEND 配置选择 Memory/Redis 后端）
│   │   │   ├── base.py        ← 抽象接口（get / set / incr / expire 四方法）
│   │   │   └── memory.py      ← 内存实现（字典 + TTL 自动过期）
│   │   │
│   │   └── schemas/           ← 📋 消息模型
│   │       ├── __init__.py
│   │       └── websocket.py   ← WebSocket Pydantic 校验（ClientMessage / ServerMessage 联合类型）
│   │
│   └── tests/                 ← 🧪 28 个测试用例
│       ├── __init__.py
│       ├── conftest.py        ← 共享 fixture（sample_material）
│       ├── pytest.ini         ← pytest 配置（asyncio_mode = auto）
│       ├── test_material_eval.py      ← 素材评估（4 tests）
│       ├── test_orchestrator_decision.py ← 决策链路模拟（7 tests）
│       ├── test_rate_limiter.py        ← 限流器（5 tests）
│       ├── test_search_filter.py       ← 广告过滤（4 tests）
│       └── test_strip_fence.py         ← markdown 围栏清洗（8 tests）
│
├── frontend/
│   ├── .gitignore
│   ├── index.html             ← SPA 入口
│   ├── package.json           ← 依赖（React 18 / Vite 5 / Tailwind 3 / framer-motion / lucide-react）
│   ├── postcss.config.js      ← PostCSS 配置
│   ├── tailwind.config.js     ← Tailwind CSS 配置
│   ├── vite.config.js         ← Vite 构建配置（代理 /api → :8001 / WebSocket 代理）
│   │
│   ├── public/
│   │   ├── favicon.svg
│   │   ├── bg.mp4             ← 背景视频
│   │   └── images/
│   │       ├── base.jpg       ← 基底图（深色朦胧底）
│   │       └── reveal.jpg     ← 揭示图（光标聚光灯照亮）
│   │
│   └── src/
│       ├── main.jsx           ← React 挂载点
│       ├── index.css          ← Tailwind 指令 + 自定义动画 keyframes
│       ├── App.jsx            ← 🏠 主布局（液态玻璃 + 光标聚光灯 + 搜索框 + 标签云）
│       │
│       ├── components/
│       │   ├── SearchBubble.tsx    ← 🔍 搜索输入框（"免费试用 · 每日 1 次"）
│       │   ├── EventTags.tsx      ← 🏷️ 33 个示例话题标签云（右上角弹出面板）
│       │   ├── DecisionLog.tsx    ← 💭 AI 思考流程（步骤进度线 搜→定→书→绘→鉴 + 实时滚动气泡）
│       │   ├── StoryPanel.tsx     ← 📄 生成页面展示（流式渲染 + 显影动画 + 全屏/最小化）
│       │   ├── RevealLayer.tsx    ← ✨ 光标聚光灯（Canvas 2D 径向渐变 mask）
│       │   ├── FailureNotice.tsx  ← ⚠️ 失败弹窗（原因 + Demo 引导按钮）
│       │   └── ErrorBoundary.tsx  ← 🛡️ React 错误边界
│       │
│       └── hooks/
│           └── useWebSocket.js    ← 🔌 WebSocket Hook（连接/重连/流式接收/demo加载/断线指数退避）
│
└── docs/                     ← 📖 项目文档（9 份）
    ├── CUTS.md                       ← 减法记录（13 个被裁项及理由 + 捡回来时机）
    ├── UPGRADE_PLAN.md               ← 工程化升级完工文档（代码走读 6 条路径 + 面试速查表）
    ├── comprehensive-review.md       ← 综合审查（架构/API/代码质量/UX 四合一）
    ├── data-layer-diagnosis.md       ← 数据层深度诊断（持久化方案对比 / StateBackend 接入步骤）
    ├── performance-analysis.md       ← 性能剖析（多 Worker 方案 / 时序图 / 缓存命中率监控）
    ├── observability.md              ← 可观测性体系（Prometheus 指标 / OpenTelemetry / Grafana / 告警规则）
    ├── deployment-plan.md            ← 部署方案（Caddy / 蓝绿部署 / CI/CD Deploy Job / 零停机更新）
    ├── multi-agent-phase1-render.md  ← Phase 1 方案：RenderAgent 详细设计（含 3 轮代码审查修正）
    └── multi-agent-full-roadmap.md   ← 多 Agent 全景路线图（Phase 1 → Phase 5）
```

---

## 数据流一句话

```
用户输入 → WebSocket → RateLimiter → KB匹配+向量检索
    → Orchestrator while循环（_decide LLM决策 ×N）
        → 5工具（search/design/compose/render_agent/verify）
            → LLM调用（DeepSeek API，断路器+重试+记账）
                → HTML流式推前端 → verify通过 → 成品
```

## 依赖方向（单向，无循环）

```
core/ ← llm/ ← tools/ ← agents/ ← main.py
                              ↑
                          network/
```
