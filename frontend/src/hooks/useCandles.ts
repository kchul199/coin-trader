import { useState, useEffect } from 'react'
import { Candle } from '@/types'
import { chartApi } from '@/api/endpoints/chart'

export function useCandles(symbol: string, timeframe: string) {
  const [candles, setCandles] = useState<Candle[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!symbol) return
    setLoading(true)
    chartApi.candles(symbol, timeframe)
      .then((res) => {
        setCandles(res.data)
        setLoading(false)
      })
      .catch((e) => {
        setError(e.message)
        setLoading(false)
      })
  }, [symbol, timeframe])

  return { candles, loading, error }
}
