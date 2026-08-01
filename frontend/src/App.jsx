import { useWebSocket } from './hooks/useWebSocket'
import SearchBar from './components/SearchBar'
import AgentPipeline from './components/AgentPanel'
import GameFrame from './components/GameFrame'
import FailureNotice from './components/FailureNotice'
import EventLog from './components/EventLog'

export default function App() {
  const { statuses, messages, gameCode, error, isGenerating, sendEvent, cancel } = useWebSocket()

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header glass-card">
        <div className="logo">
          <div className="logo-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5 12 2" />
              <line x1="12" y1="22" x2="12" y2="15.5" />
              <polyline points="22 8.5 12 15.5 2 8.5" />
            </svg>
          </div>
          <div>
            <h1>时光像素</h1>
            <p className="tagline">6 个 AI Agent 协作，把计算机历史变成可玩的游戏</p>
          </div>
        </div>
      </header>

      {/* Main: Search + Game */}
      <main className="main-content">
        <SearchBar onGenerate={sendEvent} isGenerating={isGenerating} onCancel={cancel} />
        <FailureNotice error={error} onRetry={sendEvent} />
        <GameFrame gameCode={gameCode} />
      </main>

      {/* Sidebar: Pipeline + Log */}
      <aside className="sidebar">
        <AgentPipeline statuses={statuses} />
        <EventLog messages={messages} />
      </aside>

      {/* Footer */}
      <footer className="app-footer">
        Powered by DeepSeek · LangGraph · FastAPI · React
      </footer>
    </div>
  )
}
