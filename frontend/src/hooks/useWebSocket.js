import { useState, useRef, useCallback } from 'react'

// HTTPS 环境自动用 wss
const WS_URL = `ws${location.protocol === 'https:' ? 's' : ''}://${window.location.host}/ws/generate`

export function useWebSocket() {
  const [statuses, setStatuses] = useState({})
  const [messages, setMessages] = useState([])
  const [gameCode, setGameCode] = useState(null)
  const [error, setError] = useState(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const wsRef = useRef(null)
  const logIdRef = useRef(0)
  const generatingRef = useRef(false)  // 避免 stale closure

  const sendEvent = useCallback((eventText) => {
    if (!eventText.trim()) return

    // 关闭旧的 socket
    if (wsRef.current) {
      wsRef.current.close()
    }

    // Reset state
    setStatuses({})
    setMessages([])
    setGameCode(null)
    setError(null)
    setIsGenerating(true)
    generatingRef.current = true

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      ws.send(JSON.stringify({ event: eventText }))
    }

    ws.onmessage = (event) => {
      try {
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
            generatingRef.current = false
            break

          case 'generation_failed':
            setError({
              reason: data.reason || '生成失败',
              suggestions: data.suggestions || [],
            })
            setIsGenerating(false)
            generatingRef.current = false
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
            setMessages(prev => [...prev, {
              id: ++logIdRef.current,
              time: new Date().toLocaleTimeString(),
              agent: 'reviewer',
              detail: `❌ 审查不通过 → 退回重做: ${data.feedback?.slice(0, 80) || ''}`,
            }])
            break
        }
      } catch (e) {
        // 忽略无法解析的消息帧
        setMessages(prev => [...prev, {
          id: ++logIdRef.current,
          time: new Date().toLocaleTimeString(),
          agent: 'system',
          detail: `消息解析失败: ${e.message}`,
        }])
      }
    }

    ws.onerror = () => {
      setError({ reason: 'WebSocket 连接失败，请确认后端已启动', suggestions: [] })
      setIsGenerating(false)
      generatingRef.current = false
    }

    ws.onclose = () => {
      // 用 ref 避免 stale closure
      if (generatingRef.current) {
        setIsGenerating(false)
        generatingRef.current = false
      }
    }
  }, [])

  const cancel = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setIsGenerating(false)
    generatingRef.current = false
  }, [])

  return { statuses, messages, gameCode, error, isGenerating, sendEvent, cancel }
}
