import { useState, useEffect, useRef } from 'react'
import { ChevronDown, Compass } from 'lucide-react'

interface Props { onSelect:(name:string)=>void; disabled:boolean }

export function EventTags({ onSelect, disabled }: Props) {
  const [events, setEvents] = useState<any[]>([])
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    fetch('/api/events').then(r=>r.json()).then(d=>setEvents(d.events||[])).catch(()=>{})
  }, [])

  useEffect(() => {
    const handler = (e:MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  if (events.length===0) return null

  const names = events.map((e:any) => e.name || e.title || '')

  return (
    <div ref={ref} className="fixed top-5 right-5 z-[110] pointer-events-auto">
      <button
        onClick={() => setOpen(!open)}
        disabled={disabled}
        className="flex items-center gap-2 px-4 py-2.5 bg-white/[0.04] backdrop-blur-xl border border-white/[0.08] rounded-2xl text-white/45 hover:text-white/65 hover:bg-white/[0.06] hover:border-white/[0.14] transition-all text-xs disabled:opacity-30"
      >
        <Compass className="w-3.5 h-3.5" />
        探索主题
        <ChevronDown className={`w-3 h-3 transition-transform ${open?'rotate-180':''}`} />
      </button>

      {open && (
        <div className="absolute top-full right-0 mt-2 w-80 bg-black/80 backdrop-blur-2xl border border-white/[0.08] rounded-2xl shadow-2xl overflow-y-auto" style={{maxHeight:'50vh'}}>
          {names.map((name: string, i: number) => (
            <button
              key={i}
              onClick={() => { onSelect(name); setOpen(false) }}
              disabled={disabled}
              className="w-full text-left px-5 py-2.5 text-[13px] text-white/45 hover:text-white/85 hover:bg-white/[0.04] transition-all border-b border-white/[0.03] last:border-0 disabled:opacity-20"
            >
              {name}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
