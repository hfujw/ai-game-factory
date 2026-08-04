import { useState, useRef, useEffect } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import RevealLayer from './components/RevealLayer'
import { StoryPanel } from './components/StoryPanel'
import { SearchBubble } from './components/SearchBubble'
import { EventTags } from './components/EventTags'
import { DecisionLog } from './components/DecisionLog'
import { FailureNotice } from './components/FailureNotice'
import { ErrorBoundary } from './components/ErrorBoundary'

const BG_BASE   = '/images/base.jpg'
const BG_REVEAL = '/images/reveal.jpg'

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
          <div className="absolute z-50 top-[8%] left-0 right-0 flex flex-col items-center text-center px-5 pointer-events-none">
            <h1 className="text-white leading-[0.95]">
              <span className="block text-5xl sm:text-7xl md:text-8xl font-semibold hero-anim hero-reveal"
                style={{ fontFamily:"'PingFang SC','Noto Serif SC','STSong',serif", letterSpacing:'0.04em', animationDelay:'0.25s' }}>
                时光像素
              </span>
              <span className="block text-lg sm:text-2xl md:text-3xl font-light mt-3 text-white/45 hero-anim hero-reveal"
                style={{ letterSpacing:'0.22em', animationDelay:'0.42s' }}>
                以 光 为 笔  ·  以 史 为 墨
              </span>
            </h1>
          </div>

          {/* z-50: 搜索框 + 快捷标签 + 工具状态灯 */}
          <div className="absolute z-50 top-[28%] left-1/2 -translate-x-1/2 w-[90vw] max-w-lg pointer-events-auto flex flex-col items-center gap-4">
            <SearchBubble onGenerate={sendEvent} isGenerating={isGenerating} onCancel={cancel} />
            <div className="flex flex-wrap justify-center gap-2">
              {['秦始皇修长城','Turing 破译 Enigma','Python 装饰器','郑和下西洋','世界杯历届冠军'].map(t => (
                <button key={t} onClick={() => sendEvent(t)} disabled={isGenerating}
                  className="px-3 py-1 text-[11px] text-white/25 hover:text-white/55 bg-white/[0.02] hover:bg-white/[0.06] border border-white/[0.04] hover:border-white/[0.10] rounded-full transition-all disabled:opacity-20">
                  {t}
                </button>
              ))}
            </div>
          </div>

          {/* z-50: 事件标签 */}
          <div className="absolute z-50 inset-0 pointer-events-none">
            <EventTags onSelect={sendEvent} disabled={isGenerating} />
          </div>

          {/* z-50: 生成结果展示 */}
          <StoryPanel
            visible={!!gameCode}
            gameCode={gameCode}
            isGenerating={isGenerating}
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
          <DecisionLog messages={messages} autoCollapse={!!gameCode} />

        </section>
      </div>
    </ErrorBoundary>
  )
}
