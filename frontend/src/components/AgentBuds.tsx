import { motion } from 'framer-motion'

interface Agent { key:string; name:string }
interface Status { status:'idle'|'running'|'done'|'failed'; message:string; retries:number }

// Scattered along trunk,避开游戏面板中心区域 (top:56%, left:50%),不同水平线
const POSITIONS = [
  { top:'54%', left:'12%' },
  { top:'62%', left:'23%' },
  { top:'51%', left:'32%' },
  { top:'63%', left:'68%' },
  { top:'53%', left:'77%' },
  { top:'60%', left:'89%' },
]

// Silver lightning bolt SVG path
function LightningBolt() {
  return (
    <svg width="14" height="22" viewBox="0 0 14 22" fill="none">
      <path
        d="M8 0L0 12H5L3 22L14 8H8L10 0H8Z"
        fill="rgba(220,220,240,0.9)"
        style={{ filter:'drop-shadow(0 0 4px rgba(200,200,255,0.7)) drop-shadow(0 0 8px rgba(180,180,255,0.4))' }}
      />
    </svg>
  )
}

export function AgentBuds({ agents, statuses }: { agents:Agent[]; statuses:Record<string,Status> }) {
  return (
    <>
      {agents.map((agent, i) => {
        const s = statuses[agent.key]
        const isRunning = s?.status === 'running'
        const isDone    = s?.status === 'done'
        const isFailed  = s?.status === 'failed'
        const { top, left } = POSITIONS[i]

        return (
          <div key={agent.key} className="absolute flex flex-col items-center gap-1"
            style={{ top, left, transform:'translate(-50%,-50%)' }}>

            {/* ── 休眠点（树皮色，几乎不可见）── */}
            <motion.div className="relative flex items-center justify-center"
              initial={{ opacity:0 }}
              animate={{ opacity:1 }}
              transition={{ delay:i*0.08 }}>
              {/* Glow ring: running */}
              {isRunning && (
                <motion.div className="absolute rounded-full"
                  style={{
                    width:24, height:24,
                    background:'radial-gradient(circle, rgba(200,200,240,0.25) 0%, transparent 70%)',
                  }}
                  animate={{ scale:[1,1.5,1], opacity:[0.5,0.2,0.5] }}
                  transition={{ duration:1.8, repeat:Infinity, ease:'easeInOut' }}
                />
              )}

              {/* Done: silver glow aura */}
              {isDone && (
                <div className="absolute rounded-full"
                  style={{
                    width:20, height:20,
                    background:'radial-gradient(circle, rgba(200,200,240,0.15) 0%, transparent 70%)',
                    boxShadow:'0 0 10px rgba(180,180,230,0.2)',
                  }} />
              )}

              {/* The shape itself */}
              <motion.div
                animate={isRunning ? {
                  scale:[1, 1.2, 0.95, 1.15, 1],
                  opacity:[0.6, 1, 0.8, 1, 0.6],
                } : {}}
                transition={isRunning ? { duration:1.2, repeat:Infinity, ease:'easeInOut' } : {}}
              >
                {isDone ? (
                  <LightningBolt />
                ) : isFailed ? (
                  <div style={{
                    width:5, height:8,
                    background:'radial-gradient(ellipse at 50% 40%, #441111, #1a0000)',
                    borderRadius:'50% 50% 50% 50% / 60% 60% 40% 40%',
                    boxShadow:'0 0 4px rgba(255,40,40,0.3)',
                  }} />
                ) : isRunning ? (
                  <div style={{
                    width:6, height:9,
                    background:'radial-gradient(ellipse at 40% 30%, rgba(220,220,250,0.9), rgba(180,180,220,0.5))',
                    borderRadius:'50% 50% 50% 50% / 60% 60% 40% 40%',
                    boxShadow:'0 0 8px 2px rgba(200,200,240,0.5)',
                    transition:'all 0.5s ease',
                  }} />
                ) : (
                  /* 休眠：树皮色小点，几乎看不见 */
                  <div style={{
                    width:4, height:5,
                    background:'#2a2218',
                    borderRadius:'50%',
                    opacity:0.4,
                  }} />
                )}
              </motion.div>
            </motion.div>

            {/* 名字 */}
            <span className="text-[9px] tracking-[0.06em] font-medium whitespace-nowrap"
              style={{
                color: isDone ? 'rgba(240,240,255,0.9)' : isRunning ? 'rgba(230,230,255,0.7)' : isFailed ? 'rgba(255,120,120,0.5)' : 'rgba(255,255,255,0.1)',
                textShadow: isDone ? '0 0 6px rgba(200,200,240,0.5)' : isRunning ? '0 0 4px rgba(200,200,240,0.3)' : 'none',
              }}>
              {agent.name}
            </span>

            {/* Retry badge */}
            {s?.retries > 0 && (
              <span className="absolute -top-1 -right-1 w-3.5 h-3.5 rounded-full bg-red-500 text-[7px] font-bold text-white flex items-center justify-center"
                style={{ boxShadow:'0 0 5px rgba(239,68,68,0.5)' }}>
                {s.retries}
              </span>
            )}
          </div>
        )
      })}
    </>
  )
}
