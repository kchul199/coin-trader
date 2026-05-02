import { useEffect, useRef } from 'react'
import { usePriceStore } from '@/stores/priceStore'
import { useNotificationStore } from '@/stores/notificationStore'
import { useStrategyStore } from '@/stores/strategyStore'

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws'

type WebSocketMessage = {
  type: string
  [key: string]: unknown
}

function isWebSocketMessage(value: unknown): value is WebSocketMessage {
  return (
    typeof value === 'object' &&
    value !== null &&
    'type' in value &&
    typeof value.type === 'string'
  )
}

function getStringField(message: WebSocketMessage, key: string) {
  const value = message[key]
  return typeof value === 'string' ? value : undefined
}

function getNumberField(message: WebSocketMessage, key: string) {
  const value = message[key]
  return typeof value === 'number' ? value : undefined
}

export function useWebSocket() {
  const ws = useRef<WebSocket | null>(null)
  const updatePrice = usePriceStore((s) => s.updatePrice)
  const setWsConnected = usePriceStore((s) => s.setWsConnected)
  const addNotification = useNotificationStore((s) => s.add)
  const fetchStrategies = useStrategyStore((s) => s.fetchStrategies)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    let isUnmounted = false

    const connect = () => {
      if (isUnmounted) return
      ws.current = new WebSocket(WS_URL)

      ws.current.onopen = () => {
        setWsConnected(true)
        if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      }

      ws.current.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data) as unknown
          if (!isWebSocketMessage(msg)) return
          handleMessage(msg)
        } catch (error) {
          console.warn('Failed to parse websocket message', error)
        }
      }

      ws.current.onclose = () => {
        setWsConnected(false)
        if (!isUnmounted) {
          reconnectTimer.current = setTimeout(connect, 5000)
        }
      }

      ws.current.onerror = () => {
        ws.current?.close()
      }
    }

    const handleMessage = (msg: WebSocketMessage) => {
      switch (msg.type) {
        case 'price_update': {
          const symbol = getStringField(msg, 'symbol')
          const price = getNumberField(msg, 'price')
          const change = getNumberField(msg, 'change_24h')

          if (symbol && price != null && change != null) {
            updatePrice(symbol, price, change)
          }
          break
        }

        case 'order_filled': {
          const symbol = getStringField(msg, 'symbol')
          const side = getStringField(msg, 'side')
          const filledQuantity = getNumberField(msg, 'filled_quantity')
          const avgFillPrice = getNumberField(msg, 'avg_fill_price')
          if (!symbol || !side || filledQuantity == null || avgFillPrice == null) break
          addNotification({
            type: 'order_filled',
            title: '주문 체결',
            message: `${symbol} ${side === 'buy' ? '매수' : '매도'} ${filledQuantity} @ ${avgFillPrice}`,
            strategyId: getStringField(msg, 'strategy_id'),
          })
          break
        }

        case 'order_created': {
          const symbol = getStringField(msg, 'symbol')
          const side = getStringField(msg, 'side')
          if (!symbol || !side) break
          addNotification({
            type: 'order_created',
            title: '주문 생성',
            message: `${symbol} ${side === 'buy' ? '매수' : '매도'} 주문이 생성되었습니다.`,
            strategyId: getStringField(msg, 'strategy_id'),
          })
          break
        }

        case 'order_failed': {
          const error = getStringField(msg, 'error')
          if (!error) break
          addNotification({
            type: 'order_failed',
            title: '주문 실패',
            message: `주문 실패: ${error}`,
            strategyId: getStringField(msg, 'strategy_id'),
          })
          break
        }

        case 'emergency_stop': {
          const reason = getStringField(msg, 'reason')
          if (!reason) break
          addNotification({
            type: 'emergency_stop',
            title: '⚠️ 긴급 정지',
            message: `전략 긴급 정지: ${reason}`,
            strategyId: getStringField(msg, 'strategy_id'),
          })
          void fetchStrategies()
          break
        }

        case 'ai_advice': {
          const decision = getStringField(msg, 'decision')
          const confidence = getNumberField(msg, 'confidence')
          if (!decision || confidence == null) break
          addNotification({
            type: 'ai_advice',
            title: 'AI 자문 업데이트',
            message: `결정: ${decision} (신뢰도 ${confidence}%)`,
            strategyId: getStringField(msg, 'strategy_id'),
          })
          break
        }

        case 'system_notice': {
          const title = getStringField(msg, 'title')
          const message = getStringField(msg, 'message')
          const level = getStringField(msg, 'level')
          if (!title || !message) break
          addNotification({
            type: level === 'error' ? 'error' : 'info',
            title,
            message,
          })
          break
        }
      }
    }

    connect()
    return () => {
      isUnmounted = true
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      ws.current?.close()
    }
  }, [addNotification, fetchStrategies, setWsConnected, updatePrice])
}
