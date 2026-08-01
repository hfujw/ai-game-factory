import { useState, useEffect } from 'react'

const DEMO_EVENTS = ['1940年 Turing 破译 Enigma','1989年 Guido 发明 Python','1974年 TCP 协议诞生','1991年 Linus 写下 Linux','1995年 Java 的诞生']
const POSITIONS = [{ top:'12%',left:'20%' },{ top:'8%',left:'72%' },{ top:'84%',left:'26%' },{ top:'82%',left:'68%' },{ top:'46%',left:'6%' }]

interface Props { onSelect:(name:string)=>void; disabled:boolean }

export function EventTags({ onSelect, disabled }: Props) {
  const [events, setEvents] = useState<string[]>([])
  useEffect(() => {
    fetch('/api/events').then(r=>r.json()).then(d=>setEvents((d.events||[]).map((e:any)=>e.name))).catch(()=>setEvents(DEMO_EVENTS))
  }, [])
  if (events.length===0) return null
  return (<>
    {events.slice(0,5).map((name,i)=>(
      <button key={i} onClick={()=>onSelect(name)} disabled={disabled}
        className="absolute px-3 py-1.5 text-[11px] bg-white/[0.08] backdrop-blur-md border border-white/[0.14] rounded-full text-white/55 hover:bg-white/[0.16] hover:text-white/90 hover:border-white/[0.25] transition-all disabled:opacity-20 disabled:cursor-not-allowed pointer-events-auto"
        style={{ top:POSITIONS[i].top, left:POSITIONS[i].left }}>
        {name.length>22?name.slice(0,22)+'…':name}
      </button>
    ))}
  </>)
}
