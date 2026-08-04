# AI-Native Workflow · 时光像素

> 输入任意主题 → AI 自主决策每一步 → 生成交互式 HTML 页面  
> 不是"调了 LLM 的流水线"，是 **LLM 自己决定流程** 的 AI 原生系统

[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
![Python](https://img.shields.io/badge/python-3.13-blue)
![FastAPI](https://img.shields.io/badge/fastapi-0.111-green)
![React](https://img.shields.io/badge/react-18-blue)

---

## 为什么说它是 AI-Native？

不是因为有 LLM——是因为**流程不是人写死的**。

| 传统 Pipeline | AI-Native Workflow |
|-------------|-------------------|
| 人决定"先搜→再设计→再写→再审查" | LLM 自己决定：搜几次？跳过设计直接写？审查不过退给谁？ |
| 审查不通过→固定退回上一步 | LLM 诊断病因→退回正确的节点 |
| 素材不足→硬着头皮生成→失败 | 外置评估自动降级为"诚实模式" |
| 搜索无结果→反复搜直到耗尽预算 | 连续 2 次搜空→强制停止 |
| 生成的代码对不对→LLM 自己猜 | Playwright 无头浏览器真执行验证 |

---

## 架构

```
用户输入
    ↓
编排 LLM（自己决定流程，不被人写死）
    ├── search     搜素材（Bing + 33 个示例话题知识库）
    ├── design     选叙事形式（时间轴/对比表/卡片/流程图/地图/百科）
    ├── compose    写文案 + 每个数字标注来源
    ├── render     生成 HTML（AsyncOpenAI，16384 token 输出上限）
    └── verify     Playwright 真执行 + 硬规则检查 + 判决
    ↓
交互式 HTML 页面
```

**硬边界**（LLM 不能突破）：最多 20 步、预算 ¥1、搜最多 8 次、render 后必须 verify、同一工具连续失败强制换策略、素材不足自动诚实模式。

---

## 快速开始

```bash
# 后端
cd backend
..\venv\Scripts\python -m uvicorn app.main:app --port 8001

# 前端
cd frontend
npm run dev
```

浏览器打开 `http://localhost:5173`，输入任意主题开始。

---

## 项目结构

```
backend/app/
├── main.py              FastAPI + WebSocket 入口
├── orchestrator.py      编排 Agent（思考→行动→反馈主循环，全 async）
├── tools.py             5 个工具（search/design/compose/render/verify）
├── llm_client.py        AsyncOpenAI 封装（DeepSeek）
├── ws_manager.py        WebSocket 连接管理（safe send）
├── web_search.py        Bing→DuckDuckGo 搜索（零 API Key）
└── kb.py                33 个示例话题知识库
frontend/src/
├── App.jsx              主布局（液态玻璃 + 光标聚光灯）
├── components/
│   ├── DecisionLog.tsx   AI 思考流程主舞台（实时滚动）
│   ├── StoryPanel.tsx    iframe 展示生成页面
│   ├── SearchBubble.tsx  搜索输入框
│   ├── EventTags.tsx     示例话题下拉
│   ├── AgentBuds.tsx     工具状态灯
│   ├── RevealLayer.tsx   光标聚光灯 Canvas mask
│   ├── FailureNotice.tsx 失败提示
│   └── ErrorBoundary.tsx React 错误边界
└── hooks/
    └── useWebSocket.js   WebSocket 实时推送 + 防抖
```

---

## 关键词

`ai-native` `ai-workflow` `llm-orchestration` `agentic-workflow` `visual-storytelling` `ai-agent` `langchain-alternative` `playwright-verification` `async-openai` `deepseek-api` `fastapi-websocket` `react-tailwind`

---

## GitHub

https://github.com/hfujw/ai-native-workflow
