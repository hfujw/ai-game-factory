import { useState } from 'react'
import { Maximize2, Minimize2, X } from 'lucide-react'

interface Props { visible:boolean; gameCode:string|null; isGenerating:boolean; agentCount:number; doneCount:number; onClose:()=>void }

export function GamePanel({ visible, gameCode, isGenerating, agentCount, doneCount, onClose }: Props) {
  const [isFullscreen, setFullscreen] = useState(false)
  if (!visible && !isGenerating) return null
  const progress = agentCount>0 ? (doneCount/agentCount)*100 : 0

  const panelStyle = (isFullscreen:boolean) => ({
    position: 'absolute' as const, left:'50%', zIndex:50,
    width: isFullscreen ? '100vw' : 'min(560px, 55vw)',
    height: isFullscreen ? '100vh' : 'auto',
    aspectRatio: isFullscreen ? undefined : '16/9',
    top: isFullscreen ? 0 : '56%',
    transform: isFullscreen ? 'translate(-50%,0)' : 'translate(-50%,-50%)',
    borderRadius: isFullscreen ? 0 : 20,
    background: isFullscreen ? 'rgba(0,0,0,0.95)'
      : visible ? 'rgba(0,0,0,0.55)'          // 游戏渲染：实一点
      : 'rgba(0,0,0,0.12)',                     // 生成中：极透液态玻璃
    backdropFilter: isFullscreen ? 'none'
      : visible ? 'blur(18px)'
      : 'blur(6px)',
    WebkitBackdropFilter: isFullscreen ? 'none'
      : visible ? 'blur(18px)'
      : 'blur(6px)',
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
      {/* Generating progress */}
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

      {/* Empty idle */}
      {!isGenerating && !visible && (
        <div className="w-full h-full flex flex-col items-center justify-center gap-5">
          <p className="text-white/45 text-sm tracking-[0.05em]" style={{ animation:'blink 2s infinite' }}>
            等待时间裂隙开启...
          </p>
          <div className="w-4 h-4 rounded-full"
            style={{ background:'rgba(251,146,60,0.5)', boxShadow:'0 0 16px rgba(251,146,60,0.4)', animation:'blink 1.5s infinite' }} />
        </div>
      )}

      {/* Game iframe */}
      {visible && !isFullscreen && (<>
        <div className="absolute top-3 right-3 z-10 flex gap-1.5">
          <button onClick={()=>setFullscreen(true)}
            className="p-2 rounded-lg bg-white/[0.08] hover:bg-white/[0.18] text-white/50 hover:text-white/80 transition-colors" title="全屏"><Maximize2 size={14}/></button>
          <button onClick={onClose}
            className="p-2 rounded-lg bg-white/[0.08] hover:bg-red-500/20 text-white/50 hover:text-red-400 transition-colors" title="关闭"><X size={14}/></button>
        </div>
        <iframe srcDoc={gameCode||''} sandbox="allow-scripts" title="生成游戏"
          className="w-full h-full border-none bg-black" style={{ borderRadius:16 }} />
      </>)}

      {/* Fullscreen */}
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
