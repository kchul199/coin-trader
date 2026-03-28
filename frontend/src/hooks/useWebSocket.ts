import { useEffect, useRef } from 'react'
import { usePriceStore } from '@/stores/priceStore'

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws'

export function useWebSocket() {
  const ws = useRef<WebSocket | null>(null)
  const { updatePrice, setWsConnected } = usePriceStore()
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
          if (msg.type === 'price_update') {
            updatePrice(msg.symbol, msg.price, msg.change_24h)
          }
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

    connect()
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      ws.current?.close()
    }
  }, [])
}
