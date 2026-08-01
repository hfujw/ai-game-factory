import { Component, ReactNode } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

export class ErrorBoundary extends Component<{ children:ReactNode }, { hasError:boolean; error:Error|null }> {
  constructor(props:{ children:ReactNode }) {
    super(props)
    this.state = { hasError:false, error:null }
  }
  static getDerivedStateFromError(error:Error) { return { hasError:true, error } }
  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-dvh bg-black flex items-center justify-center p-8">
          <div className="text-center">
            <div className="w-14 h-14 mx-auto mb-5 rounded-2xl bg-red-500/8 flex items-center justify-center">
              <AlertTriangle className="w-6 h-6 text-red-400" />
            </div>
            <h2 className="text-white/70 text-lg font-semibold mb-2">界面渲染出错</h2>
            <p className="text-white/25 text-sm mb-5">{this.state.error?.message||'未知错误'}</p>
            <button onClick={() => window.location.reload()}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-2xl text-white/50 hover:text-white hover:bg-white/[0.08] transition-all text-sm">
              <RefreshCw className="w-4 h-4" />刷新页面
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
