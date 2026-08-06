# AI-Native Workflow · 时光像素

> 输入任意主题 → LLM 自主决策每一步 → 生成交互式 HTML 页面
> 不是"调了 LLM 的流水线"，是 **LLM 自己决定流程** 的 AI 原生系统

[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
![Python](https://img.shields.io/badge/python-3.13-blue)
![FastAPI](https://img.shields.io/badge/fastapi-0.141-green)
![React](https://img.shields.io/badge/react-18-blue)
![Tests](https://img.shields.io/badge/tests-28%20passed-brightgreen)

---

## 为什么是 AI-Native？

流程不是人写死的。LLM 自己决定：搜几次？跳过搜索直接用自身知识？审查不过退给谁？

| 传统 Pipeline | 本系统 |
|-------------|--------|
| 人决定"先搜→再设计→再写→再审查" | LLM 自主决策每一步调什么工具 |
| 审查不通过→固定退回上一步 | LLM 诊断病因→退回正确的节点 |
| 素材不足→硬着头皮生成→失败 | LLM 主动触发"诚实模式"降级 |
| 搜索死循环→耗尽预算 | 搜索 8 次硬拦截 + LLM 自身知识兜底 |
| 生成的代码对不对→LLM 自己猜 | Playwright 无头浏览器真执行验证 |

---

## 架构

```mermaid
flowchart TD
    U[用户输入主题] --> WS[WebSocket]
    WS --> RL[Rate Limiter<br/>IP 1次/天 · ¥5 日预算帽]
    RL --> O[Orchestrator · ReAct 循环]
    O --> D[_decide · LLM 决策]
    D -->|自主选择| S[Search<br/>Tavily + KB + RAG]
    D -->|自主选择| DE[Design<br/>选叙事形式]
    D -->|自主选择| C[Compose<br/>文案 + 来源标注]
    D -->|自主选择| R[Render<br/>HTML 流式生成]
    D -->|自主选择| V[Verify<br/>Playwright 真执行]
    V -->|通过| HTML[交互式 HTML]
    V -->|不通过| D
    S -->|搜不到| D
    R -->|必须| V
```

**硬边界**（LLM 不能突破）：最多 20 步 · 预算 ¥1 · 搜索 ≤8 次 · render 后必须 verify · 连续 2 次 verify 失败强制终止。

---

## 快速开始

### 前置要求

- Python 3.11+
- Node.js 18+
- DeepSeek API Key（[注册地址](https://platform.deepseek.com)）
- Tavily Search API Key（[注册地址](https://tavily.com)，免费 1000 次/月，不配也能用）

### 1. 克隆项目

```bash
git clone https://github.com/hfujw/ai-native-workflow.git
cd ai-native-workflow
```

### 2. 配置环境变量

```bash
# 复制配置模板
cp backend/.env.example backend/.env

# 编辑 backend/.env，填入你的 Key：
# DEEPSEEK_API_KEY=sk-xxxxxxxx
# TAVILY_API_KEY=tvly-xxxxxxxx（可选——不配也能跑，LLM 会用自身知识）
```

### 3. 安装依赖

```bash
# 后端
cd backend
python -m venv venv
venv\Scripts\pip install -r requirements.txt   # Windows
# source venv/bin/pip install -r requirements.txt  # macOS/Linux

# 前端
cd ../frontend
npm install
```

### 4. 启动

```bash
# 终端 1：后端（端口 8001）
cd backend
venv\Scripts\python -m uvicorn app.main:app --port 8001

# 终端 2：前端（端口 5173）
cd frontend
npm run dev
```

浏览器打开 `http://localhost:5173`，输入任意主题即可。

### 首次启动说明

- ChromaDB 中文模型（~400MB）首次会自动从 `hf-mirror.com` 下载，走国内镜像不需要代理
- 下载失败不影响使用——语义检索不可用，关键词检索 + LLM 自身知识仍然正常工作
- Tavily Key 不配也没关系——搜索返回空，LLM 用自己的知识生成

---

## Docker 部署

```bash
# 一键启动
docker-compose up

# 后台运行
docker-compose up -d
```

浏览器打开 `http://localhost:8000`。

---

## 项目结构

```
backend/app/
├── main.py                 FastAPI + WebSocket 入口
├── config.py               pydantic-settings 集中配置
├── exceptions.py           自定义异常体系
├── llm_client.py           AsyncOpenAI 封装 + 流式输出
├── tools.py                5 个工具（search/design/compose/render/verify）
├── ws_manager.py           WebSocket 连接管理 + 优雅关闭
├── rate_limiter.py         IP 限流 + 日预算帽
├── circuit_breaker.py      断路器（三态状态机）
├── metrics.py              Prometheus /metrics 端点
├── demo.py                 Demo 预生成页面管理
├── agents/
│   └── orchestrator.py     ReAct 编排主循环
├── knowledge/
│   ├── kb.py               33 个示例话题 + 关键词检索
│   └── vector_store.py     ChromaDB 语义向量检索
└── state/
    ├── base.py             状态抽象层（Memory/Redis）
    ├── memory.py           内存实现
    └── agent_state.py      AgentState 数据结构

backend/demos/              预生成 HTML（本地跑一次替换）
backend/tests/              28 个 pytest 用例

frontend/src/
├── App.jsx                 主布局（液态玻璃 + 光标聚光灯）
├── components/
│   ├── DecisionLog.tsx     AI 思考流程（步骤进度线 + 实时滚动）
│   ├── StoryPanel.tsx      生成页面展示（显影动画 + 流式渲染）
│   ├── SearchBubble.tsx    搜索输入框
│   ├── EventTags.tsx       33 个示例话题标签云
│   ├── RevealLayer.tsx     光标聚光灯 Canvas mask
│   ├── FailureNotice.tsx   失败提示 + demo 引导
│   └── ErrorBoundary.tsx   React 错误边界
└── hooks/
    └── useWebSocket.js     WebSocket + 断线重连 + 流式接收
```

---

## 关键设计决策

| 决策 | 为什么 |
|------|--------|
| 不用 LangGraph | 当前 5 个工具的复杂度用 async while 循环最合适。tool 接口已标准化为 state-in/state-out，预留了 LangGraph 迁移能力 |
| 验证层外置 | Playwright 真执行，不是 LLM 猜对错。正则硬规则 + 浏览器执行 + 事实核查三阶段 |
| 诚实模式 | 素材不足时 LLM 主动降级为"资料有限"的诚实页面，不编造事实 |
| 搜索是可选增强 | LLM 决策中心——有把握的话题直接跳过搜索，不确定才搜。搜索不到 LLM 用自身知识兜底 |
| Tavily 替代 Bing | 国内可直连，返回 JSON 已清洗文本。不配 Key 也能跑 |
| 流式渲染 | `contentDocument.write` 写 DOM，不换 `srcdoc`——不频闪，用户看到页面逐段"长出来" |
| 断路器 | 连续 3 次 LLM API 失败自动熔断 30s，防止级联故障浪费重试和 Token |
| 预算控制 | 每个工具虚拟定价，总预算 ¥1 硬上限。IP 1 次/天试用 + 全站 ¥5/天，公网不破产 |

---

## 配置项

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `DEEPSEEK_API_KEY` | **必填** | DeepSeek API Key |
| `TAVILY_API_KEY` | 空（不配也能跑） | Tavily Search API Key |
| `DAILY_BUDGET` | 5.0 | 全站日预算（元） |
| `TRIALS_PER_IP` | 1 | 每 IP 每天试用次数 |
| `MAX_STEPS` | 20 | Agent 最大循环步数 |
| `GENERATION_TIMEOUT` | 300 | 单次生成超时（秒） |
| `LOG_PROMPTS` | 0 | 设为 1 记录完整 prompt（调试用） |
| `STATE_BACKEND` | memory | memory / redis（多实例部署时） |

---

## 关键词

`ai-native` `ai-workflow` `llm-orchestration` `react-agent` `visual-storytelling` `ai-agent` `langchain-alternative` `playwright-verification` `deepseek-api` `fastapi-websocket` `chromadb` `prometheus` `tavily` `honest-ai` `circuit-breaker`
