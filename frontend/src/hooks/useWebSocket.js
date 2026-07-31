import { useState, useRef, useCallback } from 'react'

// 走 Vite proxy：/ws → localhost:8000（开发），生产环境直连同域
const WS_URL = `ws://${window.location.host}/ws/generate`

export function useWebSocket() {
  const [statuses, setStatuses] = useState({})
  const [messages, setMessages] = useState([])
  const [gameCode, setGameCode] = useState(null)
  const [error, setError] = useState(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const wsRef = useRef(null)
  const logIdRef = useRef(0)

  const sendEvent = useCallback((eventText) => {
    if (!eventText.trim()) return

    // Reset state
    setStatuses({})
    setMessages([])
    setGameCode(null)
    setError(null)
    setIsGenerating(true)

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      ws.send(JSON.stringify({ event: eventText }))
    }

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)

      switch (data.type) {
        case 'agent_progress':
          setStatuses(prev => ({
            ...prev,
            [data.agent]: {
              status: data.status,
              message: data.message,
              retries: (prev[data.agent]?.retries || 0),
            },
          }))
          setMessages(prev => [...prev, {
            id: ++logIdRef.current,
            time: new Date().toLocaleTimeString(),
            agent: data.agent,
            detail: data.message,
          }])
          break

        case 'game_ready':
          setGameCode(data.game_code)
          setIsGenerating(false)
          break

        case 'generation_failed':
          setError({
            reason: data.reason || '生成失败',
            suggestions: data.suggestions || [],
          })
          setIsGenerating(false)
          break

        case 'agent_log':
          setMessages(prev => [...prev, {
            id: ++logIdRef.current,
            time: new Date().toLocaleTimeString(),
            agent: data.agent,
            detail: `${data.action}: ${data.detail}`,
          }])
          break

        case 'review_rejected':
          setStatuses(prev => {
            const coder = prev['coder'] || {}
            return {
              ...prev,
              coder: { ...coder, status: 'running', retries: (coder.retries || 0) + 1 },
            }
          })
          setMessages(prev => [...prev, {
            id: ++logIdRef.current,
            time: new Date().toLocaleTimeString(),
            agent: 'reviewer',
            detail: `❌ 审查不通过 → 退回重做: ${data.feedback?.slice(0, 80) || ''}`,
          }])
          break

        default:
          break
      }
    }

    ws.onerror = () => {
      setError({ reason: 'WebSocket 连接失败，请确认后端已启动', suggestions: [] })
      setIsGenerating(false)
    }

    ws.onclose = () => {
      if (isGenerating) {
        setIsGenerating(false)
      }
    }
  }, [])

  const cancel = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setIsGenerating(false)
  }, [])

  return { statuses, messages, gameCode, error, isGenerating, sendEvent, cancel }
}
