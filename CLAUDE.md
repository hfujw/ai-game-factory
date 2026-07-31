# AI 游戏工坊 — 项目完整上下文

> 最后更新：2026-07-31 晚
> 当前阶段：I0-I2 完成，I3-I6 待做

## 项目是什么

输入一个计算机历史事件 → 6个AI Agent协作（搜史料→定谜题→写剧本→写代码→审查→美术）→ 产出可玩的像素解谜网页游戏。

面试叙事：不是"AI生成文字"，是"AI Agent自主完成完整软件开发流程"。

## 我是谁

朱子钦，二本应届生，2026届秋招，主攻AI应用工程岗（60%）+ 后端兜底（40%）。
项目是面试作品集核心——用"聊天机器人做不到"的Agent项目脱颖而出。

## 技术栈

| 层 | 选型 | 原因 |
|----|------|------|
| Agent编排 | LangGraph StateGraph | 有分支+条件回退，不是线性Chain |
| LLM | DeepSeek API | 便宜、中文好、已有Key |
| Web框架 | FastAPI | 原生异步+WebSocket |
| 实时通信 | WebSocket | Agent每完成一步推送前端 |
| 前端 | React + Vite | 前后端分离，面试展示面大 |
| Python | venv Python 3.13 | 系统Python 3.8不兼容LangGraph |
| 包管理 | npm | Node v24可用 |

## 架构

```
React前端(localhost:5173) ←WebSocket→ FastAPI(localhost:8000) ←LangGraph→ 6 Agent
                                          ↓
                                    DeepSeek API
```

### 6 Agent Pipeline
```
crawler → planner → writer → coder → reviewer → artist
              ↑                        ↓ 不通过
              └── 回退重做(最多3次) ──┘
```

| Agent | 文件 | 职责 | LLM |
|-------|------|------|-----|
| 爬虫 | `backend/app/agents/crawler.py` | 先查本地验证知识库(10事件)→DeepSeek兜底 | 仅KB未命中时 |
| 策划 | `backend/app/agents/planner.py` | 基于史料选谜题类型(cipher/sequence/logic) | 1次 |
| 文案 | `backend/app/agents/writer.py` | 写游戏剧本(背景故事+谜题描述+台词) | 1次 |
| 程序 | `backend/app/agents/coder.py` | 生成HTML+JS+CSS游戏(四段式+历史真相按钮) | 1次 |
| 审查 | `backend/app/agents/reviewer.py` | 四维审查(体验/代码/史实/可玩)→不通过退coder | 1次 |
| 美术 | `backend/app/agents/artist.py` | 注入像素风CSS(4套主题可选) | 1次 |

### WebSocket协议
```json
{"type":"agent_progress","agent":"crawler","status":"running","message":"爬虫Agent 正在工作中…"}
{"type":"agent_log","agent":"planner","action":"designed","detail":"选择谜题类型：cipher..."}
{"type":"review_rejected","feedback":"缺少标题画面","retry":1}
{"type":"game_ready","game_code":"<!DOCTYPE html>..."}
{"type":"generation_failed","reason":"...","suggestions":["事件1","事件2"]}
```

## 目录结构

```
contract-review-agent/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI + WebSocket + CORS + /api/events
│   │   ├── ws_manager.py        # WebSocket连接管理+消息推送
│   │   ├── llm_client.py        # DeepSeek API封装(chat+chat_json)
│   │   ├── graph/
│   │   │   ├── state.py         # GameFactoryState(TypedDict)
│   │   │   └── workflow.py      # StateGraph编排+条件边
│   │   ├── agents/
│   │   │   ├── crawler.py       # 知识检索(验证KB+DeepSeek兜底)
│   │   │   ├── planner.py       # 谜题类型选择+机制设计
│   │   │   ├── writer.py        # 游戏剧本生成
│   │   │   ├── coder.py         # HTML游戏代码生成
│   │   │   ├── reviewer.py      # 四维审查(三层JSON解析)
│   │   │   └── artist.py        # 像素风CSS注入
│   │   ├── mcp/                 # MCP stub(__init__.py only)
│   │   └── knowledge/
│   │       ├── verified_events.json  # 10个验证事件+别名
│   │       └── pixel-theme.css       # 4套游戏CSS主题
│   ├── tests/                   # 空目录
│   ├── test_pipeline.py         # Pipeline手动测试脚本
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # 主布局
│   │   ├── main.jsx
│   │   ├── hooks/useWebSocket.js # WS状态管理
│   │   ├── components/
│   │   │   ├── SearchBar.jsx    # 输入框+事件chips
│   │   │   ├── AgentPanel.jsx   # 6头像网格
│   │   │   ├── AgentAvatar.jsx  # emoji头像+状态灯+气泡
│   │   │   ├── GameFrame.jsx    # iframe游戏展示
│   │   │   ├── FailureNotice.jsx # 失败提示+推荐
│   │   │   └── EventLog.jsx     # 决策轨迹面板
│   │   └── styles/pixel-theme.css # 暖终端设计系统
│   ├── vite.config.js           # proxy→localhost:8000
│   └── package.json
├── docs/
│   ├── design-system.md         # 前端设计规范(暖终端配色)
│   └── superpowers/
│       ├── brainstorms/2026-07-31-ai-game-factory-brainstorm.md
│       └── specs/2026-07-31-ai-game-factory-design.md
├── .gitignore
└── CLAUDE.md                    # 本文件
```

## 今天(7月31日)做的改动

### I0: Bug修复
1. `reviewer.py` — 修NameError(API异常时response未定义)，三层解析：chat_json → 正则兜底 → 硬门禁
2. `reviewer.py` — 终止路径补error_message+suggestions
3. `coder.py` — prompt传入search_results，要求历史真相按钮
4. `verified_events.json` — 每个事件加aliases(中文名)，如"图灵"→"Turing"
5. `main.py` — 加CORS中间件 + GET /api/events端点

### I1: React前端
- Vite+React项目，6组件+WebSocket hook+像素CSS
- 设计方向：暖终端（琥珀文字#e8d5a3 + 暖黑背景#1a1410）
- 字体：Press Start 2P(标题) + VT323(正文) + Fira Code(日志)
- 构建成功(41模块，835ms)

### I2: Agent决策可见化
- `main.py` — 推送agent_log(含planner推理理由) + review_rejected(重试循环可见)
- `ws_manager.py` — 新增send_json方法
- 前端useWebSocket处理所有5种消息类型

## 关键决策记录

1. 项目从"智能合同审查Agent"→转型"AI游戏工坊"(7/31头脑风暴)
2. MVP只做解谜游戏(cipher/sequence/logic)，以后扩展
3. 交互方式：纯自由输入，失败时Agent解释为什么+推荐事件
4. 美术：像素风CSS，不生成AI图片
5. Agent顺序：crawler→planner(必须先爬虫再策划)
6. 爬虫策略：验证知识库(10事件100%真实)→DeepSeek兜底(标unverified)
7. LLM：DeepSeek一个Key驱动全部6 Agent
8. 前端：React+Vite，前后端分离，WebSocket
9. 审查JSON解析失败→硬门禁兜底(检查script标签+doctype)

## 验证知识库10事件
Turing/Enigma, Guido/Python, Cerf-Kahn/TCP, Linus/Linux, Java/Gosling, Codd/SQL, McCarthy/Lisp, Bayer/B-tree, antirez/Redis, Andreessen/Mosaic

## 待做(I3-I6)

### I3: MCP Server (估1天)
- `app/tools/web_search.py` — DuckDuckGo(无需API key)
- `app/tools/code_exec.py` — subprocess + node --check
- `app/tools/browser_test.py` — Playwright headless
- `app/mcp/` — fastmcp注册为MCP工具(一份实现两个入口)

### I4: 游戏可玩性加固 (估1天)
- 目前reviewer太严格→Enigma 3次拒审→失败
- Coder prompt契约化(强制gameState+四段式)
- Reviewer硬门禁(正则检查必需元素)
- 3-5个演示事件prompt预调优

### I5-I6: 测试+README+Demo (估2天)
- ~20个pytest用例(全离线mock LLM)
- README(mermaid架构图+协议文档)
- 2分钟Demo脚本

## 操作命令

```bash
# 后端启动(cd到backend/)
cd backend && ../venv/Scripts/python -m uvicorn app.main:app --reload

# 前端启动(cd到frontend/)
cd frontend && npm run dev

# 跑Pipeline测试
cd backend && ../venv/Scripts/python test_pipeline.py

# 浏览器打开
http://localhost:5173
```

## 相关文件位置

| 内容 | 路径 |
|------|------|
| gstack checkpoint(7/31) | `~/.gstack/projects/contract-review-agent/checkpoints/` |
| 实施计划 | `~/.claude/plans/fancy-wandering-flurry.md` |
| 一个月冲刺计划 | `~/.claude/projects/.../memory/一个月冲刺计划-路线A.md` |
| 学习资料 | `C:\Users\22075\Desktop\一个月学习\` |
| 旧项目方案(合同审查) | `C:\Users\22075\Desktop\一个月学习\下午晚上写项目------项目方案-智能合同审查Agent.md` |
