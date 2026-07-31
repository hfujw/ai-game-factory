---
Date Started: 2026-07-31
Status: In Progress
Current Phase: alignment
Last Updated: 2026-07-31
Based On: none
---

# AI 游戏工坊 — 头脑风暴决策记录

### Q1: 游戏范围 — 固定类型 vs 多类型匹配
**Options Presented:** A) 固定一个游戏类型 B) 多种小游戏类型，Agent自动为每个历史事件匹配玩法 C) 用户自己想法
**Decision:** B — 多类型匹配
**Rationale:** "Agent不是在执行固定流水线，而是自己做了一个设计决策——这个故事适合做成解谜游戏。这就是字节JD里说的Agent自主决策能力。"
**Timestamp:** 2026-07-31

### Q3: 游戏玩法类型
**Options Presented:** 收集+躲避 / 解谜 / 连线管道 / 问答闯关，选3-4个
**Decision:** MVP 只做解谜——以后再加其他
**Rationale:** "先做深一个类型。解谜和'破译/发现'类历史事件天然契合，智力感强。面试官看到的不只是一个游戏模板换皮——同一个解谜框架能适配完全不同的历史故事。"
**Timestamp:** 2026-07-31

---

### Q2: 交互方式 — 预设事件库 vs 自由输入
**Options Presented:** A) 预设事件库 B) 自由输入+预设兜底 C) 纯自由输入
**Decision:** C — 纯自由输入
**Rationale:** "成功时最震撼，失败时也体面——Agent知道自己做不到，还能解释为什么。Agent的自主决策不只包括选对的方案，也包括判断自己做不了。"
**Timestamp:** 2026-07-31

---

### Q4: 生成过程展示
**Options Presented:** A) 实时日志流 B) 进度条+Agent头像 C) 纯等待动画
**Decision:** B — 进度条+Agent头像
**Rationale:** "更像产品，视觉化。6个Agent头像排列，当前干活的亮起来+气泡显示思考内容。"

### Q5: 美术/画面风格
**Options Presented:** A) 像素风+CSS B) 极简文字+排版 C) Emoji+几何图形
**Decision:** A — 像素风+CSS
**Rationale:** "Game Boy风格。和'计算机历史'主题天然契合——在玩计算机的童年。纯CSS代码生成，零外部依赖。"

### Q6: Agent 阵容确认
**Decision:** 6 个 Agent，测试 Agent 职责合并到审查 Agent
**Agent 清单:** 策划(设计谜题机制) / 爬虫(搜索真实史料) / 文案(写游戏剧本) / 程序(生成HTML+JS+CSS) / 审查(查bug+验证史实+试玩) / 美术(像素风CSS配色+动画)

### Q7: 搜索API
**Options Presented:** A) Bing Search API B) DuckDuckGo C) Google+代理
**Decision:** A — Bing Search API
**Rationale:** "微软的，每月1000次免费，中文搜索好。MCP工具写'web_search MCP Server调Bing API'——面试官知道这是正经企业方案。"

### Q8 & Q9: LLM + 前端
**LLM Decision:** DeepSeek API — 用户已有经验，便宜，中文好，代码生成够用
**Frontend Decision:** React + Vite — 前后端分离。字节/美团JD里前端部分常提React，技术栈直接对上了。WebSocket做实时通信，Agent每完成一步推送给前端
**Rationale:** "前后端分离，上限更高。前端做成像素风复古控制台——6个Agent头像、打字机效果、绿灯咔嗒声。面试官看到的不只是功能，是一个完整的艺术品。"

---

### Phase A → B Transition Confirmation [2026-07-31]
**Alignment Summary:**
- Q1+Q3: MVP只做解谜游戏，一个历史事件生成一个像素风谜题。以后扩展更多游戏类型
- Q2: 纯自由输入——面试官随便打字。Agent失败时能解释为什么，推荐预设事件
- Q4: 6个Agent头像+进度条+WebSocket实时推送进度
- Q5: 像素风CSS——Game Boy复古风格，纯代码生成零外部依赖
- Q6: 6个Agent(策划/爬虫/文案/程序/审查/美术)，审查Agent兼任测试
- Q7: Bing Search API → MCP web_search Server
- Q8: DeepSeek API → LLM推理
- Q9+10: React+Vite前端 ←WebSocket→ FastAPI后端 ←LangGraph→ 6 Agent Pipeline

**User Confirmation:** ✓ Confirmed

### Phase B: Spec Writing
**Initial draft:** `docs/superpowers/specs/2026-07-31-ai-game-factory-design.md`
**Status:** Draft complete, pending user review

---

## Original User Request

用户说"我想玩一个XX游戏"，6个AI Agent协作（策划Agent做玩法设计→文案Agent写世界观→程序Agent写代码→审查Agent检查bug→测试Agent试玩→美术Agent生成素材），最终产出一个能玩的网页小游戏。技术栈：LangGraph编排 + MCP协议 + FastAPI + 多Agent协作。这是为了秋招AI应用工程岗做的项目，需要体现LangGraph、MCP、多Agent、Tool Calling等JD高频关键词。
