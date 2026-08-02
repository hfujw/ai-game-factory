# 时光像素 — 项目全景（给设计 AI）

## 产品一句话

用户输入计算机历史事件 → 7 个 AI Agent 协作 → 自动生成可玩的像素解谜网页游戏。

面试作品集项目。不是"AI 写文字"，是"AI Agent 自主完成完整软件开发流程"。

## 7 Agent Pipeline（当前状态）

```
crawler → planner → writer → artist_pre → coder → reviewer → artist_post → END
  KB+LLM    LLM       LLM      LLM         LLM      LLM       正则+可选LLM
```

| Agent | 职责 | 完成度 |
|-------|------|:--:|
| 🔍 crawler | 查史料（10事件KB命中→免费；未命中→DeepSeek兜底） | ✅ |
| 🎯 planner | 选谜题类型（cipher密码破译/sequence时间排序/logic逻辑推理） | ✅ |
| ✍️ writer | 输出结构化GameScript JSON（事件/主角/冲突/提示/故事/视觉情绪） | ✅ |
| 🎨 artist_pre | **正在讨论**——在coder之前出视觉设计方向 | 🔴 待定稿 |
| 💻 coder | 按剧本+设计方向生成完整HTML游戏（5画面+谜题交互+新手引导） | ✅ |
| 🔎 reviewer | 两阶段：Phase1正则(5条结构检查,免费) + Phase2 LLM(4维度质量审查) | ✅ |
| 🎨 artist_post | 正则注入(CRT/字体/粒子/transition) + 可选LLM微调(只处理CSS文本) | ✅ |

## 当前架构亮点

1. **Coder-Reviewer 契约驱动**：coder 必须按 5 画面结构 + classList.toggle('active') 写游戏。reviewer 用正则机械检查（不浪费 LLM），通过后才 LLM 审查质量
2. **Writer 输出结构化 JSON**：不是散文，是 `{event, protagonist, puzzle:{type,surface,answer,hints}, history_facts:{title,story,key_point,fun_fact}, visual:{palette,mood,decorations}}`。下游 Agent 按字段消费
3. **Artist_post 两步走**：正则注入（零风险，必须成功）+ LLM 只处理 CSS 文本追加（可选，挂了不影响）——"装坏了回退到 coder 原版"
4. **Reviewer 务实审查**：4 维度（能跑/能通关/历史对/流程完整），不是"好不好看"

## 当前架构短板

1. **Artist_pre 还没定稿**——目前是死模板（BASE_CSS + PUZZLE_OVERRIDES），零 LLM，没有设计灵魂。正在 V4 讨论中
2. **Coder 产出的游戏质量不稳定**——同样的 prompt，有的游戏好玩有引导，有的粗糙难懂。LLM 的随机性
3. **没有 MCP 工具**——Agent 不能搜网页、不能运行代码、不能截图验证
4. **没有自动化测试**——pytest 在 requirements.txt 但 tests/ 是空目录

## Coder 的游戏结构（artist_pre 需要理解）

每个游戏 5 个画面：
```
#screen-title  → 事件名 + 悬念句 + 开始按钮
#screen-howto  → 操作说明 + 开始挑战按钮
#screen-game   → 谜题交互区（按 puzzle_type 实现不同范式）
#screen-result → 胜利/失败 + 历史真相按钮 + 再来一次
#screen-history→ 历史故事面板（writer 产出的 story 小故事）
```

3 种谜题范式（coder 在 system prompt 里有详细交互模板）：
- **cipher**：符文破译台——字母盘点击填入凹槽，逐位高亮检查
- **sequence**：时间碎片——卡片拖拽排序，邻位正确绿线连接
- **logic**：星图推演——线索节点展开，SVG 光线绘制选项

游戏循环有张力曲线：裂纹递增 + 背景渐暗 + 3 层提示逐级浮现。新手引导有：首个元素高亮脉冲 + 小字操作提示 + 第一轮不扣次数。

## 前端（独立于 Agent 讨论）

React + Vite + Tailwind CSS + framer-motion。树园主题：横树干 + 6 个 Agent 芽点（休眠→银白脉动→SVG 银色闪电）+ 光标聚光灯 RevealLayer + 液态玻璃游戏面板。WebSocket 实时推送 Agent 进度。

## Writer 输出的 GameScript 结构（关键——artist_pre 的输入）

```json
{
  "event": "1940年 Turing 破译德军 Enigma 密码",
  "year": 1940,
  "location": "布莱切利园，英国",
  "protagonist": "Alan Turing",
  "antagonist": "Enigma 密码机",
  "core_conflict": "如何在有限时间内破译每日更换的密码",
  "atmosphere": "紧张的战时密码室，打字机声，纸张燃烧的味道",
  "opening_hook": "一封纳粹密电刚刚被截获。桌上的电报机还在滴答作响。",

  "puzzle": {
    "type": "cipher",
    "surface": "一封截获的德军密电",
    "answer": "ATTACK AT DAWN",
    "hints": [
      {"level":1, "text":"密电使用了当日的Enigma密钥..."},
      {"level":2, "text":"注意重复出现的字母模式..."},
      {"level":3, "text":"Turing发现某些固定格式的开头..."}
    ],
    "max_attempts": 3
  },

  "history_facts": {
    "title": "一台机器如何改变战争走向",
    "story": "1940年，Alan Turing 加入布莱切利园的密码破译团队...(200-300字口语化故事)",
    "key_point": "Bombe 机器的发明让盟军提前2年结束战争",
    "fun_fact": "Turing 的破译方法至今仍影响着现代密码学"
  },

  "victory_line": "密码破译成功！盟军得以拦截德军补给线。",
  "defeat_line": "时间耗尽。但历史记住了每一个尝试。",

  "visual": {
    "palette": ["#0d0a08", "#e8702a", "#34d399", "#e8ddd0", "#5a4a3a"],
    "mood": "紧张的战时密码室，烛光摇曳，纸张泛黄",
    "decorations": ["打字机电报声", "烧焦的纸片边缘", "蜡封印章"]
  }
}
```

## 成本

单次完整生成约 ¥0.11-0.13（5-6 次 LLM 调用）。crawler 走 KB 命中时免费。

## GitHub

https://github.com/hfujw/ai-game-factory
