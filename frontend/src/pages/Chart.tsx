import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useCandles } from '@/hooks/useCandles'
import { usePriceStore } from '@/stores/priceStore'
import { CandleChart } from '@/components/chart/CandleChart'

const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
const TIMEFRAMES = ['1m', '5m', '15m', '30m', '1h', '4h', '1d']

export default function Chart() {
  const { symbol: paramSymbol } = useParams<{ symbol: string }>()
  const [symbol, setSymbol] = useState(paramSymbol || 'BTCUSDT')
  const [timeframe, setTimeframe] = useState('1h')
  const { candles, loading, error } = useCandles(symbol, timeframe)
  const prices = usePriceStore((s) => s.prices)
  const changes = usePriceStore((s) => s.changes)

  const currentPrice = prices[symbol] || prices[symbol.replace('USDT', '/USDT')] || 0
  const change = changes[symbol] || 0

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-white">차트 분석</h1>
        <div className="flex gap-2">
          <select
            className="bg-gray-800 text-white text-sm rounded px-3 py-1.5 border border-gray-700"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
          >
            {SYMBOLS.map((s) => <option key={s}>{s}</option>)}
          </select>
          <div className="flex bg-gray-800 border border-gray-700 rounded overflow-hidden">
            {TIMEFRAMES.map((tf) => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                className={`px-3 py-1.5 text-sm transition-colors ${
                  timeframe === tf
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-400 hover:text-white hover:bg-gray-700'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>
        </div>
      </div>

      {currentPrice > 0 && (
        <div className="flex items-center gap-4 bg-gray-800 rounded-lg p-3 border border-gray-700">
          <span className="text-2xl font-bold text-white">${currentPrice.toLocaleString()}</span>
          <span className={`text-sm font-medium ${change >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
            {change >= 0 ? '+' : ''}{change.toFixed(2)}%
          </span>
        </div>
      )}

      <div className="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-96 text-gray-400">
            <div className="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full mr-2" />
            데이터 로딩 중...
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-96 text-red-400">
            데이터 로드 실패: {error}
          </div>
        ) : (
          <CandleChart candles={candles} symbol={symbol} height={450} />
        )}
      </div>
    </div>
  )
}
