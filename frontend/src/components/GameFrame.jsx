export default function GameFrame({ gameCode }) {
  const hasGame = !!gameCode

  return (
    <section className={`game-section glass-card ${hasGame ? 'has-game' : ''}`}>
      <div className="game-section-header">
        <h3>游戏展示区</h3>
        {hasGame && <span className="game-badge">● LIVE</span>}
      </div>
      {hasGame ? (
        <iframe
          className="game-frame"
          srcDoc={gameCode}
          sandbox="allow-scripts allow-same-origin"
          title="生成的游戏"
        />
      ) : (
        <div className="game-empty">
          <div className="empty-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
              <line x1="8" y1="21" x2="16" y2="21" />
              <line x1="12" y1="17" x2="12" y2="21" />
            </svg>
          </div>
          <span className="empty-text">等待 Agent 生成游戏…</span>
          <span className="empty-sub">输入计算机历史事件，AI 将自动生成可玩的解谜游戏</span>
        </div>
      )}
    </section>
  )
}
