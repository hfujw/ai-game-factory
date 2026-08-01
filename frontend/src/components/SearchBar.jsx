import { useState, useEffect } from 'react'

export default function SearchBar({ onGenerate, isGenerating, onCancel }) {
  const [input, setInput] = useState('')
  const [events, setEvents] = useState([])
  const [eventsLoading, setEventsLoading] = useState(true)

  useEffect(() => {
    fetch('/api/events')
      .then(r => r.json())
      .then(d => setEvents(d.events || []))
      .catch(() => {})
      .finally(() => setEventsLoading(false))
  }, [])

  const handleSubmit = (e) => {
    e?.preventDefault()
    if (input.trim() && !isGenerating) {
      onGenerate(input.trim())
    }
  }

  const handleChipClick = (eventName) => {
    setInput(eventName)
    if (!isGenerating) {
      onGenerate(eventName)
    }
  }

  return (
    <section className="search-section glass-card">
      <form className="search-row" onSubmit={handleSubmit}>
        <svg className="search-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--text-muted)', flexShrink: 0 }}>
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <input
          className="search-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="输入一个计算机历史事件，例如：1991年 Linus 写下了 Linux 的第一行代码"
          disabled={isGenerating}
        />
        <button
          type="submit"
          className="search-btn"
          disabled={isGenerating || !input.trim()}
        >
          {isGenerating ? '生成中…' : '⚡ 生成游戏'}
        </button>
        {isGenerating && onCancel && (
          <button type="button" className="cancel-btn" onClick={onCancel}>
            取消
          </button>
        )}
      </form>
      <div className="event-chips">
        {eventsLoading ? (
          <span style={{ color: 'rgba(255,255,255,0.3)', fontSize: '13px' }}>加载推荐事件…</span>
        ) : events.length === 0 ? (
          <span style={{ color: 'rgba(255,255,255,0.3)', fontSize: '13px' }}>无法加载推荐事件</span>
        ) : (
          events.slice(0, 5).map((e) => (
            <button
              key={e.name}
              className="chip"
              onClick={() => handleChipClick(e.name)}
              disabled={isGenerating}
              aria-label={`生成: ${e.name}`}
            >
              {e.name.length > 28 ? e.name.slice(0, 28) + '…' : e.name}
            </button>
          ))
        )}
      </div>
    </section>
  )
}
