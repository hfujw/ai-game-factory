# 时光像素 — 数据全景

## 当前数据来源

### 1. 统一知识库（dual JSON files）

**位置**：
- `backend/app/knowledge/verified_events.json` — 25 个计算机历史事件
- `backend/app/knowledge/verified_bagu.json` — 8 道 Python 面试题（共 33 个示例话题）

**两种格式，统一处理**：

历史事件格式：
```json
{
  "event": "事件全名",
  "keywords": ["关键词数组"],
  "aliases": ["中文别名/俗称"],
  "facts": {
    "time": "时间", "place": "地点", "people": ["人物"],
    "story": "200-500字故事（writer 核心素材）",
    "fun_fact": "趣闻"
  },
  "atmosphere_tags": ["氛围标签"],
  "key_props": ["可视觉化道具"],
  "visual_anchor": "一句话画面描述"
}
```

Python话题格式：
```json
{
  "title": "可变对象 vs 不可变对象",
  "content": {
    "original": "代码片段",
    "translation": "代码解释",
    "annotations": ["知识点1", "知识点2"]
  },
  "difficulty": 1,
  "keywords": ["关键词"], "aliases": ["别名"],
  "atmosphere_tags": ["终端", "代码", "IDE"],
  "key_props": ["终端", "光标"],
  "visual_anchor": "画面描述"
}
```

**kb.py 的 `event_to_search_results()`** 统一将两种格式转为相同的 `search_results` 结构（`title/content/key_facts/atmosphere_tags/key_props/visual_anchor`），下游 Agent 不区分来源。

### 2. web_search（Bing → DuckDuckGo）

所有输入都会触发 web_search，补充素材。返回 `{title, snippet, url}`，标记 `verified: false`。

### 3. DeepSeek 兜底

当素材不足时，crawler 调用 DeepSeek 补充，标记 `source: "deepseek_knowledge"`。

## 用户输入 → 完整数据流

```
用户输入
  ↓
crawler: KB匹配(作为起始素材) + Bing搜索(补充素材) + LLM 6维评估(素材质量)
  ├── 素材充足 → material_sufficient=true, suggested_type=cipher/sequence/logic
  ├── 素材不足+DeepSeek补充成功 → 继续
  └── 素材彻底不足 → 失败，前端展示"素材不足，建议尝试: ..."
  ↓
planner: CoT 6步推理 → 选 puzzle_type(cipher/sequence/logic) + 设计机制
  ↓
writer: 基于素材+谜题设计 → GameScript JSON
  ↓
artist_pre: 基于剧本 → 3个视觉方向 + 自选
  ↓
orchestrator: 跨Agent一致性检查 → orchestrator_notes
  ↓
coder: 基于剧本+视觉方向+协调备注 → HTML游戏
  ↓
reviewer: 两阶段审查 → 通过/回退(最多3次)
  ↓
artist_post: BS4注入CSS → 最终游戏
```

**所有输入走完全相同流程。** KB 命中只是提供更丰富的起始素材，不改变 pipeline 逻辑。

## 33 个示例话题

**计算机历史 (25):** Turing/Enigma, Guido/Python, Cerf-Kahn/TCP, Linus/Linux, Java/Gosling, Codd/SQL, McCarthy/Lisp, Bayer/B-tree, antirez/Redis, Andreessen/Mosaic, ENIAC, ARPANET, Macintosh, Facebook, OpenAI, Google, iPhone, Transformer, Intel, GitHub, ChatGPT, GNU, Wikipedia, Winamp, Napster, Unicode, Docker

**Python (8):** 可变对象 vs 不可变对象, 深拷贝 vs 浅拷贝, 装饰器语法糖, 生成器与 yield, GIL 全局解释器锁, 上下文管理器, 描述符与 @property, 可变默认参数陷阱

## 如何扩展

在 `verified_events.json` 或 `verified_bagu.json` 中添加新条目即可。`aliases` 字段覆盖常见叫法，`keywords` 覆盖模糊匹配。`event_to_search_results()` 自动处理。
