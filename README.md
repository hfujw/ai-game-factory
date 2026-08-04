# 时光像素 · AI 视觉叙事引擎

> 输入任意主题 → AI 自主决策 → 生成精美的交互式 HTML 页面

## 它是什么

一个 AI 原生系统。说"AI 原生"不是因为它调了 LLM，而是因为**流程是 AI 自己决定的**——搜多少次、用什么形式呈现、失败了退回哪一步，全是 AI 的决策。

用户输入任意主题——AI 自己搜索素材，自己决定用时间轴还是对比表还是卡片集，自己写文案并标注信息来源，自己生成 HTML 并用 Playwright 真执行验证。整个过程在前端驾驶舱实时可见。每个行动之前 AI 先"思考"——用户看到思考气泡，AI 才开始干活。

## 架构

```
用户输入
    ↓
编排 LLM（自己决定流程，不被人写死）
    ├── search   搜素材（Bing + KB）
    ├── design   选叙事形式（时间轴/对比表/卡片/流程图/地图/百科）
    ├── compose  写文案 + 每个事实标注来源
    ├── render   生成 HTML（max_tokens=8192，截断自动检测）
    └── verify   Playwright 真执行 + 事实核查 + 判决
    ↓
交互式视觉叙事页面
```

## 为什么不做游戏了

上一版做解谜游戏。约束太重——必须能玩、必须有 5 个 screen、必须有游戏循环。LLM 写到一半截断，审查反复打回，¥0.50 打水漂。把约束从"必须能玩"松绑到"必须好看且准确"，AI 决策空间 ×5，稳定性 ×10。

## 运行

```bash
# 后端
cd backend && ..\venv\Scripts\python -m uvicorn app.main:app --reload

# 前端
cd frontend && npm run dev
```

## 项目结构

```
backend/app/
├── main.py           FastAPI + WebSocket
├── orchestrator.py   编排Agent（思考→行动→反馈主循环）
├── tools.py          5个工具（search/design/compose/render/verify）
├── llm_client.py     DeepSeek API
├── ws_manager.py     WebSocket管理
├── web_search.py     Bing搜索
└── kb.py             33个示例话题
frontend/src/
├── App.jsx
├── components/
│   ├── DecisionLog.tsx   AI思考流程主舞台
│   ├── StoryPanel.tsx    iframe展示
│   ├── AgentBuds.tsx     工具状态灯
│   └── ...
└── hooks/useWebSocket.js
```

## GitHub

https://github.com/hfujw/ai-game-factory
