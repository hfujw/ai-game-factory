import { motion } from 'framer-motion'

interface Agent { key:string; name:string }
interface Status { status:'idle'|'running'|'done'|'failed'; message:string; retries:number }

function LightningBolt() {
  return (
    <svg width="12" height="18" viewBox="0 0 14 22" fill="none">
      <path
        d="M8 0L0 12H5L3 22L14 8H8L10 0H8Z"
        fill="rgba(220,220,240,0.9)"
        style={{ filter:'drop-shadow(0 0 4px rgba(200,200,255,0.7)) drop-shadow(0 0 8px rgba(180,180,255,0.4))' }}
      />
    </svg>
  )
}

export function AgentBuds({ agents, statuses }: { agents:Agent[]; statuses:Record<string,Status> }) {
  const anyActive = Object.values(statuses).some(s => s.status !== 'idle')

  return (
    <div className="flex items-center justify-center gap-6">
      {agents.map((agent, i) => {
        const s = statuses[agent.key]
        const isRunning = s?.status === 'running'
        const isDone    = s?.status === 'done'
        const isFailed  = s?.status === 'failed'

        return (
          <motion.div
            key={agent.key}
            className="flex flex-col items-center gap-1.5"
            initial={{ opacity:0, y:8 }}
            animate={{ opacity: anyActive ? 1 : 0.3, y:0 }}
            transition={{ delay: i * 0.06 }}
          >
            <motion.div className="relative flex items-center justify-center">
              {/* Glow ring: running */}
              {isRunning && (
                <motion.div className="absolute rounded-full"
                  style={{ width:18, height:18,
                    background:'radial-gradient(circle, rgba(200,200,240,0.25) 0%, transparent 70%)' }}
                  animate={{ scale:[1,1.4,1], opacity:[0.5,0.2,0.5] }}
                  transition={{ duration:1.8, repeat:Infinity, ease:'easeInOut' }}
                />
              )}

              {isDone && (
                <div className="absolute rounded-full"
                  style={{ width:14, height:14,
                    background:'radial-gradient(circle, rgba(200,200,240,0.12) 0%, transparent 70%)',
                    boxShadow:'0 0 8px rgba(180,180,230,0.15)' }} />
              )}

              <motion.div
                animate={isRunning ? {
                  scale:[1, 1.15, 0.95, 1.1, 1],
                  opacity:[0.6, 1, 0.8, 1, 0.6],
                } : {}}
                transition={isRunning ? { duration:1.2, repeat:Infinity, ease:'easeInOut' } : {}}
              >
                {isDone ? (
                  <LightningBolt />
                ) : isFailed ? (
                  <div style={{ width:4, height:6,
                    background:'radial-gradient(ellipse at 50% 40%, #441111, #1a0000)',
                    borderRadius:'50% 50% 50% 50% / 60% 60% 40% 40%',
                    boxShadow:'0 0 3px rgba(255,40,40,0.25)' }} />
                ) : isRunning ? (
                  <div style={{ width:5, height:7,
                    background:'radial-gradient(ellipse at 40% 30%, rgba(220,220,250,0.9), rgba(180,180,220,0.5))',
                    borderRadius:'50% 50% 50% 50% / 60% 60% 40% 40%',
                    boxShadow:'0 0 6px 2px rgba(200,200,240,0.5)' }} />
                ) : (
                  <div style={{ width:3, height:4,
                    background:'#fff', borderRadius:'50%', opacity:0.15 }} />
                )}
              </motion.div>
            </motion.div>

            <span className="text-[9px] tracking-[0.06em] font-medium whitespace-nowrap"
              style={{
                color: isDone ? 'rgba(240,240,255,0.85)' : isRunning ? 'rgba(230,230,255,0.65)' : isFailed ? 'rgba(255,120,120,0.45)' : 'rgba(255,255,255,0.20)',
                textShadow: isDone ? '0 0 5px rgba(200,200,240,0.4)' : isRunning ? '0 0 3px rgba(200,200,240,0.2)' : 'none',
              }}>
              {agent.name}
            </span>

            {s?.retries > 0 && (
              <span className="absolute -top-0.5 -right-0.5 w-3 h-3 rounded-full bg-red-500 text-[6px] font-bold text-white flex items-center justify-center"
                style={{ boxShadow:'0 0 4px rgba(239,68,68,0.4)' }}>
                {s.retries}
              </span>
            )}
          </motion.div>
        )
      })}
    </div>
  )
}
