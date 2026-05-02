import client from '../client'
import { Candle, TickerSnapshot } from '../../types'

export const chartApi = {
  candles: (symbol: string, tf: string, limit = 200) =>
    client.get<Candle[]>(`/chart/${symbol}/candles`, { params: { tf, limit } }),
  ticker: (symbol: string) =>
    client.get<TickerSnapshot>(`/chart/${symbol}/ticker`),
}
