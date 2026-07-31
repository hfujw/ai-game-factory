import { useState, useEffect, useRef } from 'react'

export default function EventLog({ messages }) {
  const [isOpen, setIsOpen] = useState(true)
  const bodyRef = useRef(null)

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (bodyRef.current && isOpen) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight
    }
  }, [messages, isOpen])

  return (
    <section className="event-log glass-card-light">
      <div className="event-log-header" onClick={() => setIsOpen(!isOpen)}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <h3>决策轨迹</h3>
          {messages.length > 0 && (
            <span className="log-count">{messages.length}</span>
          )}
        </div>
        <span className="toggle" style={{ transform: isOpen ? 'rotate(0deg)' : 'rotate(-90deg)' }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </span>
      </div>
      {isOpen && (
        <div className="event-log-body" ref={bodyRef}>
          {messages.length === 0 ? (
            <div className="log-entry" style={{ justifyContent: 'center', padding: '16px 0' }}>
              <span className="detail" style={{ color: 'var(--text-muted)' }}>等待 Agent 开始工作…</span>
            </div>
          ) : (
            messages.map((m) => (
              <div key={m.id} className="log-entry">
                <span className="time">{m.time}</span>
                <span className="agent-name">[{m.agent}]</span>
                <span className="detail">{m.detail}</span>
              </div>
            ))
          )}
        </div>
      )}
    </section>
  )
}
