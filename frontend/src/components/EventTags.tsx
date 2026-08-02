import { useState, useEffect, useRef } from 'react'
import { ChevronDown, History } from 'lucide-react'

const DEMO_EVENTS = ['1940年 Turing 破译 Enigma','1989年 Guido 发明 Python','1974年 TCP 协议诞生','1991年 Linus 写下 Linux','1995年 Java 的诞生']

interface Props { onSelect:(name:string)=>void; disabled:boolean }

export function EventTags({ onSelect, disabled }: Props) {
  const [events, setEvents] = useState<string[]>([])
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    fetch('/api/events').then(r=>r.json()).then(d=>setEvents((d.events||[]).map((e:any)=>e.name))).catch(()=>setEvents(DEMO_EVENTS))
  }, [])

  // Click outside to close
  useEffect(() => {
    const handler = (e:MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  if (events.length===0) return null

  return (
    <div ref={ref} className="fixed top-5 right-5 z-[110] pointer-events-auto">
      <button
        onClick={() => setOpen(!open)}
        disabled={disabled}
        className="flex items-center gap-2 px-4 py-2.5 bg-white/[0.06] backdrop-blur-xl border border-white/[0.12] rounded-2xl text-white/60 hover:text-white/85 hover:bg-white/[0.1] hover:border-white/[0.2] transition-all text-xs shadow-lg disabled:opacity-30"
      >
        <History className="w-3.5 h-3.5" />
        历史事件库
        <ChevronDown className={`w-3 h-3 transition-transform ${open?'rotate-180':''}`} />
      </button>

      {open && (
        <div className="absolute top-full right-0 mt-2 w-80 bg-black/80 backdrop-blur-2xl border border-white/[0.12] rounded-2xl shadow-2xl overflow-y-auto" style={{maxHeight:'50vh'}}>
          {events.map((name, i) => (
            <button
              key={i}
              onClick={() => { onSelect(name); setOpen(false) }}
              disabled={disabled}
              className="w-full text-left px-5 py-3 text-[13px] text-white/50 hover:text-white/90 hover:bg-white/[0.06] transition-all border-b border-white/[0.04] last:border-0 disabled:opacity-20"
            >
              {name}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
