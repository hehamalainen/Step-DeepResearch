import { useEffect, useRef, useCallback, useState } from 'react'
import { WSEvent, WSEventType } from '../types'

interface WebSocketOptions {
  runId?: string
  onEvent?: (event: WSEvent) => void
  onConnect?: () => void
  onDisconnect?: () => void
  onError?: (error: Event) => void
  autoReconnect?: boolean
  reconnectInterval?: number
}

export function useWebSocket(options: WebSocketOptions) {
  const {
    runId,
    onEvent,
    onConnect,
    onDisconnect,
    onError,
    autoReconnect = true,
    reconnectInterval = 3000,
  } = options

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [lastEvent, setLastEvent] = useState<WSEvent | null>(null)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return
    }

    const wsUrl = runId
      ? `ws://${window.location.host}/ws/${runId}`
      : `ws://${window.location.host}/ws`

    const ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      setIsConnected(true)
      onConnect?.()
    }

    ws.onclose = () => {
      setIsConnected(false)
      onDisconnect?.()

      if (autoReconnect) {
        reconnectTimeoutRef.current = setTimeout(connect, reconnectInterval)
      }
    }

    ws.onerror = (error) => {
      onError?.(error)
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as WSEvent
        setLastEvent(data)
        onEvent?.(data)
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e)
      }
    }

    wsRef.current = ws
  }, [runId, onEvent, onConnect, onDisconnect, onError, autoReconnect, reconnectInterval])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }, [])

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  useEffect(() => {
    connect()
    return () => disconnect()
  }, [connect, disconnect])

  return {
    isConnected,
    lastEvent,
    send,
    connect,
    disconnect,
  }
}

// Hook for subscribing to specific event types
export function useWSEventSubscription(
  runId: string,
  eventTypes: WSEventType[],
  callback: (event: WSEvent) => void
) {
  const handleEvent = useCallback(
    (event: WSEvent) => {
      if (eventTypes.includes(event.event_type)) {
        callback(event)
      }
    },
    [eventTypes, callback]
  )

  return useWebSocket({
    runId,
    onEvent: handleEvent,
  })
}
