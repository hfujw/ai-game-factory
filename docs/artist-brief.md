# Artist Agent 完整设计文档

## 位置

`backend/app/agents/artist.py` — 当前 60 行占位符。需要拆成两步：`artist_pre`（设计阶段）+ `artist_post`（渲染阶段）。

## 核心理念：Artist 不是"装修队"，是"建筑设计师"

现在的流程：
```
writer → coder（毛坯房）→ reviewer → artist（刷墙）
```
问题：coder 盖的是毛坯房，artist 只能在毛坯上刷漆，改不了结构。

新流程：
```
writer → artist_pre（出设计稿）→ coder（按设计稿施工）→ reviewer → artist_post（精装修）
```
artist_pre 在 coder 开工之前，就告诉它：这个游戏的配色是什么、UI 组件长什么样、氛围怎么营造。coder 带着这些指导去写 HTML/CSS，产出的游戏天生就符合视觉规范。artist_post 只做最后的精确注入（扫描线、像素纹理、动画微调）。

## coder 的游戏逻辑（artist 需要了解）

### 5 个画面结构

每个游戏有 5 个画面（div，通过 `display:none/block` 切换）：

```html
<div id="screen-title">   <!-- 标题画面：事件名 + 悬念句 + 开始按钮 -->
<div id="screen-howto">   <!-- 操作说明：2-3句话 + 开始挑战按钮 -->
<div id="screen-game">    <!-- 游戏主体：谜题交互区 -->
<div id="screen-result">  <!-- 结果画面：胜利/失败 + 历史真相按钮 + 再来一次 -->
<div id="screen-history"> <!-- 历史故事面板 -->
```

### 三种谜题范式（coder 实现的交互）

**cipher — 符文破译台**
- 布局：中央密文大字 → A-Z 字母盘（点击填入）→ 凹槽行显示进度 → "点燃符文"按钮
- 交互：点击字母填入空槽 → 字母变暗不可再用 → 逐位检查（正确=绿，错误=红+重置）
- 反馈：每次提交后裂纹增加，3次错误自动揭示答案

**sequence — 时间碎片**
- 布局：4-6 个"碎片"卡片（轻微旋转 ±2deg）→ "重组时间线"按钮
- 交互：点击两个碎片交换位置 → 选中碎片浮起 → 提交后相邻正确之间绿线连接
- 反馈：错误碎片泛红弹回，全部正确拼成完整卷轴

**logic — 星图推演**
- 布局：中央问题核心（发光圆点）→ 线索节点（小圆点+连线）→ 3-4 个选项（菱形）
- 交互：点击线索展开 → 点击选项 → 绘制光线（SVG stroke-dashoffset）
- 反馈：错误光变红+断裂，正确光变绿，每次错误自动给 hint

### 游戏循环（tension curve）

```
尝试1：模糊提示 → 轻微裂纹
尝试2：中等提示 → 背景变暗 + 裂纹加深
尝试3：直接提示 → 可查看真相碎片
用完后：自动显示正确答案 + 历史真相
```

### 新手引导（coder 实现的）

- 第一个可交互元素自动高亮脉冲
- 关键操作旁有小字提示（字号小、灰色、不干扰）
- 第一轮不扣次数（试玩轮）
- 10 秒未操作自动浮现 hint

## Artist 的两阶段设计

### Phase 1: artist_pre（设计阶段，在 coder 之前）

**输入**：(writer 的) `script_data` + `puzzle_type`

**输出**：`visual_design` dict，写入 state，供 coder 消费

**任务**：根据剧本内容，输出一份视觉设计文档

```json
{
  "visual_design": {
    "palette": {
      "bg": "#0d0a08",
      "panel": "rgba(20,16,12,0.92)",
      "text": "#e8ddd0",
      "primary": "#e8702a",
      "success": "#34d399",
      "muted": "#5a4a3a",
      "danger": "#dc2626"
    },
    "typography": {
      "title_font": "Georgia, serif",
      "body_font": "Courier New, monospace",
      "title_size": "28px",
      "body_size": "16px"
    },
    "components": {
      "button_style": "border: 1px solid var(--primary); background: transparent; text-transform: uppercase; letter-spacing: 2px",
      "panel_style": "border: 1px solid rgba(232,112,42,0.15); border-radius: 4px; padding: 24px",
      "input_style": "background: rgba(255,255,255,0.05); border: 1px solid var(--muted); color: var(--text)",
      "card_style": "background: var(--panel); transform: rotate(-1deg); border: 1px solid var(--muted)"
    },
    "decorations": [
      "body::after CRT扫描线（2px间隔，极淡）",
      "面板四角有符文标记（▸ ◈ ◆）",
      "正确反馈：边框绿色脉冲 + scale(1.02)",
      "错误反馈：水平震动 0.3s + 红色边框",
      "通关动画：石板裂纹 → 碎片飞散 → 光芒射出"
    ],
    "mood": "古老的时间工匠工作台，烛光摇曳，纸张泛黄",
    "atmosphere_css": "body { background: radial-gradient(ellipse at 50% 30%, #1a1410, #0d0a08); }"
  }
}
```

**LLM prompt**（给 artist_pre 用的 system prompt）：

```
你是一个像素风游戏视觉设计师。你会收到一份历史游戏的剧本。

你的任务是输出一份视觉设计文档（JSON），指导程序员（coder）在写代码时用什么样的配色、字体、组件样式和装饰元素。

【设计原则】
- 暗色基调，温暖不冰冷（不是纯黑#000，是暖黑#0d0a08）
- 字体要有性格但不花哨（标题用衬线，正文用等宽）
- 按钮、面板、卡片有统一的视觉语言
- 装饰元素（符文、边角、动画）增强主题但不干扰操作
- 每种谜题类型有微妙的视觉差异（cipher=密码室感/sequence=卷轴感/logic=星空感）

【输出格式】
严格 JSON，包含 palette/typography/components/decorations/mood/atmosphere_css 六个字段。
```

### Phase 2: artist_post（渲染阶段，在 reviewer 之后）

**输入**：(coder 的) `game_code` + (artist_pre 的) `visual_design`

**输出**：`styled_code`（最终游戏代码）

**任务**：coder 按 visual_design 写了游戏，但可能漏了一些细节。artist_post 做精确注入：
- 补充/修正 CSS 变量
- 注入 CRT 扫描线、像素纹理
- 添加动画关键帧（如果 coder 漏了）
- 调整细微的间距和对齐
- 不调 LLM 是最理想的——用 CSS 注入完成所有工作

**不做什么**：
- 不改 JS 逻辑
- 不改 HTML 结构
- 不推翻 coder 的配色（那是 artist_pre 定的）

## 新 workflow 编排

```python
# workflow.py 改动
workflow.add_edge("writer", "artist_pre")     # 新增
workflow.add_edge("artist_pre", "coder")      # artist_pre → coder
workflow.add_edge("coder", "reviewer")         # 不变
workflow.add_edge("reviewer", "artist_post")   # 原来叫 artist，现在叫 artist_post
workflow.add_edge("artist_post", END)          # 不变
```

完整 pipeline：
```
crawler → planner → writer → artist_pre → coder → reviewer → artist_post → END
                              ↑ 设计稿      ↑ 按设计施工        ↑ 精装修
```

## 输入输出总结

| 阶段 | 输入 | 输出 | 消费方 |
|------|------|------|--------|
| artist_pre | writer 的 script_data | visual_design (dict) | coder |
| artist_post | coder 的 game_code + visual_design | styled_code (string) | 前端 iframe |

## 铁律

1. **JS 逻辑 100% 不能动** — artist_pre 和 artist_post 都只影响 CSS/HTML 装饰
2. **失败不阻塞** — 任何阶段挂了直接返回原代码
3. **artist_pre + coder = 设计驱动开发** — 设计师出稿，程序员按稿施工
4. **artist_post 是精确注入** — 不重写，只补漏
