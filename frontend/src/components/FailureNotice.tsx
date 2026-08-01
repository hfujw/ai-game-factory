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
