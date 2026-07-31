export default function AgentPipeline({ statuses }) {
  const AGENTS = [
    { key: 'crawler', name: '爬虫', icon: 'crawler' },
    { key: 'planner', name: '策划', icon: 'planner' },
    { key: 'writer', name: '文案', icon: 'writer' },
    { key: 'coder', name: '程序', icon: 'coder' },
    { key: 'reviewer', name: '审查', icon: 'reviewer' },
    { key: 'artist', name: '美术', icon: 'artist' },
  ]

  // SVG icons for each agent type
  const icons = {
    crawler: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
      </svg>
    ),
    planner: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 20h9" /><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
      </svg>
    ),
    writer: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
      </svg>
    ),
    coder: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="16 18 22 12 16 6" /><polyline points="8 6 2 12 8 18" />
      </svg>
    ),
    reviewer: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" /><polyline points="10 9 9 9 8 9" />
      </svg>
    ),
    artist: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" />
        <path d="M2 12l10 5 10-5" />
      </svg>
    ),
  }

  return (
    <section className="agent-pipeline glass-card-light">
      <h3>Agent 协作流水线</h3>
      <div className="pipeline-list">
        {AGENTS.map(({ key, name, icon }) => {
          const s = statuses[key] || {}
          const status = s.status || 'idle'
          return (
            <div key={key} className={`pipeline-item ${status} fade-in-up`}>
              <div className={`pipeline-icon`}>
                {icons[icon]}
              </div>
              <div className="pipeline-info">
                <div className="pipeline-name">{name}</div>
                <div className="pipeline-status">
                  {s.message || '等待中…'}
                </div>
              </div>
              {s.retries > 0 && (
                <div className="pipeline-retry">{s.retries}</div>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}
