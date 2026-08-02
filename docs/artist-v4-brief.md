# Artist Agent V4 设计简报

## 上一版的错误（V3 的问题）

V3 的 `artist_pre` 是一份**死模板**（BASE_CSS + PUZZLE_OVERRIDES）。零 LLM 调用，纯字符串拼接。

问题：它不是在"设计"，是在"填空"。Coder 拿到的是固定的 CSS 文本，没有思考空间，没有选择权。这是"规定"不是"指导"。

## 用户的核心想法

> "别省那一次 LLM，让 artist_pre 读剧本，脑暴出几个设计方向，coder 选一个实施。这才是真正的设计师指导程序员。"

## V4 思路

### artist_pre（LLM 驱动的多方向设计提案）

**输入**：writer 的 script_data（结构化剧本：事件/氛围/主角/冲突/情绪/谜题类型）

**任务**：基于剧本内容，产出 **2-3 个不同的视觉设计方向**。不是 CSS 代码，是设计提案。

**输出格式**（JSON）：
```json
{
  "directions": [
    {
      "name": "方向名，如'战时密码室的烛光'",
      "mood": "一句话氛围描述",
      "palette": ["#主色", "#辅色", "#强调色"],
      "typography": "字体建议",
      "ui_style": "UI风格描述（按钮/面板/输入框长什么样）",
      "animation_style": "动画风格（沉重的/轻快的/机械的）",
      "reference_css": "一小段示例CSS，3-5行，展示核心视觉"
    },
    { "第二个方向..." },
    { "第三个方向..." }
  ],
  "designer_notes": "美术 Agent 的设计说明——为什么选这几个方向，各自适合什么类型的玩家"
}
```

**LLM prompt 骨架**：
```
你是一个像素游戏视觉设计师。你会收到一份历史游戏的剧本。
请基于剧本的 atmosphere / mood / era / puzzle_type，脑暴 2-3 个不同的视觉设计方向。

每个方向包含：name / mood / palette(3-5个色值) / typography / ui_style / animation_style / reference_css(一小段示例)

要求：
- 方向之间要有明显的风格差异（不是同一套配色的微调）
- 每种方向都要适合这个剧本的历史背景
- reference_css 只要 3-5 行，展示核心视觉语言，不是完整样式表
- 不要输出一整个 CSS 文件，这是设计提案不是施工图纸
```

### Coder（选择方向 + 实施）

**输入**：script_data + directions（2-3 个设计方向）

**任务**：
1. 阅读 2-3 个方向
2. 选择一个最合适的
3. 基于这个方向的设计语言写游戏代码

**Coder 的 system prompt 里加一段**：
```
=== 美术设计方向（从以下 2-3 个中选一个）===
{directions_text}

请选择一个最符合游戏氛围的方向，按照其视觉语言来写 HTML/CSS。
- 用该方向的 palette 中的颜色
- 按钮/面板/输入框遵循该方向的 ui_style
- 动画遵循该方向的 animation_style
- 可以自由发挥，不必逐字复制 reference_css
```

### Artist_post（精装修 + 轻量复查）

artist_post 不变——正则注入 CRT/粒子/字体 + 可选 LLM 微调。

但加一步**免费复查**（在 artist_post 之后，不调 LLM）：
- 正则检查 `<!DOCTYPE html>`、`<script>`、5 个 screen id
- 还在 → 放行
- 丢了 → 回退到 artist_post 之前的 game_code（cod 原版）

## 新 pipeline

```
writer → artist_pre(LLM, 脑暴2-3方向) → coder(选方向+施工) → reviewer → artist_post(正则+可选LLM) → light_check(正则,免费) → END
```

## 和 V3 的对比

| | V3 | V4 |
|---|-----|-----|
| artist_pre | 死模板，零 LLM | LLM 脑暴 2-3 个设计方向 |
| coder 的自主权 | 被迫按固定 CSS 写 | 从多个方向中选一个实施 |
| 设计多样性 | 每次生成的游戏视觉一样 | 每次可能选不同方向，视觉有变化 |
| LLM 调用次数 | 5 次 | 6 次（多一次 artist_pre LLM） |
| 成本 | ¥0.11 | ¥0.13 |

## 待讨论

1. 2-3 个方向够吗？会不会太多让 coder 选择困难？
2. 方向之间"明显的风格差异"怎么定义？有没有客观标准？
3. coder 选方向的逻辑——是让 LLM 自己选，还是随机选，还是基于剧本特征匹配？
