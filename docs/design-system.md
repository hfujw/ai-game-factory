# AI 游戏工坊 — 前端设计系统

## 设计方向：温暖的复古终端

不是冷峻的霓虹赛博朋克，也不是单调的黑底绿字CRT。
是**70年代计算机实验室**的感觉——暖调的暗色背景、琥珀色文字、
木质感边框、模拟电路的指示灯。像一个老工程师的工作台。

## 配色方案

| Token | Hex | 用途 |
|--------|-----|------|
| `--bg-app` | `#1a1410` | 应用背景（暖黑） |
| `--bg-surface` | `#221c16` | 卡片/面板背景 |
| `--bg-elevated` | `#2a2218` | 悬浮层背景 |
| `--bg-input` | `#0f0c08` | 输入框背景（更深） |
| `--text-primary` | `#e8d5a3` | 主文字（暖琥珀） |
| `--text-secondary` | `#b8a080` | 次要文字（暖灰） |
| `--text-dim` | `#6b5c48` | 辅助文字 |
| `--accent` | `#e8943a` | 强调色（暖橙） |
| `--accent-glow` | `#f0b050` | 发光状态 |
| `--success` | `#7aad5a` | 成功/完成（暖绿） |
| `--danger` | `#c85545` | 错误/失败（暖红） |
| `--warning` | `#d4a040` | 运行中（暖黄） |
| `--border` | `#3a3024` | 边框（暖棕） |
| `--border-active` | `#5a4a30` | 激活边框 |

## 字体

| 用途 | 字体 | Fallback |
|------|------|----------|
| 标题/Logo | **Press Start 2P** | monospace |
| 正文/UI | **VT323** (20px) | 'Courier New', monospace |
| 代码/日志 | **Fira Code** | monospace |

Google Fonts:
```
@import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&family=VT323&family=Fira+Code&display=swap');
```

## 组件设计

### 搜索区 (SearchBar)
- 大输入框，深色背景(#0f0c08)，琥珀色文字
- border: 2px solid var(--border)，focus时变accent
- 下方chips：半透明背景 + 小字体VT323
- "生成游戏"按钮：像素边框 + hover时发光

### Agent面板 (AgentPanel)
- 6个头像圆形排列或2x3网格
- 每个头像：大号emoji + 名称(VT323 14px) + 状态灯
- 状态灯：8x8px方块，颜色对应状态
  - idle：灰色(#3a3024)
  - running：黄色闪烁(#d4a040, animation: pulse 0.8s)
  - done：绿色(#7aad5a)
  - failed：红色(#c85545)
- 当前运行的Agent有发光边框 + 气泡消息
- 气泡消息：从Agent头像冒出，打字机效果逐字显示

### 游戏展示区 (GameFrame)
- iframe嵌入，像素边框包裹
- 加载时显示扫描线动画
- 空状态："等待生成..." + CRT噪点

### 失败提示 (FailureNotice)
- 暖红色左边框
- 原因文字 + 推荐事件chips（点击重新提交）

### 决策轨迹面板 (EventLog)
- 底部可折叠面板
- 每行：[时间戳] [Agent名] [状态图标] [消息]
- 单色间距排列，Fira Code字体
- 自动滚动到最新

## 动效

| 动画 | 时长 | 效果 |
|------|------|------|
| 状态灯闪烁(running) | 0.8s infinite | opacity 1→0.3→1, steps(1) |
| Agent切换 | 200ms | 边框颜色过渡 + scale(1.02) |
| 气泡出现 | 150ms | translateY(-4px) + opacity 0→1 |
| 打字机效果 | 30ms/字 | setInterval逐字追加 |
| 面板展开 | 250ms | max-height过渡 |
| 按钮hover | 100ms | background亮10% + 轻微上移 |
| 重试抖动 | 300ms | translateX(±4px) steps(3) |

## CRT效果（可选叠加）
- body::after：repeating-linear-gradient扫描线
- 屏幕四角暗角：radial-gradient vignette
- 微妙噪点：SVG feTurbulence + mix-blend-mode overlay
