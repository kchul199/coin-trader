import { useEffect, useRef } from 'react'
import { usePriceStore } from '@/stores/priceStore'
import { useNotificationStore } from '@/stores/notificationStore'
import { useStrategyStore } from '@/stores/strategyStore'

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws'

export function useWebSocket() {
  const ws = useRef<WebSocket | null>(null)
  const { updatePrice, setWsConnected } = usePriceStore()
  const { add: addNotification } = useNotificationStore()
  const { fetchStrategies } = useStrategyStore()
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    const connect = () => {
      ws.current = new WebSocket(WS_URL)

      ws.current.onopen = () => {
        setWsConnected(true)
        if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      }

      ws.current.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          handleMessage(msg)
        } catch {}
      }

      ws.current.onclose = () => {
        setWsConnected(false)
        reconnectTimer.current = setTimeout(connect, 5000)
      }

      ws.current.onerror = () => {
        ws.current?.close()
      }
    }

    const handleMessage = (msg: any) => {
      switch (msg.type) {
        case 'price_update':
          updatePrice(msg.symbol, msg.price, msg.change_24h)
          break

        case 'order_filled':
          addNotification({
            type: 'order_filled',
            title: '주문 체결',
            message: `${msg.symbol} ${msg.side === 'buy' ? '매수' : '매도'} ${msg.filled_quantity} @ ${msg.avg_fill_price}`,
            strategyId: msg.strategy_id,
          })
          break

        case 'order_created':
          addNotification({
            type: 'order_created',
            title: '주문 생성',
            message: `${msg.symbol} ${msg.side === 'buy' ? '매수' : '매도'} 주문이 생성되었습니다.`,
            strategyId: msg.strategy_id,
          })
          break

        case 'order_failed':
          addNotification({
            type: 'order_failed',
            title: '주문 실패',
            message: `주문 실패: ${msg.error}`,
            strategyId: msg.strategy_id,
          })
          break

        case 'emergency_stop':
          addNotification({
            type: 'emergency_stop',
            title: '⚠️ 긴급 정지',
            message: `전략 긴급 정지: ${msg.reason}`,
            strategyId: msg.strategy_id,
          })
          // 전략 목록 갱신
          fetchStrategies()
          break

        case 'ai_advice':
          addNotification({
            type: 'ai_advice',
            title: 'AI 자문 업데이트',
            message: `결정: ${msg.decision} (신뢰도 ${msg.confidence}%)`,
            strategyId: msg.strategy_id,
          })
          break
      }
    }

    connect()
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      ws.current?.close()
    }
  }, [])
}
