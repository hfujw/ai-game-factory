# AI 游戏工坊 — 规格文档

## Problem

面试官问"你做过什么 Agent 项目"，95% 的候选人拿出一个 RAG 问答系统——上传文档、提问、LLM 回答。面试官一天看十个。没有区分度。

这个项目解决一个问题：**做一个聊天机器人做不到的东西。** 你说一个计算机历史事件，6 个 AI Agent 自己去搜史料、设计谜题机制、写代码、画像素画、审查测试，最后给你一个能玩的网页解谜游戏。这不是"AI 生成一段文字"——是"AI Agent 自主完成一个完整的软件开发流程。"

## Goals

1. **Agent 自主决策**：Agent 根据历史事件内容，自己决定谜题类型（密码破译 / 顺序排列 / 逻辑推理），不是写死的模板
2. **可展示的产物**：每次生成一个像素风 HTML 解谜游戏，能直接在浏览器里玩
3. **全流程可见**：用户看到 6 个 Agent 在实时协作，不是"黑屏等结果"
4. **失败时体面**：素材不够或事件太抽象时，Agent 能解释为什么失败并推荐替代方案
5. **JD 关键词全覆盖**：LangGraph 编排、MCP 协议、多 Agent 协作、Tool Calling、WebSocket 实时通信、React 前端

## Non-Goals

- 不追求生成"商业级游戏"——像素风小游戏，2-3 分钟内可通关
- 不支持 3D 游戏、多人联机
- 不做用户登录、历史记录持久化（MVP 不碰数据库）
- 不追求 100% 生成成功率——Agent 失败后体面解释即可

## Design Principles

1. **Agent 优先，不是 Prompt 优先**：每个 Agent 是独立模块，有明确的输入/输出契约，不是一段 prompt 的变体
2. **每一步可追溯**：Agent 的决策（"我选了解谜类型 A 因为…"）作为日志保留
3. **像素风统一视觉**：从界面到游戏画面，统一 Game Boy 时代的美学
4. **真实史料，不是 LLM 编的**：爬虫 Agent 搜到的每一段历史事实都带来源 URL

## Acceptance Scenarios

### Scenario 1: 正常生成流程
```
GIVEN 用户在搜索框输入 "1940年 Turing 破译 Enigma"
WHEN 用户点击"生成游戏"
THEN 6个Agent依次执行：
  - 策划Agent判断"这适合密码破译型谜题"
  - 爬虫Agent搜索到Enigma相关的真实史料
  - 文案Agent写出游戏剧本（背景故事+谜题规则）
  - 程序Agent生成HTML+JS+CSS代码
  - 审查Agent验证代码可运行+史实准确
  - 美术Agent应用像素风CSS主题
AND 前端实时展示每个Agent的工作状态
AND 2-3分钟后用户看到一个可玩的像素风解谜游戏
AND 游戏底部附带"历史真相"按钮，点击展示史料来源URL
```

### Scenario 2: 事件太抽象，Agent 优雅失败
```
GIVEN 用户在搜索框输入 "1983年 ACID 的诞生"
WHEN 用户点击"生成游戏"
THEN 爬虫Agent搜索后发现素材不足（只有学术定义，无人物故事）
AND 策划Agent判断"无法设计可玩的谜题机制"
AND 系统向前端推送失败通知
AND 前端展示：
  - "抱歉，这个事件暂时无法生成游戏"
  - 失败原因：缺少人物冲突和可玩机制
  - 推荐3个类似但素材更丰富的事件
```

### Scenario 3: 审查Agent发现bug，回退重做
```
GIVEN 程序Agent生成了游戏代码
WHEN 审查Agent在headless浏览器中试玩
AND 发现谜题逻辑有bug（正确答案无法输入）
THEN 审查Agent标记"不通过"
AND LangGraph状态图回退到程序Agent节点
AND 程序Agent收到审查反馈，修复bug后重新提交
AND 最多重试3次，3次都不通过则终止并返回部分成果
```

## Design

### 系统架构

```
┌─────────────────────────────────────────────────┐
│                  React 前端 (Vite)                │
│  ┌─────────┐ ┌──────────┐ ┌───────────────────┐ │
│  │ 搜索框   │ │ Agent面板 │ │ 游戏展示区         │ │
│  │(自由输入) │ │(6个头像) │ │ (生成的HTML游戏)   │ │
│  └─────────┘ └──────────┘ └───────────────────┘ │
│              ↕ WebSocket                         │
└─────────────────────────────────────────────────┘
                       ↕ WebSocket
┌─────────────────────────────────────────────────┐
│               FastAPI 后端                        │
│  ┌─────────────────────────────────────────────┐ │
│  │         LangGraph StateGraph                  │ │
│  │                                              │ │
│  │  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐     │ │
│  │  │爬虫   │→│策划   │→│文案   │→│程序   │     │ │
│  │  │Agent │ │Agent │ │Agent │ │Agent │     │ │
│  │  └──────┘  └──────┘  └──────┘  └──────┘     │ │
│  │                                    ↓         │ │
│  │                              ┌──────┐        │ │
│  │                         ←── │审查   │        │ │
│  │                        │    │Agent │        │ │
│  │                        │    └──────┘        │ │
│  │                        │        ↓            │ │
│  │                        │   审查不通过?─→回退   │ │
│  │                        │        ↓ 通过        │ │
│  │                        │    ┌──────┐         │ │
│  │                        └──→ │美术   │        │ │
│  │                             │Agent │        │ │
│  │                             └──────┘        │ │
│  └─────────────────────────────────────────────┘ │
│                                                  │
│  MCP Servers:                                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ web_search│ │code_exec │ │browser_test      │ │
│  │ (Bing API)│ │(沙箱执行) │ │(headless验证)    │ │
│  └──────────┘ └──────────┘ └──────────────────┘ │
└─────────────────────────────────────────────────┘
```

### LangGraph 状态图设计

```
State = {
    user_input: str,           # 用户输入的历史事件
    # 策划Agent输出
    puzzle_type: str | None,   # "cipher" | "sequence" | "logic"
    puzzle_design: dict | None,# 谜题机制设计
    # 爬虫Agent输出
    search_results: list | None,# [{title, url, snippet, content}]
    material_score: float,      # 素材质量评分 0-1
    # 文案Agent输出
    game_script: str | None,    # 游戏剧本（背景故事+谜题描述）
    # 程序Agent输出
    game_code: str | None,      # HTML+JS+CSS 完整代码
    # 审查Agent输出
    review_passed: bool,        # 审查是否通过
    review_feedback: str,       # 审查反馈（不通过时给程序Agent的修改建议）
    retry_count: int,           # 当前重试次数
    # 美术Agent输出
    styled_code: str | None,    # 应用像素风主题后的最终代码
    # 元数据
    status: str,                # "running" | "success" | "failed"
    error_message: str,         # 失败原因
    suggestions: list,          # 推荐替代事件
}

Nodes:
  planner_node     → analyze_event() → puzzle_type + puzzle_design
  crawler_node     → search_history() → search_results + material_score
  writer_node      → write_script() → game_script
  coder_node       → generate_code() → game_code
  reviewer_node    → review() → review_passed + review_feedback
  artist_node      → apply_style() → styled_code

Edges:
  crawler → planner → writer → coder → reviewer
  reviewer → coder (if not passed AND retry_count < 3)  # 回退重试
  reviewer → artist (if passed)
  reviewer → END (if not passed AND retry_count >= 3)   # 超过重试上限
  artist → END
```

### 6 个 Agent 的详细设计

#### 1. 爬虫 Agent (Crawler) — 第一个执行
- **输入**：用户输入的历史事件描述
- **职责**：通过 MCP web_search Server 调用 Bing API 搜索中英文史料。搜不到足够素材→流程直接终止
- **输出**：结构化史料 + 来源URL列表 + 素材质量评分 + material_sufficient 判断
- **LLM 调用**：0 次（纯 API 调用 + 结果清洗）
- **MCP Tool**：`web_search(query, lang="zh|en")`
- **早停条件**：搜索结果<3条 或 内容总字数<500 → material_sufficient=False → 流程终止

#### 2. 策划 Agent (Planner)
- **输入**：爬虫搜到的结构化史料 + 用户输入
- **职责**：基于真实史料分析事件特征 → 选择谜题类型 → 设计谜题机制。**先看史料再决定，不是凭空猜。**
- **决策逻辑**：
  - 史料中有"破译/解密/密码"内容 → cipher 型谜题
  - 史料中有清晰时间线/因果链 → sequence 型谜题
  - 史料中有冲突/博弈/选择 → logic 型谜题
- **LLM 调用**：1 次（分析史料 + 设计谜题）

#### 3. 文案 Agent (Writer)
- **输入**：爬虫搜到的史料 + 策划Agent的谜题机制
- **职责**：写游戏剧本——背景故事（300字以内）+ 谜题描述 + 通关/失败台词
- **LLM 调用**：1 次

#### 4. 程序 Agent (Coder)
- **输入**：文案的剧本 + 策划的谜题机制
- **职责**：生成完整的 HTML+JS+CSS 游戏代码。包含三个文件的内容合并在一个 HTML 中（inline CSS + inline JS）
- **输出要求**：
  - 单文件 HTML，可直接在浏览器打开
  - 像素风视觉（由美术Agent后期增强）
  - 谜题可通关（至少有一条正确的通关路径）
- **LLM 调用**：1 次（代码生成）
- **MCP Tool**：`code_exec(code, language="html")` — 在沙箱中试运行

#### 5. 审查 Agent (Reviewer)
- **输入**：游戏代码 + 游戏剧本 + 原始史料
- **职责**：三重审查
  - **代码审查**：JS 语法是否正确？HTML 结构是否完整？CSS 是否生效？
  - **历史审查**：游戏中的关键事实是否与史料一致？有没有编造？
  - **可玩性审查**：谜题是否有解？通关路径是否可达？
- **LLM 调用**：1 次（综合审查）
- **MCP Tool**：`browser_test(html_code)` — 在 headless 浏览器中载入并验证可交互性

#### 6. 美术 Agent (Artist)
- **输入**：审查通过的游戏代码
- **职责**：应用像素风 CSS 主题——配色方案、像素字体、scanline 效果、边框样式
- **LLM 调用**：1 次（CSS 增强）
- **不生成图片**：全部视觉效果由 CSS 实现

### MCP Server 设计

| MCP Server | Tool | 实现 |
|-----------|------|------|
| **web_search** | `search(query, lang)` | 调 Bing Search API v7，返回前10条结果的结构化摘要 |
| **code_exec** | `execute(code, language)` | 在隔离的 Node.js 进程中执行 JS 代码，返回执行结果或错误信息 |
| **browser_test** | `test(html_code)` | 使用 Playwright headless 模式载入 HTML，检查页面是否正常渲染、交互元素是否可点击 |

### WebSocket 通信协议

```
后端 → 前端消息格式：
{
  "type": "agent_progress",     # 消息类型
  "agent": "crawler",           # 当前Agent名称
  "status": "running",          # "running" | "done" | "failed"
  "message": "正在搜索史料...",  # 人类可读的状态描述
  "data": {}                    # 可选，Agent的输出摘要
}

type 可选值：
  - agent_progress: Agent状态更新
  - game_ready: 游戏生成完成，附带游戏代码URL
  - generation_failed: 生成失败，附带原因和建议
```

## Implementation Phases

### Phase 1: 后端骨架 (Day 1-3)
- FastAPI 项目初始化
- LangGraph StateGraph 定义（状态 + 节点 + 边）
- 3 个 MCP Server 的基础实现（web_search / code_exec / browser_test）
- 6 个 Agent 节点的 stub 实现（先用 mock 返回，验证编排逻辑正确）
- WebSocket 端点（`/ws/generate`）——用户输入 → 触发 LangGraph 运行 → 实时推送状态
- 测试：单元测试覆盖每个 Agent 节点的输入/输出契约

### Phase 2: Agent 实现 (Day 4-7)
- 爬虫 Agent：接 Bing API + 结果结构化
- 策划 Agent：DeepSeek prompt 设计 + 输出解析
- 文案 Agent：DeepSeek prompt + 剧本模板
- 程序 Agent：DeepSeek 代码生成 prompt + MCP code_exec 沙箱验证
- 审查 Agent：三重审查 prompt + MCP browser_test
- 美术 Agent：像素风 CSS 模板注入
- 测试：端到端测试——"Turing 破译 Enigma" 输入 → 完整游戏输出

### Phase 3: 前端 (Day 8-10)
- React + Vite 项目初始化
- 搜索框组件（纯自由输入）
- Agent 面板组件（6 个头像 + 状态灯 + 气泡消息）
- WebSocket 客户端（接收实时进度）
- 游戏展示区（iframe 嵌入生成的 HTML 游戏）
- 像素风 CSS 主题（全局应用）
- 失败提示组件（原因 + 推荐事件）

### Phase 4: 打磨 + 面试准备 (Day 11-12)
- 面试 Demo 脚本精调（推荐的输入事件，保证高成功率）
- 3-5 个"必成功"的历史事件测试并预调优 prompt
- README（架构图 + 技术栈 + 本地运行指南）
- GitHub 仓库整理
- 录 2 分钟 Demo 视频

## Testing Strategy

| 层 | 测什么 | 工具 |
|----|--------|------|
| 单元测试 | 每个 Agent 的输入/输出契约 | pytest |
| 集成测试 | LangGraph 编排——正常流程 + 回退重试 + 素材不足终止 | pytest + httpx |
| 端到端测试 | 模拟用户输入 → WebSocket 推送 → 最终输出游戏代码 | pytest + playwright |
| 手动测试 | 10 个不同的历史事件，人工验证游戏质量和史实准确性 | 人工 |

测试文件清单：
- `tests/test_agents.py` — 单元测试
- `tests/test_graph.py` — LangGraph 编排测试
- `tests/test_api.py` — FastAPI + WebSocket 测试
- `tests/test_mcp.py` — MCP Server 测试

## File Inventory

```
ai-game-factory/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI 入口 + WebSocket 端点
│   │   ├── graph/
│   │   │   ├── state.py             # LangGraph State 定义
│   │   │   └── workflow.py          # 节点 + 边编排
│   │   ├── agents/
│   │   │   ├── planner.py           # 策划Agent
│   │   │   ├── crawler.py           # 爬虫Agent
│   │   │   ├── writer.py            # 文案Agent
│   │   │   ├── coder.py             # 程序Agent
│   │   │   ├── reviewer.py          # 审查Agent
│   │   │   └── artist.py            # 美术Agent
│   │   ├── mcp/
│   │   │   ├── web_search.py        # MCP: Bing Search
│   │   │   ├── code_exec.py         # MCP: Code Execution
│   │   │   └── browser_test.py      # MCP: Browser Test
│   │   └── ws_manager.py            # WebSocket 连接管理
│   ├── tests/
│   │   ├── test_agents.py
│   │   ├── test_graph.py
│   │   ├── test_api.py
│   │   └── test_mcp.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx                  # 主应用
│   │   ├── components/
│   │   │   ├── SearchBar.jsx        # 搜索框
│   │   │   ├── AgentPanel.jsx       # Agent头像面板
│   │   │   ├── AgentAvatar.jsx      # 单个Agent头像+状态灯
│   │   │   ├── GameFrame.jsx        # iframe游戏展示
│   │   │   └── FailureNotice.jsx    # 失败提示+推荐
│   │   ├── hooks/
│   │   │   └── useWebSocket.js      # WebSocket hook
│   │   └── styles/
│   │       └── pixel-theme.css      # 像素风全局主题
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
└── README.md
```

## Out of Scope

- 用户登录/注册系统
- 游戏历史记录/收藏
- 数据库持久化
- AI 图片生成（全部视觉由 CSS 实现）
- 移动端适配（桌面优先）
- 多语言支持（MVP 仅中文）
- 除"解谜"之外的游戏类型（架构预留扩展点，但不实现）
