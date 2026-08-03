# 时光像素 — 前端 完整源码

> 给 Kimi 看 · 文件 2/2 · 2026-08-03
> React 18 + Vite 5 + Tailwind 3 + frmr-motion + lucide-react

---

## 技术栈

- React 18.3 + Vite 5.4
- Tailwind CSS 3.4
- framer-motion 12
- lucide-react 0.400
- 设计风格：液态玻璃暗色 + 光标聚光灯

## 组件树

```
App
├── RevealLayer          # z-20: canvas mask 光标聚光灯
├── 标题                  # z-50: "时光像素" hero动画
├── SearchBubble         # z-50: 搜索输入框+生成/取消
├── EventTags            # z-110: category切换+事件下拉
├── AgentBuds            # z-50: 6Agent银色闪电+状态灯
├── GamePanel            # z-50: iframe游戏+进度条
├── FailureNotice        # z-200: 失败提示+推荐重试
├── DecisionLog          # z-100: 决策轨迹面板
└── ErrorBoundary        # 渲染错误捕获
```

## WebSocket 消息协议

| type | 前端处理 |
|------|---------|
| agent_progress | 更新6Agent状态灯+日志行 |
| agent_log | 追加决策轨迹 |
| review_rejected | 显示反馈+重试计数 |
| game_ready | 在iframe中展示游戏 |
| generation_failed | 显示失败原因+推荐 |

---

## 源码

### 1. main.jsx

```jsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

### 2. index.css

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

* { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif; }

@keyframes heroReveal {
  0%   { opacity:0; transform:translateY(28px); filter:blur(12px); }
  100% { opacity:1; transform:translateY(0); filter:blur(0); }
}
@keyframes heroFadeUp {
  0%   { opacity:0; transform:translateY(20px); }
  100% { opacity:1; transform:translateY(0); }
}
@keyframes heroZoom {
  0%   { transform:scale(1.12); }
  100% { transform:scale(1); }
}
@keyframes panelReveal {
  0%   { opacity:0; transform:translateX(-50%) scale(0.92); }
  100% { opacity:1; transform:translateX(-50%) scale(1); }
}
@keyframes pulseGlow {
  0%,100% { box-shadow:0 0 8px rgba(52,211,153,0.15); }
  50%     { box-shadow:0 0 24px rgba(52,211,153,0.3); }
}
@keyframes blink {
  0%,100% { opacity:1; }
  50%     { opacity:0.2; }
}
@keyframes progressBar {
  0%   { width:0%; }
  100% { width:100%; }
}

.hero-anim   { opacity:0; animation-fill-mode:forwards; animation-timing-function:cubic-bezier(0.16,1,0.3,1); }
.hero-reveal { animation-name:heroReveal; animation-duration:1.1s; }
.hero-fade   { animation-name:heroFadeUp; animation-duration:1s; }
.hero-zoom   { animation:heroZoom 1.8s cubic-bezier(0.16,1,0.3,1) forwards; }
.panel-reveal{ animation:panelReveal 0.4s cubic-bezier(0.16,1,0.3,1) forwards; }

@media (prefers-reduced-motion:reduce){ .hero-anim,.hero-zoom,.panel-reveal{ animation:none;opacity:1; } }

::-webkit-scrollbar { width:3px; }
::-webkit-scrollbar-track { background:transparent; }
::-webkit-scrollbar-thumb { background:rgba(255,255,255,0.08); border-radius:10px; }
```

### 3. App.jsx

```jsx
import { useState, useRef, useEffect } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import RevealLayer from './components/RevealLayer'
import { GamePanel } from './components/GamePanel'
import { AgentBuds } from './components/AgentBuds'
import { SearchBubble } from './components/SearchBubble'
import { EventTags } from './components/EventTags'
import { DecisionLog } from './components/DecisionLog'
import { FailureNotice } from './components/FailureNotice'
import { ErrorBoundary } from './components/ErrorBoundary'

const BG_BASE   = '/images/base.jpg'
const BG_REVEAL = '/images/reveal.jpg'

const AGENTS = [
  { key:'crawler',  name:'寻根' },
  { key:'planner',  name:'织梦' },
  { key:'writer',   name:'叙事' },
  { key:'coder',    name:'构建' },
  { key:'reviewer', name:'凝视' },
  { key:'artist_post', name:'着色' },
]

export default function App() {
  const { statuses, messages, gameCode, error, isGenerating, sendEvent, cancel, dismiss } = useWebSocket()

  // ── 光标聚光灯（同 lithos-replica）──
  const mouse  = useRef({ x:-999, y:-999 })
  const smooth = useRef({ x:-999, y:-999 })
  const rafRef = useRef()
  const [cursorPos, setCursorPos] = useState({ x:-999, y:-999 })

  useEffect(() => {
    const onMove = (e) => { mouse.current = { x:e.clientX, y:e.clientY } }
    window.addEventListener('mousemove', onMove)
    const loop = () => {
      smooth.current.x += (mouse.current.x - smooth.current.x) * 0.1
      smooth.current.y += (mouse.current.y - smooth.current.y) * 0.1
      const rx=Math.round(smooth.current.x), ry=Math.round(smooth.current.y)
      setCursorPos(p => (p.x===rx&&p.y===ry)?p:{x:rx,y:ry})
      rafRef.current = requestAnimationFrame(loop)
    }
    rafRef.current = requestAnimationFrame(loop)
    return () => { window.removeEventListener('mousemove',onMove); cancelAnimationFrame(rafRef.current) }
  }, [])

  const completedAgents = Object.values(statuses).filter(s => s.status==='done').length

  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-black">
        <section className="relative w-full h-screen overflow-hidden bg-black" style={{ height:'100dvh' }}>

          {/* z-10: 基底图 */}
          <div className="absolute inset-0 bg-center bg-cover bg-no-repeat z-10 hero-zoom"
            style={{ backgroundImage:`url(${BG_BASE})` }} />

          {/* z-20: 光标揭示层 */}
          <RevealLayer image={BG_REVEAL} cursorX={cursorPos.x} cursorY={cursorPos.y} />

          {/* z-50: 标题 */}
          <div className="absolute z-50 top-[10%] left-0 right-0 flex flex-col items-center text-center px-5 pointer-events-none">
            <h1 className="text-white leading-[0.95]">
              <span className="block text-5xl sm:text-7xl md:text-8xl font-semibold hero-anim hero-reveal"
                style={{ fontFamily:"'PingFang SC','Noto Serif SC','STSong',serif", letterSpacing:'0.04em', animationDelay:'0.25s' }}>
                时光像素
              </span>
              <span className="block text-lg sm:text-2xl md:text-3xl font-light mt-1 text-white/45 hero-anim hero-reveal"
                style={{ letterSpacing:'0.18em', animationDelay:'0.42s' }}>
                以 史 为 壤  ·  生 长 游 戏
              </span>
            </h1>
          </div>

          {/* z-50: 搜索框 */}
          <div className="absolute z-50 top-[28%] left-1/2 -translate-x-1/2 w-[90vw] max-w-lg pointer-events-auto">
            <SearchBubble onGenerate={sendEvent} isGenerating={isGenerating} onCancel={cancel} />
          </div>

          {/* z-50: 事件标签 */}
          <div className="absolute z-50 inset-0 pointer-events-none">
            <EventTags onSelect={sendEvent} disabled={isGenerating} />
          </div>

          {/* z-50: 6 Agent 银色闪电 */}
          <div className="absolute z-50 inset-0 pointer-events-none">
            <AgentBuds agents={AGENTS} statuses={statuses} />
          </div>

          {/* z-50: 游戏展示区 */}
          <GamePanel
            visible={!!gameCode}
            gameCode={gameCode}
            isGenerating={isGenerating}
            agentCount={AGENTS.length}
            doneCount={completedAgents}
            onClose={dismiss}
          />

          {/* z-100: 失败提示 */}
          <FailureNotice
            visible={!!error}
            reason={error?.reason||''}
            suggestions={error?.suggestions||[]}
            onRetry={sendEvent}
            onDismiss={dismiss}
          />

          {/* z-100: 决策轨迹 */}
          <DecisionLog messages={messages} />

        </section>
      </div>
    </ErrorBoundary>
  )
}
```

### 4. hooks/useWebSocket.js

```javascript
import { useState, useRef, useCallback } from 'react'

const WS_URL = `ws${location.protocol === 'https:' ? 's' : ''}://${window.location.host}/ws/generate`

export function useWebSocket() {
  const [statuses, setStatuses] = useState({})
  const [messages, setMessages] = useState([])
  const [gameCode, setGameCode] = useState(null)
  const [error, setError] = useState(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const wsRef = useRef(null)
  const logIdRef = useRef(0)
  const generatingRef = useRef(false)
  const lastSend = useRef(0)

  const sendEvent = useCallback((eventText) => {
    if (!eventText.trim()) return
    const now = Date.now()
    if (now - lastSend.current < 1000) return
    lastSend.current = now

    if (wsRef.current) { wsRef.current.close() }

    setStatuses({}); setMessages([]); setGameCode(null); setError(null)
    setIsGenerating(true); generatingRef.current = true

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => { ws.send(JSON.stringify({ event: eventText })) }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        switch (data.type) {
          case 'agent_progress':
            setStatuses(prev => ({
              ...prev,
              [data.agent]: { status: data.status, message: data.message, retries: (prev[data.agent]?.retries || 0) },
            }))
            setMessages(prev => [...prev, {
              id: ++logIdRef.current, time: new Date().toLocaleTimeString(),
              agent: data.agent, detail: data.message,
            }])
            break
          case 'game_ready':
            setGameCode(data.game_code); setIsGenerating(false); generatingRef.current = false
            break
          case 'generation_failed':
            setError({ reason: data.reason || '生成失败', suggestions: data.suggestions || [] })
            setIsGenerating(false); generatingRef.current = false
            break
          case 'agent_log':
            setMessages(prev => [...prev, {
              id: ++logIdRef.current, time: new Date().toLocaleTimeString(),
              agent: data.agent, detail: `${data.action}: ${data.detail}`,
            }])
            break
          case 'review_rejected':
            setMessages(prev => [...prev, {
              id: ++logIdRef.current, time: new Date().toLocaleTimeString(),
              agent: 'reviewer', detail: `❌ 审查不通过 → 退回重做: ${data.feedback?.slice(0, 80) || ''}`,
            }])
            break
        }
      } catch (e) {
        setMessages(prev => [...prev, {
          id: ++logIdRef.current, time: new Date().toLocaleTimeString(),
          agent: 'system', detail: `消息解析失败: ${e.message}`,
        }])
      }
    }

    ws.onerror = () => {
      setError({ reason: 'WebSocket 连接失败，请确认后端已启动', suggestions: [] })
      setIsGenerating(false); generatingRef.current = false
    }

    ws.onclose = () => {
      if (generatingRef.current) { setIsGenerating(false); generatingRef.current = false }
    }
  }, [])

  const cancel = useCallback(() => {
    if (wsRef.current) { wsRef.current.close(); wsRef.current = null }
    setIsGenerating(false); generatingRef.current = false
  }, [])

  const dismiss = useCallback(() => {
    if (wsRef.current) { wsRef.current.close(); wsRef.current = null }
    setIsGenerating(false); generatingRef.current = false
    setGameCode(null); setError(null); setStatuses({}); setMessages([])
  }, [])

  return { statuses, messages, gameCode, error, isGenerating, sendEvent, cancel, dismiss }
}
```

### 5. components/SearchBubble.tsx

```tsx
import { useState } from 'react'
import { Search, Zap, X } from 'lucide-react'

interface Props { onGenerate:(text:string)=>void; isGenerating:boolean; onCancel:()=>void }

export function SearchBubble({ onGenerate, isGenerating, onCancel }: Props) {
  const [value, setValue] = useState('')

  return (
    <form onSubmit={e=>{e.preventDefault();if(value.trim()){onGenerate(value.trim());setValue('')}}}
      className="flex gap-2 hero-anim hero-fade" style={{ animationDelay:'0.55s' }}>
      <div className="relative flex-1">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40 pointer-events-none" />
        <input value={value} onChange={e=>setValue(e.target.value)} placeholder="输入计算机历史事件…"
          disabled={isGenerating} aria-label="计算机历史事件"
          className="w-full pl-11 pr-4 py-3.5 bg-white/[0.10] backdrop-blur-xl border border-white/[0.18] rounded-2xl text-white text-sm placeholder:text-white/35 focus:outline-none focus:border-lime-400/60 focus:bg-white/[0.16] transition-all disabled:opacity-40 shadow-lg" />
      </div>
      {isGenerating ? (
        <button type="button" onClick={onCancel}
          className="px-4 py-3.5 bg-white/[0.08] border border-white/[0.15] rounded-2xl text-white/60 hover:text-red-400 hover:border-red-400/40 transition-all">
          <X className="w-4 h-4" /></button>
      ) : (
        <button type="submit" disabled={!value.trim()}
          className="px-5 py-3.5 bg-lime-600 hover:bg-lime-500 text-white text-sm font-medium rounded-2xl transition-all hover:scale-[1.02] active:scale-95 disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:scale-100 flex items-center gap-2 shadow-lg shadow-lime-500/20">
          <Zap className="w-4 h-4" />生成</button>
      )}
    </form>
  )
}
```

### 6. components/EventTags.tsx

```tsx
import { useState, useEffect, useRef } from 'react'
import { ChevronDown, History, Code2 } from 'lucide-react'

const DEMO_EVENTS = ['1940年 Turing 破译 Enigma','1989年 Guido 发明 Python','1974年 TCP 协议诞生','1991年 Linus 写下 Linux','1995年 Java 的诞生']

interface Props { onSelect:(name:string)=>void; disabled:boolean }

export function EventTags({ onSelect, disabled }: Props) {
  const [events, setEvents] = useState<any[]>([])
  const [open, setOpen] = useState(false)
  const [category, setCategory] = useState<'computer_history'|'bagu'>('computer_history')
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const cat = category === 'bagu' ? '?category=bagu' : ''
    fetch(`/api/events${cat}`).then(r=>r.json()).then(d=>setEvents(d.events||[])).catch(()=>setEvents(DEMO_EVENTS.map(n=>({name:n}))))
  }, [category])

  useEffect(() => {
    const handler = (e:MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  if (events.length===0) return null

  const isBag = category === 'bagu'
  const names = events.map((e:any) => e.name || e.title || '')

  return (
    <div ref={ref} className="fixed top-5 right-5 z-[110] pointer-events-auto">
      <div className="flex items-center gap-2">
        <button
          onClick={() => { setCategory(isBag ? 'computer_history' : 'bagu'); setOpen(false) }}
          disabled={disabled}
          className="flex items-center gap-1.5 px-3 py-2.5 bg-white/[0.04] backdrop-blur-xl border border-white/[0.08] rounded-2xl text-white/40 hover:text-white/70 hover:bg-white/[0.08] transition-all text-[11px] disabled:opacity-30"
          title={isBag ? '切换到计算机历史' : '切换到 Python 面试'}
        >
          {isBag ? <Code2 className="w-3.5 h-3.5" /> : <History className="w-3.5 h-3.5" />}
          {isBag ? 'Python 面试' : '事件库'}
        </button>
        <button
          onClick={() => setOpen(!open)}
          disabled={disabled}
          className="flex items-center gap-2 px-4 py-2.5 bg-white/[0.06] backdrop-blur-xl border border-white/[0.12] rounded-2xl text-white/60 hover:text-white/85 hover:bg-white/[0.1] hover:border-white/[0.2] transition-all text-xs shadow-lg disabled:opacity-30"
        >
          事件库
          <ChevronDown className={`w-3 h-3 transition-transform ${open?'rotate-180':''}`} />
        </button>
      </div>

      {open && (
        <div className="absolute top-full right-0 mt-2 w-80 bg-black/80 backdrop-blur-2xl border border-white/[0.12] rounded-2xl shadow-2xl overflow-y-auto" style={{maxHeight:'50vh'}}>
          {names.map((name: string, i: number) => (
            <button
              key={i}
              onClick={() => { onSelect(name); setOpen(false) }}
              disabled={disabled}
              className="w-full text-left px-5 py-3 text-[13px] text-white/50 hover:text-white/90 hover:bg-white/[0.06] transition-all border-b border-white/[0.04] last:border-0 disabled:opacity-20 flex items-center gap-2"
            >
              {isBag && events[i]?.difficulty ? (
                <span className="text-[10px] text-lime-400/50">{'★'.repeat(events[i].difficulty)}{'☆'.repeat(4-events[i].difficulty)}</span>
              ) : null}
              <span className="truncate">{name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
```

### 7. components/AgentBuds.tsx

```tsx
import { motion } from 'framer-motion'

interface Agent { key:string; name:string }
interface Status { status:'idle'|'running'|'done'|'failed'; message:string; retries:number }

const POSITIONS = [
  { top:'54%', left:'12%' },
  { top:'62%', left:'23%' },
  { top:'51%', left:'32%' },
  { top:'63%', left:'68%' },
  { top:'53%', left:'77%' },
  { top:'60%', left:'89%' },
]

function LightningBolt() {
  return (
    <svg width="14" height="22" viewBox="0 0 14 22" fill="none">
      <path
        d="M8 0L0 12H5L3 22L14 8H8L10 0H8Z"
        fill="rgba(220,220,240,0.9)"
        style={{ filter:'drop-shadow(0 0 4px rgba(200,200,255,0.7)) drop-shadow(0 0 8px rgba(180,180,255,0.4))' }}
      />
    </svg>
  )
}

export function AgentBuds({ agents, statuses }: { agents:Agent[]; statuses:Record<string,Status> }) {
  return (
    <>
      {agents.map((agent, i) => {
        const s = statuses[agent.key]
        const isRunning = s?.status === 'running'
        const isDone    = s?.status === 'done'
        const isFailed  = s?.status === 'failed'
        const { top, left } = POSITIONS[i]

        return (
          <div key={agent.key} className="absolute flex flex-col items-center gap-1"
            style={{ top, left, transform:'translate(-50%,-50%)' }}>

            <motion.div className="relative flex items-center justify-center"
              initial={{ opacity:0 }}
              animate={{ opacity:1 }}
              transition={{ delay:i*0.08 }}>
              {isRunning && (
                <motion.div className="absolute rounded-full"
                  style={{ width:24, height:24, background:'radial-gradient(circle, rgba(200,200,240,0.25) 0%, transparent 70%)' }}
                  animate={{ scale:[1,1.5,1], opacity:[0.5,0.2,0.5] }}
                  transition={{ duration:1.8, repeat:Infinity, ease:'easeInOut' }}
                />
              )}
              {isDone && (
                <div className="absolute rounded-full"
                  style={{ width:20, height:20, background:'radial-gradient(circle, rgba(200,200,240,0.15) 0%, transparent 70%)', boxShadow:'0 0 10px rgba(180,180,230,0.2)' }}
                />
              )}
              <motion.div
                animate={isRunning ? { scale:[1, 1.2, 0.95, 1.15, 1], opacity:[0.6, 1, 0.8, 1, 0.6] } : {}}
                transition={isRunning ? { duration:1.2, repeat:Infinity, ease:'easeInOut' } : {}}
              >
                {isDone ? (
                  <LightningBolt />
                ) : isFailed ? (
                  <div style={{ width:5, height:8, background:'radial-gradient(ellipse at 50% 40%, #441111, #1a0000)', borderRadius:'50% 50% 50% 50% / 60% 60% 40% 40%', boxShadow:'0 0 4px rgba(255,40,40,0.3)' }} />
                ) : isRunning ? (
                  <div style={{ width:6, height:9, background:'radial-gradient(ellipse at 40% 30%, rgba(220,220,250,0.9), rgba(180,180,220,0.5))', borderRadius:'50% 50% 50% 50% / 60% 60% 40% 40%', boxShadow:'0 0 8px 2px rgba(200,200,240,0.5)', transition:'all 0.5s ease' }} />
                ) : (
                  <div style={{ width:4, height:5, background:'#2a2218', borderRadius:'50%', opacity:0.4 }} />
                )}
              </motion.div>
            </motion.div>

            <span className="text-[9px] tracking-[0.06em] font-medium whitespace-nowrap"
              style={{
                color: isDone ? 'rgba(240,240,255,0.9)' : isRunning ? 'rgba(230,230,255,0.7)' : isFailed ? 'rgba(255,120,120,0.5)' : 'rgba(255,255,255,0.1)',
                textShadow: isDone ? '0 0 6px rgba(200,200,240,0.5)' : isRunning ? '0 0 4px rgba(200,200,240,0.3)' : 'none',
              }}>
              {agent.name}
            </span>

            {s?.retries > 0 && (
              <span className="absolute -top-1 -right-1 w-3.5 h-3.5 rounded-full bg-red-500 text-[7px] font-bold text-white flex items-center justify-center"
                style={{ boxShadow:'0 0 5px rgba(239,68,68,0.5)' }}>
                {s.retries}
              </span>
            )}
          </div>
        )
      })}
    </>
  )
}
```

### 8. components/GamePanel.tsx

```tsx
import { useState } from 'react'
import { Maximize2, Minimize2, Minus, X } from 'lucide-react'

interface Props { visible:boolean; gameCode:string|null; isGenerating:boolean; agentCount:number; doneCount:number; onClose:()=>void }

export function GamePanel({ visible, gameCode, isGenerating, agentCount, doneCount, onClose }: Props) {
  const [isFullscreen, setFullscreen] = useState(false)
  const [minimized, setMinimized] = useState(false)

  if (!visible && !isGenerating) return null
  const progress = agentCount>0 ? (doneCount/agentCount)*100 : 0

  if (minimized && visible) {
    return (
      <div className="absolute z-50 left-1/2 -translate-x-1/2 pointer-events-auto" style={{ top:'58%' }}>
        <button onClick={() => setMinimized(false)}
          className="flex items-center gap-2 px-4 py-2 bg-black/40 backdrop-blur-xl border border-lime-400/20 rounded-full text-lime-400/70 hover:text-lime-300 hover:border-lime-400/40 transition-all text-xs shadow-lg">
          <div className="w-2 h-2 rounded-full bg-lime-400 animate-pulse" />
          游戏已就绪
        </button>
      </div>
    )
  }

  const panelStyle = (full:boolean) => ({
    position: 'absolute' as const, left:'50%', zIndex:50,
    width: full ? '100vw' : 'min(560px, 55vw)',
    height: full ? '100vh' : 'auto',
    aspectRatio: full ? undefined : '16/9',
    top: full ? 0 : '56%',
    transform: full ? 'translate(-50%,0)' : 'translate(-50%,-50%)',
    borderRadius: full ? 0 : 20,
    background: full ? 'rgba(0,0,0,0.95)'
      : visible ? 'rgba(0,0,0,0.55)'
      : 'rgba(0,0,0,0.12)',
    backdropFilter: full ? 'none' : visible ? 'blur(18px)' : 'blur(6px)',
    WebkitBackdropFilter: full ? 'none' : visible ? 'blur(18px)' : 'blur(6px)',
    border: visible ? '1px solid rgba(52,211,153,0.3)'
      : isGenerating ? '1px solid rgba(255,255,255,0.1)'
      : '1px solid rgba(255,255,255,0.06)',
    boxShadow: visible ? '0 0 40px rgba(52,211,153,0.2)'
      : isGenerating ? '0 0 0 transparent'
      : '0 4px 24px rgba(0,0,0,0.3)',
    transition:'all 0.5s cubic-bezier(0.16,1,0.3,1)',
  })

  const s = panelStyle(isFullscreen)

  return (
    <div style={s}>
      {isGenerating && !visible && (
        <div className="w-full h-full flex flex-col items-center justify-center gap-4 px-8">
          <p className="text-white/60 text-sm tracking-[0.05em]">Agent 协作中…</p>
          <div className="flex gap-3">
            {[...Array(agentCount)].map((_,i)=>(
              <div key={i} className="w-2.5 h-2.5 rounded-full transition-all duration-300"
                style={{ background:i<doneCount?'#34d399':i===doneCount?'#34d399':'rgba(255,255,255,0.15)',
                  boxShadow:i===doneCount?'0 0 10px rgba(52,211,153,0.6)':'none',
                  animation:i===doneCount?'blink 1s infinite':'none' }} />
            ))}
          </div>
          <div className="w-full h-[2px] bg-white/[0.08] rounded-full overflow-hidden">
            <div className="h-full rounded-full transition-all duration-700"
              style={{ width:`${progress}%`, background:'linear-gradient(90deg,#f59e0b,#34d399)' }} />
          </div>
        </div>
      )}

      {!isGenerating && !visible && (
        <div className="w-full h-full flex flex-col items-center justify-center gap-5">
          <p className="text-white/45 text-sm tracking-[0.05em]" style={{ animation:'blink 2s infinite' }}>
            等待时间裂隙开启...
          </p>
          <div className="w-4 h-4 rounded-full"
            style={{ background:'rgba(251,146,60,0.5)', boxShadow:'0 0 16px rgba(251,146,60,0.4)', animation:'blink 1.5s infinite' }} />
        </div>
      )}

      {visible && !isFullscreen && (<>
        <div className="absolute top-3 right-3 z-10 flex gap-1.5">
          <button onClick={() => setMinimized(true)}
            className="p-2 rounded-lg bg-white/[0.08] hover:bg-white/[0.18] text-white/50 hover:text-amber-400 transition-colors" title="最小化">
            <Minus size={14}/></button>
          <button onClick={()=>setFullscreen(true)}
            className="p-2 rounded-lg bg-white/[0.08] hover:bg-white/[0.18] text-white/50 hover:text-white/80 transition-colors" title="全屏">
            <Maximize2 size={14}/></button>
          <button onClick={onClose}
            className="p-2 rounded-lg bg-white/[0.08] hover:bg-red-500/20 text-white/50 hover:text-red-400 transition-colors" title="关闭">
            <X size={14}/></button>
        </div>
        <iframe srcDoc={gameCode||''} sandbox="allow-scripts" title="生成游戏"
          className="w-full h-full border-none bg-black" style={{ borderRadius:16 }} />
      </>)}

      {visible && isFullscreen && (
        <div className="relative w-full h-full">
          <button onClick={()=>setFullscreen(false)}
            className="absolute top-4 right-4 z-20 p-2.5 rounded-lg bg-white/[0.1] hover:bg-red-500/25 text-white/50 hover:text-red-400 transition-colors" title="退出全屏">
            <Minimize2 size={16}/></button>
          <iframe srcDoc={gameCode||''} sandbox="allow-scripts" title="生成游戏-全屏"
            className="w-full h-full border-none bg-black" />
        </div>
      )}
    </div>
  )
}
```

### 9. components/RevealLayer.tsx

```tsx
import { useRef, useEffect } from 'react';

interface RevealLayerProps {
  image: string;
  cursorX: number;
  cursorY: number;
}

const SPOTLIGHT_R = 260;

export default function RevealLayer({ image, cursorX, cursorY }: RevealLayerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const revealRef = useRef<HTMLDivElement>(null);
  const cursorRef = useRef({ x: cursorX, y: cursorY });

  cursorRef.current = { x: cursorX, y: cursorY };

  const draw = () => {
    const canvas = canvasRef.current;
    const revealDiv = revealRef.current;
    if (!canvas || !revealDiv) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const w = window.innerWidth;
    const h = window.innerHeight;

    if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
    }

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    const cx = cursorRef.current.x;
    const cy = cursorRef.current.y;

    if (cx >= 0 || cy >= 0) {
      const gradient = ctx.createRadialGradient(cx, cy, 0, cx, cy, SPOTLIGHT_R);
      gradient.addColorStop(0, 'rgba(255,255,255,1)');
      gradient.addColorStop(0.4, 'rgba(255,255,255,1)');
      gradient.addColorStop(0.6, 'rgba(255,255,255,0.75)');
      gradient.addColorStop(0.75, 'rgba(255,255,255,0.4)');
      gradient.addColorStop(0.88, 'rgba(255,255,255,0.12)');
      gradient.addColorStop(1, 'rgba(255,255,255,0)');

      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.arc(cx, cy, SPOTLIGHT_R, 0, Math.PI * 2);
      ctx.fill();
    }

    const dataUrl = canvas.toDataURL();
    revealDiv.style.maskImage = `url(${dataUrl})`;
    revealDiv.style.webkitMaskImage = `url(${dataUrl})`;
    revealDiv.style.maskSize = '100% 100%';
    revealDiv.style.webkitMaskSize = '100% 100%';
  };

  useEffect(() => { draw(); }, [cursorX, cursorY]);

  useEffect(() => {
    const handleResize = () => draw();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <>
      <canvas ref={canvasRef} className="absolute inset-0 pointer-events-none" style={{ display: 'none' }} />
      <div ref={revealRef}
        className="absolute inset-0 bg-center bg-cover bg-no-repeat z-30 pointer-events-none"
        style={{ backgroundImage: `url(${image})` }} />
    </>
  );
}
```

### 10. components/FailureNotice.tsx

```tsx
import { AlertCircle, X } from 'lucide-react'

interface Props {
  visible: boolean
  reason: string
  suggestions: string[]
  onRetry: (s:string) => void
  onDismiss: () => void
}

export function FailureNotice({ visible, reason, suggestions, onRetry, onDismiss }: Props) {
  if (!visible) return null

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center pointer-events-none">
      <div className="pointer-events-auto w-[90vw] max-w-md bg-black/85 backdrop-blur-2xl border border-red-500/12 rounded-3xl p-6 shadow-2xl">
        <div className="flex items-start gap-3 mb-4">
          <div className="w-9 h-9 rounded-full bg-red-500/8 flex items-center justify-center shrink-0 mt-0.5">
            <AlertCircle className="w-4 h-4 text-red-400" />
          </div>
          <div className="flex-1">
            <h3 className="text-sm font-semibold text-red-400 mb-1">生成失败</h3>
            <p className="text-[13px] text-white/40 leading-relaxed">{reason}</p>
          </div>
          <button onClick={onDismiss} className="p-1 rounded-lg hover:bg-white/[0.05] text-white/20 hover:text-white/50 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>
        {suggestions.length > 0 && (
          <div className="flex flex-wrap gap-2 pl-12">
            <span className="text-[10px] text-white/20 self-center">建议尝试：</span>
            {suggestions.slice(0,4).map((s,i) => (
              <button key={i} onClick={() => onRetry(s)}
                className="px-3 py-1 text-[11px] bg-white/[0.03] border border-white/[0.06] rounded-full text-white/40 hover:bg-white/[0.08] hover:text-white/70 transition-all">
                {s.length>20 ? s.slice(0,20)+'…' : s}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
```

### 11. components/DecisionLog.tsx

```tsx
import { useState, useEffect, useRef } from 'react'
import { ScrollText, ChevronDown } from 'lucide-react'

interface Message { id:number; time:string; agent:string; detail:string }

export function DecisionLog({ messages }: { messages:Message[] }) {
  const [open, setOpen] = useState(false)
  const bodyRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (bodyRef.current && open) bodyRef.current.scrollTop = bodyRef.current.scrollHeight
  }, [messages, open])

  return (
    <div className="fixed bottom-6 left-6 z-[100]">
      {open && (
        <div className="mb-3 w-72 max-h-56 bg-black/75 backdrop-blur-2xl border border-white/[0.06] rounded-2xl overflow-hidden shadow-2xl">
          <div ref={bodyRef} className="overflow-y-auto max-h-48 p-3 space-y-1">
            {messages.length === 0 ? (
              <div className="text-white/12 text-[11px] text-center py-6">等待 Agent 开始工作…</div>
            ) : (
              messages.slice(-30).map(m => (
                <div key={m.id} className="flex gap-2 text-[10px] font-mono text-white/35 hover:bg-white/[0.03] rounded px-1 py-0.5">
                  <span className="text-white/12 shrink-0 w-11">{m.time}</span>
                  <span className="text-lime-400/50 shrink-0 w-12">[{m.agent}]</span>
                  <span className="truncate">{m.detail}</span>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      <button onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-4 py-2.5 bg-black/60 backdrop-blur-xl border border-white/[0.14] rounded-full text-white/55 hover:text-white/85 transition-all text-xs shadow-lg">
        <ScrollText className="w-3.5 h-3.5" />
        决策轨迹
        {messages.length > 0 && (
          <span className="bg-lime-400/8 text-lime-400/70 text-[10px] px-1.5 py-0.5 rounded-full">{messages.length}</span>
        )}
        <ChevronDown className={`w-3 h-3 transition-transform ${open?'rotate-180':''}`} />
      </button>
    </div>
  )
}
```

### 12. components/ErrorBoundary.tsx

```tsx
import { Component, ReactNode } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

export class ErrorBoundary extends Component<{ children:ReactNode }, { hasError:boolean; error:Error|null }> {
  constructor(props:{ children:ReactNode }) {
    super(props)
    this.state = { hasError:false, error:null }
  }
  static getDerivedStateFromError(error:Error) { return { hasError:true, error } }
  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-dvh bg-black flex items-center justify-center p-8">
          <div className="text-center">
            <div className="w-14 h-14 mx-auto mb-5 rounded-2xl bg-red-500/8 flex items-center justify-center">
              <AlertTriangle className="w-6 h-6 text-red-400" />
            </div>
            <h2 className="text-white/70 text-lg font-semibold mb-2">界面渲染出错</h2>
            <p className="text-white/25 text-sm mb-5">{this.state.error?.message||'未知错误'}</p>
            <button onClick={() => window.location.reload()}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-2xl text-white/50 hover:text-white hover:bg-white/[0.08] transition-all text-sm">
              <RefreshCw className="w-4 h-4" />刷新页面
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
```

### 13. package.json

```json
{
  "name": "time-pixels",
  "private": true,
  "type": "module",
  "scripts": { "dev": "vite", "build": "vite build", "preview": "vite preview" },
  "dependencies": {
    "framer-motion": "^12.0.0",
    "lucide-react": "^0.400.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.4.0",
    "vite": "^5.4.0"
  }
}
```

---

## 运行方式

```bash
cd frontend && npm run dev
# → http://localhost:5173 (或递增端口)
```

## 前端设计要点

1. **光标聚光灯 (RevealLayer)**: Canvas 2D 绘制径向渐变 mask, raf 循环更新 smooth 位置
2. **6 Agent 状态**: 银色闪电 SVG, 四种状态(idle/running/done/failed)各有不同视觉效果
3. **游戏面板 (GamePanel)**: iframe srcDoc + sandbox="allow-scripts", 支持最小化/全屏
4. **决策轨迹 (DecisionLog)**: 底部左侧展开面板, 显示最近30条 Agent 日志
5. **EventTags**: fetch /api/events?category=bagu 获取八股事件, 支持 category 切换
6. **WebSocket 防抖**: 1秒内不重复发送, generatingRef 避免 stale closure
