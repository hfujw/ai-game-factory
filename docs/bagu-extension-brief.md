# 时光像素 — 八股文学习扩展 · AI 简报

## 项目一句话

用户输入事件名 → 7 个 AI Agent 协作 → 自动生成可玩的网页小游戏。

当前 27 个计算机历史事件，用户想加**八股文学习**模块——边玩边背。

## 架构速览

```
用户输入 → crawler(检索资料) → planner(选谜题类型) → writer(写剧本)
         → artist_pre(出2个视觉方向,关键词硬匹配选一个) → coder(按方向生成HTML游戏)
         → reviewer(正则检查结构+LLM审查质量) → artist_post(注入CSS+粒子)
         → 前端 iframe 渲染
```

**关键技术决策**：
- Coder 只写功能正确的黑白游戏，不管美术。视觉由 artist_pre + artist_post 注入
- 审查两阶段：正则检查程序结构(免费)，通过后才 LLM 审质量。致命错误跳过 LLM
- 前端是树园主题——横树干 + 6个Agent银色闪电芽点。但这不是重点，前端可以不管

## 当前 3 种谜题类型（给历史叙事设计的）

| 类型 | 玩法 | 适合 |
|------|------|------|
| cipher | 字母盘点击填入凹槽，逐位检查 | 密码破译事件 |
| sequence | 卡片拖拽排序，正确绿线连接 | 时间线事件 |
| logic | 线索节点展开，光线绘制选择 | 推理判断事件 |

## 要新增什么——八股文学习

用户需要**新知识库 + 新谜题类型**。知识库独立文件 `verified_bagu.json`，谜题类型新增 3 种：

### 新增谜题类型建议

| 类型 | 玩法 | 适合背什么 |
|------|------|-----------|
| fill_blank | 原文挖空，点击/输入填写 | 记关键词 |
| recite | 逐句默写，错一字闪红 | 整段背诵 |
| match | 结构名+功能描述拖拽配对 | 记八股结构 |

### 八股数据结构示例

```json
{
  "category": "bagu",
  "title": "《论语》学而篇",
  "difficulty": 1,
  "content": {
    "original": "子曰：学而时习之，不亦说乎？有朋自远方来，不亦乐乎？",
    "translation": "孔子说：学习了然后按时温习，不也是很愉快的吗？有朋友从远方来，不也是很快乐的吗？",
    "annotations": [
      "说：通'悦'，愉快",
      "朋：志同道合的人"
    ]
  },
  "atmosphere_tags": ["古典", "书卷", "清雅"],
  "key_props": ["毛笔", "砚台", "宣纸", "线装书"],
  "visual_anchor": "明窗净几的私塾里，竹简整齐排列，松烟墨香在阳光下缓缓飘散",
  "puzzle_guide": {
    "type": "fill_blank",
    "blanks": ["学而时习之，不亦____乎？"],
    "answers": ["说"],
    "hints": [{"level":1, "text":"通假字"}, {"level":2, "text":"通悦"}, {"level":3, "text":"愉快的意思"}]
  },
  "cultural_notes": ["出自《论语·学而》第一篇", "此章为孔子论学习方法之首", "科举考试中常出填空"],
  "video_url": ""
}
```

### 需要改动的文件

| 文件 | 改动 |
|------|------|
| `backend/app/knowledge/verified_bagu.json` | **新建**——八股知识库 |
| `backend/app/knowledge/kb.py` | 加 `get_bagu_events()` + 路由逻辑 |
| `backend/app/agents/planner.py` | 加 `fill_blank`/`recite`/`match` 谜题类型 |
| `backend/app/agents/coder.py` | 为新类型各写一段谜题范式（类似已有三种的交互模板） |
| `backend/app/agents/writer.py` | 加八股场景的 system prompt |
| `backend/app/agents/artist_pre.py` | `PUZZLE_OVERRIDES` 加三类微调 |
| `frontend/src/App.jsx` | 搜索框支持 "计算机历史/八股" 切换 |

### 不需要改动的

- crawler（KB 命中即免费，逻辑不变）
- reviewer（结构检查通用）
- artist_post（CSS 注入通用）
- 前端 Agent 芽点、游戏面板、决策日志（都是通用的）
- workflow 编排

## 当前成本

单次完整生成 ¥0.10-0.13（5-6 次 LLM 调用）。crawler KB 命中时免费。

## 项目 GitHub

https://github.com/hfujw/ai-game-factory

---

**你可以自由发挥的**：八股事件选什么、谜题类型叫什么名字、数据结构怎么设计、coder 的交互模板怎么写、游戏怎么让人愿意反复玩。上面只是建议。
