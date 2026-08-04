import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Brain, Search, Palette, PenLine, Code, ShieldCheck, Sparkles, ChevronDown } from 'lucide-react'

interface Message { id:number; time:string; agent:string; detail:string; type?:string }

const TOOL_ICONS: Record<string, any> = {
  thinking: Brain, search: Search, design: Palette, compose: PenLine,
  render: Code, verify: ShieldCheck,
}
const TOOL_LABELS: Record<string, string> = {
  thinking: '思考', search: '搜索', design: '设计', compose: '文案',
  render: '生成', verify: '审查',
}

export function DecisionLog({ messages, autoCollapse }: { messages:Message[]; autoCollapse?:boolean }) {
  const [open, setOpen] = useState(true)
  const bodyRef = useRef<HTMLDivElement>(null)

  // StoryPanel 弹出时自动折叠
  useEffect(() => {
    if (autoCollapse) setOpen(false)
  }, [autoCollapse])

  useEffect(() => {
    if (!bodyRef.current || !open) return
    const el = bodyRef.current
    // 用户往上翻了就别硬拽到底部
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 50
    if (atBottom) el.scrollTop = el.scrollHeight
  }, [messages, open])

  const toolMsgs = messages.filter(m => m.type === 'thinking' || m.type === 'tool_result')

  return (
    <motion.div
      layout
      transition={{ type: "spring", stiffness: 260, damping: 28 }}
      className={`fixed bottom-6 right-6 z-[100] pointer-events-auto ${
        open
          ? 'w-[420px] max-h-[68vh]'
          : 'w-auto'
      }`}
    >
      <AnimatePresence mode="wait">
        {open ? (
          <motion.div
            key="panel"
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            className="rounded-3xl bg-black/60 backdrop-blur-2xl border border-white/10 shadow-2xl shadow-black/50 overflow-hidden"
          >
            {/* 标题栏 */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-white/[0.04] cursor-pointer"
              onClick={() => setOpen(false)}>
              <div className="flex items-center gap-2">
                <Sparkles size={14} className="text-lime-400" />
                <span className="text-xs font-medium text-white/50">AI 思考流程</span>
              </div>
              <ChevronDown size={14} className="text-white/20" />
            </div>

            {/* 日志流 */}
            <div ref={bodyRef} className="overflow-y-auto px-4 py-3 space-y-2" style={{ maxHeight: '58vh' }}>
              {toolMsgs.length === 0 ? (
                <div className="text-center py-6">
                  <span className="relative flex h-2 w-2 mx-auto mb-3">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-lime-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-lime-500"></span>
                  </span>
                  <p className="text-white/20 text-xs">正在唤醒 AI 策展人…</p>
                </div>
              ) : (
                toolMsgs.map((m) => {
                  const isThinking = m.type === 'thinking'
                  const Icon = TOOL_ICONS[m.agent] || Brain
                  return (
                    <motion.div
                      key={m.id}
                      initial={{ opacity: 0, x: 20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.25 }}
                      className={`flex gap-3 text-xs ${
                        isThinking
                          ? 'bg-lime-400/[0.03] rounded-xl px-3 py-2 -mx-1'
                          : 'opacity-70'
                      }`}
                    >
                      <div className={`w-4 h-4 rounded-md flex items-center justify-center shrink-0 mt-0.5 ${
                        isThinking ? 'bg-lime-400/10 text-lime-400' : 'bg-white/[0.04] text-white/25'
                      }`}>
                        <Icon size={10} />
                      </div>
                      <div className="flex-1 min-w-0">
                        {isThinking && (
                          <span className="text-white/[0.20] text-[10px]">🤔 思考</span>
                        )}
                        <p className={`mt-0.5 leading-relaxed ${
                          isThinking ? 'text-white/60 italic' : 'text-white/35'
                        }`}>
                          {m.detail}
                        </p>
                      </div>
                      <span className="text-white/[0.10] text-[10px] whitespace-nowrap self-start">
                        {m.time}
                      </span>
                    </motion.div>
                  )
                })
              )}
            </div>
          </motion.div>
        ) : (
          <motion.button
            key="btn"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            onClick={() => setOpen(true)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-full bg-black/60 backdrop-blur-xl border border-white/10 text-white/45 hover:text-white/70 hover:border-white/20 transition-all shadow-lg shadow-black/40"
          >
            <div className={`w-2 h-2 rounded-full ${toolMsgs.length > 0 ? 'bg-lime-400 animate-pulse' : 'bg-white/20'}`} />
            <Sparkles size={14} className="text-lime-400/70" />
            {toolMsgs.length > 0 && (
              <span className="text-[11px] font-medium text-white/60">
                {toolMsgs.length} 步
              </span>
            )}
          </motion.button>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
