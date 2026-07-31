export default function AgentAvatar({ name, icon, status, message, retries }) {
  const statusClass = status || 'idle'

  return (
    <div className={`agent-avatar ${statusClass === 'running' ? 'active' : ''} ${statusClass}`}>
      {message && <div className="agent-bubble">{message}</div>}
      {retries > 0 && <div className="retry-badge">{retries}</div>}
      <div className="agent-icon">{icon}</div>
      <div className="agent-name">{name}</div>
      <div className={`status-dot ${statusClass}`} />
    </div>
  )
}
