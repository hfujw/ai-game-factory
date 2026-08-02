# 时光像素 — 数据全景

## 当前数据来源

### 1. 本地知识库（verified_events.json）

**位置**：`backend/app/knowledge/verified_events.json`

**结构**：每个事件包含
```json
{
  "event": "事件全名",
  "keywords": ["关键词数组，用于匹配用户输入"],
  "aliases": ["中文别名/俗称/拼写变体，用于模糊匹配"],
  "facts": {
    "time": "时间",
    "place": "地点",
    "people": ["人物数组"],
    "story": "200-500字故事（writer 的核心素材）",
    "fun_fact": "趣闻"
  }
}
```

**10 个事件**：
| # | 事件 | 类型 |
|---|------|------|
| 1 | 1940年 Turing 破译德军 Enigma 密码 | cipher |
| 2 | 1989年圣诞节 Guido 发明了 Python | sequence |
| 3 | 1974年 Cerf 和 Kahn 画出 TCP 草图 | logic |
| 4 | 1991年 Linus 写下了 Linux 的第一行代码 | sequence |
| 5 | 1995年 Java 的诞生 | sequence |
| 6 | 1970年 Codd 发表关系型数据库论文 | logic |
| 7 | 1958年 McCarthy 发明 Lisp | logic |
| 8 | 1971年 Bayer 发明 B树 | logic |
| 9 | 2009年 antirez 在意大利写 Redis | sequence |
| 10 | 1993年 Andreessen 发布 Mosaic 浏览器 | sequence |

### 2. DeepSeek 兜底（crawler 的 Plan B）

当用户输入的事件不在本地 KB 中时，crawler 调用 DeepSeek 做知识检索。返回的结果结构和 KB 一致（`title/content/key_facts`），但标记 `verified: false`。

### 3. 用户输入 → 匹配流程

```
用户输入
  ↓
crawler: 关键词+别名在 KB 中匹配
  ├── 命中 → verified=true, material_score=1.0, 免费
  └── 未命中 → DeepSeek兜底 → verified=false, material_score≤0.85, 花一次LLM
  ↓
planner: 基于史料内容选 puzzle_type
  ↓
writer: 基于史料写 GameScript JSON
```

## 数据流向

```
verified_events.json ──→ crawler ──→ search_results ──→ planner ──→ puzzle_type
                                                          │
                                                          ├──→ writer ──→ game_script (JSON)
                                                          │                    │
                                                          │                    ├──→ artist_pre (视觉方向)
                                                          │                    ├──→ coder (游戏代码)
                                                          │                    └──→ reviewer (历史审查)
                                                          │
                                                          └──→ [前端]: 推荐事件 chips
```

## 如何扩展知识库

### 添加新的计算机历史事件

在 `verified_events.json` 数组中添加一条新记录：
```json
{
  "event": "事件全名（用于匹配和展示）",
  "keywords": ["英文名", "核心技术词"],
  "aliases": ["中文俗称1", "中文俗称2"],
  "facts": {
    "time": "具体时间",
    "place": "地点",
    "people": ["人物1", "人物2"],
    "story": "200-500字的叙述性故事。要口语化、有画面感。writer 会基于这个故事写剧本。",
    "fun_fact": "一条有趣的冷知识"
  }
}
```

**关键**：`aliases` 字段决定了用户输入能否匹配到这个事件。尽量覆盖常见叫法。

### 新增领域：中国历史 / 八股学习

如果需要扩展到中国历史或八股文学习，有两种方案：

**方案 A：扩展现有 KB**
- 直接在 `verified_events.json` 里加中国历史事件
- 加新的事件类型标签（如 `category: "chinese_history"` 或 `category: "bagu_learning"`）
- 前端加分类筛选

**方案 B：独立知识库**
- 新建 `verified_chinese_history.json`
- `verified_bagu.json`
- crawler 根据用户输入的关键词自动路由到不同 KB
- 不同领域可以有不同的谜题类型（如八股学习可以加 `recite` 背诵型、`fill_blank` 填空型）

**需要新增的数据字段（建议）**：
```json
{
  "category": "computer_history | chinese_history | bagu",
  "era": "1940s | 明朝 | 春秋",
  "difficulty": 1-3,
  "related_events": ["关联的其他事件名"],
  "learning_points": ["知识点1", "知识点2"]
}
```

## Writer 产出的 GameScript 结构

这是 artist_pre 和 coder 消费的核心数据：

```json
{
  "event": "事件名",
  "year": 年份,
  "location": "地点",
  "protagonist": "主角",
  "antagonist": "对抗方",
  "core_conflict": "核心冲突",
  "atmosphere": "氛围描述",
  "opening_hook": "开场悬念句",

  "puzzle": {
    "type": "cipher|sequence|logic",
    "surface": "谜题表皮描述",
    "answer": "正确答案",
    "items_count": 元素数量,
    "items_labels": ["标签"],
    "hints": [{"level":1,"text":"..."}, {"level":2,"text":"..."}, {"level":3,"text":"..."}],
    "max_attempts": 3
  },

  "history_facts": {
    "title": "小故事标题",
    "story": "200-300字口语化故事",
    "key_point": "一句话核心收获",
    "fun_fact": "趣闻"
  },

  "victory_line": "通关台词",
  "defeat_line": "失败台词",

  "visual": {
    "palette": ["#色1","#色2","#色3","#色4","#色5"],
    "mood": "视觉情绪",
    "decorations": ["装饰1","装饰2"]
  }
}
```
