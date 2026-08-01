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
