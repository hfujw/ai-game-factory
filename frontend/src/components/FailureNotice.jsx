export default function FailureNotice({ error, onRetry }) {
  if (!error) return null

  return (
    <section className="failure-notice glass-card fade-in-up">
      <div className="failure-notice-header">
        <div className="fail-icon">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        </div>
        <h3>生成失败</h3>
      </div>
      <p className="reason">{error.reason}</p>
      {error.suggestions.length > 0 && (
        <div className="suggestions">
          <span className="suggest-label">建议尝试：</span>
          {error.suggestions.slice(0, 4).map((s, i) => (
            <span key={i} className="chip" onClick={() => onRetry(s)}>
              {s.length > 28 ? s.slice(0, 28) + '…' : s}
            </span>
          ))}
        </div>
      )}
    </section>
  )
}
