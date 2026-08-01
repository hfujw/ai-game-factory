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
      {/* Expanded panel */}
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

      {/* Toggle button */}
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
