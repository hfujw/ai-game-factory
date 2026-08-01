import { Component } from 'react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          minHeight: '100dvh', background: 'var(--bg-root, #0A0A0F)',
          color: 'rgba(255,255,255,0.7)', fontFamily: 'system-ui, sans-serif',
          textAlign: 'center', padding: '2rem',
        }}>
          <div>
            <h2 style={{ marginBottom: '0.5rem', color: '#FF375F' }}>界面渲染出错</h2>
            <p style={{ fontSize: '0.9rem', marginBottom: '1rem' }}>
              {this.state.error?.message || '未知错误'}
            </p>
            <button
              onClick={() => window.location.reload()}
              style={{
                padding: '0.5rem 1.5rem', border: '1px solid rgba(255,255,255,0.3)',
                background: 'rgba(255,255,255,0.1)', color: '#fff', borderRadius: '8px',
                cursor: 'pointer', fontSize: '0.9rem',
              }}
            >
              刷新页面
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
