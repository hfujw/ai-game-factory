# 时光像素 · 前端重设计简报

> 给前端 AI：这是完整的技术上下文。设计上**没有任何约束**，请你自由发挥创意。

---

## 产品是什么

用户输入一个计算机历史事件（如 "1940年 Turing 破译 Enigma 密码"），6 个 AI Agent 自动协作，生成一个可玩的像素解谜网页游戏。

面试级别的作品集项目——要让人一眼记住。

## 技术约束（不能改的）

| 项目 | 值 |
|------|-----|
| 框架 | React + Vite |
| 样式方案 | 随意（CSS/Tailwind/shadcn 都行，项目当前是纯 CSS） |
| 字体方案 | 随意（当前 Google Fonts: Inter, Press Start 2P, VT323, Fira Code） |
| 后端 | FastAPI :8000，不可变 |
| 通信 | WebSocket，协议见下方 |
| 游戏展示 | iframe srcdoc 渲染后端返回的 HTML 字符串 |
| 浏览器 | 桌面端为主，移动端兼容即可 |

## 数据流

```
用户输入事件名
    ↓
WebSocket 连接 ws://localhost:8000/ws/generate
    ↓
后端推送 5 种消息（实时）
    ↓
最终收到 game_code → 放入 iframe srcdoc
```

## WebSocket 协议

**连接**：`ws://localhost:8000/ws/generate`

**客户端发送**：
```json
{ "event": "1940年 Turing 破译德军 Enigma 密码" }
```

**服务端推送 5 种消息类型**：

```json
// 1. Agent 进度 — 每个 Agent 状态变化时推送
{
  "type": "agent_progress",
  "agent": "crawler",        // crawler|planner|writer|coder|reviewer|artist
  "status": "running",       // running|done
  "message": "爬虫Agent 正在工作中…"
}

// 2. Agent 决策日志 — Agent 的推理过程
{
  "type": "agent_log",
  "agent": "planner",
  "action": "designed",       // verified|retrieved_unverified|designed|script_written|code_generated|pass|reject|style_applied|error
  "detail": "选择谜题类型：cipher。理由：该事件核心是密码破译..."
}

// 3. 审查拒绝 — reviewer 不通过，coder 重试
{
  "type": "review_rejected",
  "feedback": "缺少标题画面和操作说明...",
  "retry": 1                 // 第几次重试（最多3次）
}

// 4. 生成成功 — 游戏代码就绪
{
  "type": "game_ready",
  "game_code": "<!DOCTYPE html><html>...</html>"
}

// 5. 生成失败 — 3次重试后仍然不通过
{
  "type": "generation_failed",
  "reason": "游戏代码经过 3 次审查和修改仍未通过",
  "suggestions": ["1940年 Turing...", "1989年圣诞节 Guido..."]
}
```

## REST API

```
GET /api/events
→ { "events": [{ "name": "1940年 Turing 破译德军 Enigma 密码" }, ...], "total": 10 }

GET /api/health
→ { "status": "ok" }

GET /api/cost
→ { "calls": 5, "total_input_tokens": 8906, "estimated_cost_rmb": 0.11 }
```

## 前端状态管理

只需管理 5 个状态：

```js
statuses:     { crawler: {status, message}, planner: {...}, ... }  // 6个Agent实时状态
messages:     [{id, time, agent, detail}, ...]                     // 决策轨迹日志
gameCode:     "<!DOCTYPE html>..." | null                          // 游戏HTML
error:        {reason, suggestions} | null                        // 失败信息
isGenerating: boolean                                              // 是否生成中
cancel:       () => void                                           // 中断生成
```

## 6 个 Agent 信息

| key | 中文名 | 职责 | 执行顺序 |
|-----|--------|------|:--:|
| crawler | 爬虫 | 查史料（本地知识库命中→免费；未命中→DeepSeek兜底） | 1 |
| planner | 策划 | 分析史料，选择谜题类型（cipher密码破译 / sequence顺序排列 / logic逻辑推理） | 2 |
| writer | 文案 | 写游戏剧本（背景故事 + 谜题描述 + 通关/失败台词） | 3 |
| coder | 程序 | 按 13 条契约生成完整 HTML 游戏代码 | 4 |
| reviewer | 审查 | 两阶段检查（正则验证结构 + LLM 审查质量），不通过退回 coder | 5 |
| artist | 美术 | 注入像素风 CSS 主题，不改 JS 逻辑 | 6 |

特殊逻辑：reviewer 不通过 → coder 重试（最多3次）→ 3次都不通过 → 整体失败

## 项目当前文件

```
frontend/
├── index.html
├── package.json
├── vite.config.js
├── public/
│   ├── bg.mp4          # 视频背景 (218MB)
│   ├── favicon.svg
│   └── icons.svg
└── src/
    ├── main.jsx
    ├── App.jsx
    ├── hooks/
    │   └── useWebSocket.js   # WS 连接 + 状态管理 hook
    ├── components/
    │   ├── SearchBar.jsx      # 搜索框 + 事件推荐 chips
    │   ├── AgentPanel.jsx     # 6 Agent 流水线面板
    │   ├── GameFrame.jsx      # iframe 游戏展示
    │   ├── EventLog.jsx       # 决策轨迹日志
    │   ├── FailureNotice.jsx  # 失败提示 + 推荐重试
    │   └── ErrorBoundary.jsx  # 崩溃兜底
    └── styles/
        └── pixel-theme.css    # 当前样式（液态玻璃主题，可全部替换）
```

---

## 创意方向（仅供参考，不要被限制）

以下是一些发散方向，但你**完全可以跳出这些**：

- **剧场/舞台**：Agent 是演员，游戏是演出。舞台灯光、幕布、报幕效果
- **实验室/工坊**：Agent 在工作台上忙碌，游戏从传送带输出
- **太空/星舰**：Agent 是指挥舱的船员，探索历史星云
- **故事书/卷轴**：历史事件展开成卷轴，游戏从书页中浮现
- **电路板/数据流**：Agent 是芯片，数据在电路间流动
- **画廊/展馆**：每次生成 = 一幅作品，挂在虚拟展厅里
- **终端/命令行**：极简黑客风，所有交互用命令行完成
- **极简白/苹果风**：大留白，精致的微交互，内容为王
- **赛博朋克/霓虹**：暗底 + 霓虹灯效 + 故障艺术
- **手绘/涂鸦**：纸张质感，手写字体，温暖的"未完成感"

## 要避免的

- 不要 emoji 当图标（用 SVG）
- 不要死板的表格排布
- 不要让 Agent 状态挤成一团
- 不要让用户猜 "现在发生了什么"

---

**去吧，做点让人眼前一亮的东西。**
