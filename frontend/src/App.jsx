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
  { key:'artist',   name:'着色' },
]

export default function App() {
  const { statuses, messages, gameCode, error, isGenerating, sendEvent, cancel } = useWebSocket()

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
            onClose={cancel}
          />

          {/* z-100: 失败提示 */}
          <FailureNotice
            visible={!!error}
            reason={error?.reason||''}
            suggestions={error?.suggestions||[]}
            onRetry={sendEvent}
            onDismiss={cancel}
          />

          {/* z-100: 决策轨迹 */}
          <DecisionLog messages={messages} />

        </section>
      </div>
    </ErrorBoundary>
  )
}
