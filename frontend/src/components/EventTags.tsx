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

  // Click outside to close
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
        {/* Category toggle */}
        <button
          onClick={() => { setCategory(isBag ? 'computer_history' : 'bagu'); setOpen(false) }}
          disabled={disabled}
          className="flex items-center gap-1.5 px-3 py-2.5 bg-white/[0.04] backdrop-blur-xl border border-white/[0.08] rounded-2xl text-white/40 hover:text-white/70 hover:bg-white/[0.08] transition-all text-[11px] disabled:opacity-30"
          title={isBag ? '切换到计算机历史' : '切换到 Python 面试'}
        >
          {isBag ? <Code2 className="w-3.5 h-3.5" /> : <History className="w-3.5 h-3.5" />}
          {isBag ? 'Python 面试' : '计算机历史'}
        </button>
        {/* Dropdown */}
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
