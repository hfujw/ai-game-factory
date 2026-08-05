# AI-Native Workflow · 时光像素

> 最后更新：2026-08-05
> 当前阶段：AI 原生工作流 v2，稳定运行中

## 项目是什么

一个 AI 原生系统。输入任意主题 → 编排 LLM 自己决定流程（搜几次、用什么形式、失败了退回哪步）→ 生成交互式 HTML 页面。**流程是 LLM 自己决定的，不被人写死。**

## 我是谁

朱子钦，衡水学院 2026 届应届生，秋招主攻 AI 应用工程岗。

## 技术栈

| 层 | 选型 | 原因 |
|----|------|------|
| LLM | DeepSeek API (deepseek-chat) | 便宜、中文好 |
| 编排 | 自研 async 循环（不是 LangGraph） | 全异步、LLM 自主决策 |
| Web | FastAPI + WebSocket | 实时推送思考过程 |
| 前端 | React 18 + Vite 5 + Tailwind 3 | 液态玻璃 + 光标聚光灯 |
| 搜索 | Bing（零 API Key） | 无需申请 |
| 验证 | Playwright 无头浏览器 | 真执行，不靠猜 |
| Python | venv Python 3.13 | 系统 3.8 不兼容 |

## 架构

```
用户输入 → 编排 LLM 主循环
              ├── search   搜素材（Bing + 33 示例话题）
              ├── design   选叙事形式（时间轴/对比表/卡片/流程图/地图）
              ├── compose  写文案 + 标注来源
              ├── render   生成 HTML（AsyncOpenAI, 16384 tokens）
              └── verify   Playwright 真执行 + 硬规则判决
              ↓
         交互式 HTML 页面
```

**硬边界**：最多 20 步、预算 ¥1、搜最多 8 次、render 后必须 verify、verify 失败强制回退、素材不足自动诚实模式。

## 目录结构

```
backend/app/
├── main.py                 FastAPI + WebSocket
├── agents/
│   └── orchestrator.py     编排 Agent（思考→行动→反馈主循环）
├── tools.py                5 工具（search/design/compose/render/verify）
├── llm_client.py           AsyncOpenAI 封装
├── ws_manager.py           WebSocket 管理
├── mcp/web_search.py       Bing 搜索
└── knowledge/kb.py         33 示例话题
frontend/src/
├── App.jsx                 主布局
├── components/
│   ├── DecisionLog.tsx      AI 思考流程主舞台
│   ├── StoryPanel.tsx       生成页面展示
│   ├── RevealLayer.tsx      光标聚光灯
│   └── ...
└── hooks/useWebSocket.js   实时推送
```

## 关键设计决策

1. 不用 LangGraph Pipeline——一个 async 循环 + LLM 决策，流程不是写死的
2. AsyncOpenAI 全链路异步——渲染期间也能推消息到前端
3. 审查外置——Playwright 真执行，不是 LLM 猜对错
4. 诚实模式——素材不足自动降级，不硬撑
5. 搜索死循环防护——连续 2 次搜空强制停止
6. DecisionLog 是核心产品——AI 思考过程全透明

## 运行

```bash
# 后端
cd backend && ..\venv\Scripts\python -m uvicorn app.main:app --port 8001

# 前端
cd frontend && npm run dev
```

## GitHub

https://github.com/hfujw/ai-native-workflow
