import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { TrendingUp, TrendingDown, Zap } from 'lucide-react'
import { usePriceStore } from '@/stores/priceStore'
import { useStrategyStore } from '@/stores/strategyStore'
import { useWebSocket } from '@/hooks/useWebSocket'
import { DEFAULT_DASHBOARD_SYMBOLS, formatQuoteCurrency, normalizeMarketSymbol } from '@/utils/market'

interface PriceCardProps {
  symbol: string
  price: number
  change: number
}

function PriceCard({ symbol, price, change }: PriceCardProps) {
  const isUp = change >= 0
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-400">{symbol}</span>
        <span className={`flex items-center gap-1 text-xs font-medium ${isUp ? 'text-emerald-400' : 'text-red-400'}`}>
          {isUp ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
          {isUp ? '+' : ''}{change.toFixed(2)}%
        </span>
      </div>
      <div className="text-xl font-bold text-white">
        {price > 0 ? formatQuoteCurrency(price) : '--'}
      </div>
    </div>
  )
}

export default function Dashboard() {
  useWebSocket()
  const prices = usePriceStore((s) => s.prices)
  const changes = usePriceStore((s) => s.changes)
  const wsConnected = usePriceStore((s) => s.wsConnected)
  const strategies = useStrategyStore((s) => s.strategies)
  const fetchStrategies = useStrategyStore((s) => s.fetchStrategies)

  useEffect(() => {
    void fetchStrategies()
  }, [fetchStrategies])

  const activeStrategies = strategies.filter((s) => s.is_active)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-white">대시보드</h1>
        <div className={`flex items-center gap-2 text-xs px-3 py-1 rounded-full border ${wsConnected ? 'bg-emerald-900/30 text-emerald-400 border-emerald-800' : 'bg-gray-800 text-gray-500 border-gray-700'}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${wsConnected ? 'bg-emerald-400 animate-pulse' : 'bg-gray-500'}`} />
          {wsConnected ? '실시간 연결' : '연결 중...'}
        </div>
      </div>

      {/* 실시간 가격 */}
      <section>
        <h2 className="text-sm font-medium text-gray-400 mb-3">실시간 시세</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {DEFAULT_DASHBOARD_SYMBOLS.map((sym) => (
            <Link key={sym} to={`/chart/${sym}`}>
              <PriceCard symbol={normalizeMarketSymbol(sym)} price={prices[sym] || 0} change={changes[sym] || 0} />
            </Link>
          ))}
        </div>
      </section>

      {/* 전략 현황 */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-medium text-gray-400">전략 실행 현황</h2>
          <Link to="/strategies" className="text-xs text-blue-400 hover:text-blue-300">전체 보기 →</Link>
        </div>
        {strategies.length === 0 ? (
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-6 text-center text-gray-500">
            <Zap size={24} className="mx-auto mb-2 opacity-50" />
            <p className="text-sm">등록된 전략이 없습니다.</p>
            <Link to="/strategies" className="inline-block mt-2 text-xs text-blue-400 hover:text-blue-300">전략 추가하기</Link>
          </div>
        ) : (
          <div className="space-y-2">
            {strategies.slice(0, 5).map((s) => (
              <div key={s.id} className="flex items-center justify-between bg-gray-800 border border-gray-700 rounded-lg px-4 py-3">
                <div>
                  <span className="font-medium text-white text-sm">{s.name}</span>
                  <span className="ml-2 text-xs text-gray-400">{s.symbol} · {s.timeframe}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs px-2 py-0.5 rounded-full border ${s.is_active ? 'bg-emerald-900/30 text-emerald-400 border-emerald-800' : 'bg-gray-700 text-gray-500 border-gray-700'}`}>
                    {s.is_active ? '● 활성' : '○ 정지'}
                  </span>
                  <span className="text-xs text-gray-500">AI: {s.ai_mode === 'off' ? '끄기' : s.ai_mode}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* 통계 요약 */}
      <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: '전체 전략', value: strategies.length, color: 'text-white' },
          { label: '활성 전략', value: activeStrategies.length, color: 'text-emerald-400' },
          { label: 'AI 자문 ON', value: strategies.filter((s) => s.ai_mode !== 'off').length, color: 'text-blue-400' },
          { label: '실시간 연결', value: wsConnected ? '정상' : '끊김', color: wsConnected ? 'text-emerald-400' : 'text-red-400' },
        ].map((stat) => (
          <div key={stat.label} className="bg-gray-800 border border-gray-700 rounded-lg p-4">
            <p className="text-xs text-gray-400 mb-1">{stat.label}</p>
            <p className={`text-2xl font-bold ${stat.color}`}>{stat.value}</p>
          </div>
        ))}
      </section>
    </div>
  )
}
