# ============================================================
# DEBUGGER_TEMPLATE
# ============================================================
DEBUGGER_TEMPLATE = """
你正在为一个 Python 面试学习游戏生成 HTML/CSS/JS 代码。

【游戏类型】debugger（Bug 定位）
【核心机制】给一段有 bug 的 Python 代码 + 控制台报错信息，玩家先点击可疑行号定位 bug，再选择 bug 类型。两步都正确才算通关。

【必须包含的交互元素】
1. 代码展示区：
   - 带行号的代码编辑器样式，左侧行号可点击
   - 语法高亮（关键字蓝、字符串绿、注释灰、数字橙）
   - 点击行号后该行高亮（蓝色边框），可多选但提示"通常只有一处"

2. 控制台面板：
   - 显示报错信息（Traceback 样式），红色文字
   - 报错信息从 window.__PUZZLE_DATA__.bug_info.traceback 读取

3. Bug 类型选择区：
   - 点击行号后弹出/展开选项卡
   - 选项从 window.__PUZZLE_DATA__.bug_info.options 读取
   - 选项包含：缩进错误 / 可变默认参数 / 浅拷贝陷阱 / 异常捕获不当 / 类型错误 / 逻辑错误 等

4. 两步验证逻辑：
   Step 1: 玩家点击行号 → 该行高亮，记录 selected_line
   Step 2: 玩家选择 bug 类型 → 记录 selected_type
   Step 3: 点击"提交调试"

   结果判定：
   - 行号正确 + 类型正确 → 该行绿色高亮，显示修复后代码，播放"修复成功"动画，得分
   - 行号正确 + 类型错误 → 黄色提示"行号找对了，再想想是什么类型的问题"，不扣分
   - 行号错误 → 红色提示"这行代码没问题，请重新定位"，该行红色闪烁

5. 修复展示：
   - 通关后，原代码和修复代码并排对比（diff 样式）
   - 修复行高亮显示
   - 显示解释：为什么这是 bug，正确做法是什么

6. 提示系统：
   - Level 1: "注意看报错信息里的行号提示"
   - Level 2: "这个 bug 和可变对象有关"
   - Level 3: "正确的修复方式是把默认参数改为 None"

7. 进度与得分：
   - 首次定位正确 +50 分
   - 类型选择正确 +50 分
   - 使用提示每次 -10 分
   - 错误尝试每次 -5 分

【视觉风格】
- 背景：深色终端 #0d1117
- 代码区：VS Code 风格，行号灰色，选中行蓝色边框
- 正确行：绿色背景 + 对勾图标
- 错误行：红色闪烁 + 叉号图标
- 控制台：等宽字体，红色报错文字
- 修复对比：左侧红色删除线（原代码），右侧绿色新增（修复代码）
- 完成动画：bug 图标碎裂，变成绿色对勾

【代码结构要求】
- 使用原生 HTML/CSS/JS，不依赖外部库
- 所有样式内联或写在 <style> 中
- 游戏数据从 window.__PUZZLE_DATA__ 读取
- 提供 initGame(data) 入口函数
- data.bug_info 结构：
  {
    "bug_line": 3,                    // bug 所在行号（从1开始）
    "bug_type": "mutable_default",    // bug 类型标识
    "traceback": "Traceback (most recent call last):\n  ...",  // 报错信息
    "options": [                      // 可选的 bug 类型
      {"id": "mutable_default", "label": "可变默认参数陷阱"},
      {"id": "indent_error", "label": "缩进错误"},
      {"id": "shallow_copy", "label": "浅拷贝陷阱"},
      {"id": "type_error", "label": "类型错误"},
      {"id": "logic_error", "label": "逻辑错误"}
    ],
    "fix_code": "def append_item(item, lst=None):\n    if lst is None:\n        lst = []\n    lst.append(item)\n    return lst",  // 修复后代码
    "explanation": "Python 的默认参数在函数定义时求值，且只创建一次。使用可变对象（如列表）作为默认参数会导致所有调用共享同一个列表。正确做法是用 None 作为默认值，在函数体内创建新列表。"
  }

【校验逻辑】
- 前端 JS 校验，不执行代码
- 比对 selected_line === bug_line && selected_type === bug_type
"""

# ============================================================
# MATCH_TEMPLATE
# ============================================================
MATCH_TEMPLATE = """
你正在为一个 Python 面试学习游戏生成 HTML/CSS/JS 代码。

【游戏类型】match（概念配对）
【核心机制】左侧为 Python 概念/代码片段，右侧为机制描述。玩家通过拖拽或点击将左右配对。配对正确显示绿色连线，错误显示红色并短暂抖动。

【必须包含的交互元素】
1. 左右两栏：
   - 左栏：概念/代码片段卡片（如 "copy.deepcopy()"、"GIL"、"@property"）
   - 右栏：机制描述卡片（如 "递归复制所有嵌套对象"）
   - 卡片从 window.__PUZZLE_DATA__.puzzle_guide.match_pairs 读取

2. 连线绘制：
   - 使用 SVG 绘制玩家选择的连线
   - 点击左栏卡片 → 再点击右栏卡片 → 绘制连线
   - 支持拖拽连线（可选，点击配对为保底方案）

3. 配对校验：
   - 正确 → 绿色实线 + 两端卡片绿色高亮 + 锁定（不可再操作）
   - 错误 → 红色虚线 + 两端卡片抖动 0.5s 后消失

4. 知识卡片：
   - 配对正确后，点击该对可查看详细解释
   - 显示：概念定义 + 代码示例 + 面试话术

5. 完成统计：
   - 显示配对正确率、用时、连击奖励
   - 全部完成后显示"知识网络已建立"动画

6. 重置按钮：可清空所有连线重新开始

【视觉风格】
- 背景：深色终端 #0d1117
- 左栏卡片：黑色边框，概念名用荧光绿 #7ee787
- 右栏卡片：米白色描述，黑色文字
- 正确连线：荧光绿实线，带箭头
- 错误连线：红色虚线
- 完成效果：所有连线如电路板般点亮，显示"知识网络已建立"

【代码结构要求】
- 使用原生 HTML/CSS/JS，不依赖外部库
- 所有样式内联或写在 <style> 中
- 游戏数据从 window.__PUZZLE_DATA__ 读取
- 提供 initGame(data) 入口函数
- data.puzzle_guide.match_pairs 结构：
  [
    {"left": "copy.deepcopy()", "right": "递归复制所有嵌套对象，完全独立"},
    {"left": "GIL", "right": "全局解释器锁，限制多线程 CPU 并行"},
    {"left": "@property", "right": "将方法转换为属性访问，实现描述符协议"},
    {"left": "__slots__", "right": "限制实例属性，节省内存，禁止 __dict__"}
  ]
"""

# ============================================================
# FILL_BLANK_TEMPLATE
# ============================================================
FILL_BLANK_TEMPLATE = """
你正在为一个 Python 面试学习游戏生成 HTML/CSS/JS 代码。

【游戏类型】fill_blank（代码填空）
【核心机制】给一段有 ___ 的 Python 代码，玩家点击空位输入关键字/API/参数。填对变绿，填错变红并显示模拟报错信息。

【必须包含的交互元素】
1. 代码展示区：
   - 带行号的代码编辑器样式
   - 语法高亮（关键字蓝 #58a6ff、字符串绿 #7ee787、注释灰 #8b949e、数字橙 #d2a8ff）
   - 空位用闪烁的下划线 ___ 表示（animation: blink 1s step-end infinite）
   - 点击空位弹出小输入框（overlay 在空位上方）

2. 输入与校验：
   - 输入框自动聚焦，支持 Enter 提交
   - 校验逻辑：比对玩家输入和正确答案（不区分大小写、忽略首尾空格）
   - 答案从 window.__PUZZLE_DATA__.blanks[i].answer 读取

3. 三层反馈：
   - 填错 → 空位变红 + 显示模拟 Python 报错（从 expected_output.error 读取）
   - 填对但非最优 → 空位变黄 + 显示 warning 提示（从 expected_output.warning 读取）
   - 填对且最优 → 空位变绿 + 右侧"终端"显示 success 输出（从 expected_output.success 读取）

4. 终端面板：
   - 等宽字体，深色背景 #0d1117
   - 正确时显示 >>> Success + 输出结果 + 时间复杂度
   - 错误时显示红色 Traceback 样式报错

5. 提示系统：3 层 hint，使用一次扣分

6. 得分：base_score + hint_penalty + time_bonus

【视觉风格】
- 背景 #0d1117，代码区类似 VS Code 暗色主题
- 语法高亮：关键字蓝 / 字符串绿 / 注释灰 / 数字橙
- 正确反馈：绿色高亮 + ✓ 图标
- 错误反馈：红色下划线 + ✗ 图标 + 模拟报错
- 完成动画：代码逐行变绿，终端输出 'Process finished with exit code 0'

【代码结构要求】
- 原生 HTML/CSS/JS，不依赖外部库
- 数据从 window.__PUZZLE_DATA__ 读取
- 提供 initGame(data) 入口函数
- data.blanks 结构：[{"code": "def ___(self):", "answer": "__enter__", "position": "方法名"}, ...]
- data.expected_output: {error, warning, success}
"""

# ============================================================
# RECITE_TEMPLATE
# ============================================================
RECITE_TEMPLATE = """
你正在为一个 Python 面试学习游戏生成 HTML/CSS/JS 代码。

【游戏类型】recite（代码默写 — 剥洋葱式）
【核心机制】根据需求描述，在"伪 IDE"里写出完整代码片段。默认 L1（70% 骨架），可挑战 L2（30%）和 L3（裸写）。

【骨架自动生成规则】
你必须在前端 JS 中实现自动抽空逻辑：
1. 读取 data.content.original 完整代码
2. 读取 data.puzzle_guide.recite_config.preserve_keywords（保留关键字列表）
3. 读取 data.puzzle_guide.recite_config.preserve_builtins（保留内置函数）
4. 保留所有 Python 关键字（def/for/in/yield/return/class/if/else/with/as...）
5. 保留所有内置函数名（print/range/len/next/iter/open...）
6. 抽空用户自定义名（函数名/变量名/参数名）→ ___
7. L1 保留 70%（只抽空自定义名）、L2 保留 30%（抽空自定义名 + 部分关键字）、L3 裸写

【必须包含的交互元素】
1. 需求区：顶部显示题目描述 + 函数签名提示
2. 伪 IDE：
   - 行号（灰色）+ 代码行
   - 空白行显示闪烁光标
   - 保留行显示语法高亮的代码
   - 支持键盘输入，Tab 缩进，Enter 换行

3. 实时校验（每行 Enter 后）：
   - 使用正则结构模式校验：
     - def\\s+\\w+\\s*\\([^)]*\\): 检查函数定义
     - for\\s+\\w+\\s+in 检查 for 循环
     - with\\s+.*\\s+as 检查 with 语句
     - yield\\s+ 检查 yield 关键字
     - @\\w+ 检查装饰器
   - 关键字检测：必须包含 recite_config.preserve_keywords 中所有关键字
   - 正确：行号变绿 + >>> 模拟输出
   - 错误：行号变红 + 显示 SyntaxError 或逻辑提示

4. 难度切换：L1/L2/L3 按钮，切换时自动调整骨架保留比例

5. 得分：base_score + per_error_penalty + segment_bonus + perfect_bonus

【视觉风格】同 fill_blank — 深色终端 #0d1117 + VS Code 语法高亮

【代码结构要求】
- 数据从 window.__PUZZLE_DATA__ 读取
- data.recite_config: {preserve_keywords, preserve_builtins, strip_pattern}
- data.content.original: 完整代码
- 前端 JS 自动生成骨架，不由后端预存
"""
