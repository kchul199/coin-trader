import { ReactNode, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useCandles } from '@/hooks/useCandles'
import { usePriceStore } from '@/stores/priceStore'
import { useStrategyStore } from '@/stores/strategyStore'
import { CandleChart, ChartMarker, ChartPriceBand } from '@/components/chart/CandleChart'
import { ordersApi } from '@/api/endpoints/orders'
import { portfolioApi } from '@/api/endpoints/portfolio'
import type { Candle, OrderRecord, PortfolioPosition, Strategy } from '@/types'
import { DEFAULT_CHART_SYMBOLS, formatQuoteCurrency, normalizeMarketSymbol, toCompactSymbol } from '@/utils/market'

const SYMBOLS = DEFAULT_CHART_SYMBOLS
const TIMEFRAMES = ['1m', '5m', '15m', '30m', '1h', '4h', '1d']

export default function Chart() {
  const { symbol: paramSymbol } = useParams<{ symbol: string }>()
  const [symbol, setSymbol] = useState(paramSymbol || DEFAULT_CHART_SYMBOLS[0])
  const [timeframe, setTimeframe] = useState('1h')
  const [overlays, setOverlays] = useState({ ma20: true, ma50: false, ema20: true })
  const [panels, setPanels] = useState({ rsi: true, volume: true })
  const [orderMarkers, setOrderMarkers] = useState<ChartMarker[]>([])
  const [position, setPosition] = useState<PortfolioPosition | null>(null)
  const { candles, loading, error } = useCandles(symbol, timeframe)
  const prices = usePriceStore((s) => s.prices)
  const changes = usePriceStore((s) => s.changes)
  const strategies = useStrategyStore((s) => s.strategies)
  const fetchStrategies = useStrategyStore((s) => s.fetchStrategies)

  useEffect(() => {
    if (paramSymbol) {
      setSymbol(paramSymbol)
    }
  }, [paramSymbol])

  const normalizedSymbol = normalizeMarketSymbol(symbol)
  const compactSymbol = toCompactSymbol(symbol)
  const currentPrice = prices[compactSymbol] || 0
  const change = changes[compactSymbol] || 0

  useEffect(() => {
    let cancelled = false

    async function loadChartContext() {
      try {
        const [orderResponse, portfolioResponse] = await Promise.all([
          ordersApi.list(1, 100, normalizedSymbol),
          portfolioApi.list(),
        ])
        if (cancelled) {
          return
        }

        setOrderMarkers(buildOrderMarkers(orderResponse.data))
        setPosition(
          portfolioResponse.data.find((item) => normalizeMarketSymbol(item.symbol) === normalizedSymbol) || null
        )
      } catch {
        if (!cancelled) {
          setOrderMarkers([])
          setPosition(null)
        }
      }
    }

    void loadChartContext()

    return () => {
      cancelled = true
    }
  }, [normalizedSymbol])

  useEffect(() => {
    if (!strategies.length) {
      void fetchStrategies()
    }
  }, [fetchStrategies, strategies.length])

  const strategyForSymbol =
    strategies.find(
      (item) =>
        item.is_active &&
        normalizeMarketSymbol(item.symbol) === normalizedSymbol &&
        item.order_config?.side === 'buy'
    ) || null
  const fallbackPrice = candles.length ? candles[candles.length - 1].close : 0
  const referencePrice = currentPrice || fallbackPrice
  const positionSummary = buildPositionSummary(position, strategyForSymbol, referencePrice)
  const priceBands = buildPriceBands(positionSummary)
  const rsiSeries = buildRsiSeries(candles)
  const volumeBars = buildVolumeSeries(candles)

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
            {SYMBOLS.map((s) => (
              <option key={s} value={s}>
                {normalizeMarketSymbol(s)}
              </option>
            ))}
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

      <div className="flex flex-wrap gap-2">
        {[
          { key: 'ma20', label: 'MA 20' },
          { key: 'ma50', label: 'MA 50' },
          { key: 'ema20', label: 'EMA 20' },
        ].map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => setOverlays((prev) => ({ ...prev, [item.key]: !prev[item.key as keyof typeof prev] }))}
            className={`rounded-full border px-3 py-1 text-xs transition ${
              overlays[item.key as keyof typeof overlays]
                ? 'border-blue-600 bg-blue-600/20 text-blue-200'
                : 'border-gray-700 text-gray-400 hover:border-gray-500 hover:text-white'
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap gap-2">
        {[
          { key: 'rsi', label: 'RSI 패널' },
          { key: 'volume', label: '거래량 패널' },
        ].map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => setPanels((prev) => ({ ...prev, [item.key]: !prev[item.key as keyof typeof prev] }))}
            className={`rounded-full border px-3 py-1 text-xs transition ${
              panels[item.key as keyof typeof panels]
                ? 'border-emerald-600 bg-emerald-600/20 text-emerald-200'
                : 'border-gray-700 text-gray-400 hover:border-gray-500 hover:text-white'
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      {currentPrice > 0 && (
        <div className="flex items-center gap-4 bg-gray-800 rounded-lg p-3 border border-gray-700">
          <span className="text-2xl font-bold text-white">{formatQuoteCurrency(currentPrice)}</span>
          <span className={`text-sm font-medium ${change >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
            {change >= 0 ? '+' : ''}{change.toFixed(2)}%
          </span>
        </div>
      )}

      {positionSummary && (
        <section className="grid grid-cols-1 gap-3 lg:grid-cols-4">
          <OverlayCard label="보유 수량" value={positionSummary.quantity.toFixed(6)} />
          <OverlayCard
            label="평균 단가"
            value={formatQuoteCurrency(positionSummary.avgBuyPrice)}
            sub={positionSummary.strategyName ? `기준 전략: ${positionSummary.strategyName}` : undefined}
          />
          <OverlayCard
            label="미실현 손익"
            value={`${positionSummary.pnl >= 0 ? '+' : ''}${formatQuoteCurrency(positionSummary.pnl)}`}
            tone={positionSummary.pnl >= 0 ? 'gain' : 'loss'}
            sub={`${positionSummary.pnlPct >= 0 ? '+' : ''}${positionSummary.pnlPct.toFixed(2)}%`}
          />
          <OverlayCard
            label="보호 구간"
            value={positionSummary.stopLossPrice ? formatQuoteCurrency(positionSummary.stopLossPrice) : '-'}
            sub={
              [
                positionSummary.takeProfitPrice ? `익절 ${formatQuoteCurrency(positionSummary.takeProfitPrice)}` : null,
                positionSummary.trailingStopPct ? `트레일링 ${positionSummary.trailingStopPct.toFixed(1)}%` : null,
              ]
                .filter(Boolean)
                .join(' · ') || undefined
            }
          />
        </section>
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
          <CandleChart
            candles={candles}
            symbol={normalizedSymbol}
            height={450}
            overlays={overlays}
            markers={orderMarkers}
            priceBands={priceBands}
          />
        )}
      </div>

      {(panels.rsi || panels.volume) && !loading && !error && candles.length > 0 && (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {panels.rsi && (
            <IndicatorPanel
              title="RSI 14"
              subtitle={rsiSeries.length ? `최근 ${rsiSeries[rsiSeries.length - 1].toFixed(1)}` : '데이터 없음'}
            >
              <LineIndicatorSvg data={rsiSeries} min={0} max={100} referenceLines={[30, 70]} color="#38BDF8" />
            </IndicatorPanel>
          )}
          {panels.volume && (
            <IndicatorPanel
              title="거래량"
              subtitle={volumeBars.length ? `최근 ${Math.round(volumeBars[volumeBars.length - 1])}` : '데이터 없음'}
            >
              <VolumeIndicatorSvg data={volumeBars} candles={candles} />
            </IndicatorPanel>
          )}
        </div>
      )}
    </div>
  )
}

function OverlayCard({
  label,
  value,
  sub,
  tone = 'neutral',
}: {
  label: string
  value: string
  sub?: string
  tone?: 'neutral' | 'gain' | 'loss'
}) {
  const toneClass =
    tone === 'gain' ? 'text-emerald-400' : tone === 'loss' ? 'text-red-400' : 'text-white'

  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800/80 p-4">
      <p className="text-xs text-gray-400">{label}</p>
      <p className={`mt-1 text-xl font-semibold ${toneClass}`}>{value}</p>
      {sub && <p className="mt-1 text-xs text-gray-500">{sub}</p>}
    </div>
  )
}

function IndicatorPanel({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle?: string
  children: ReactNode
}) {
  return (
    <section className="rounded-xl border border-gray-700 bg-gray-900/80 p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-sm font-semibold text-white">{title}</p>
        {subtitle && <p className="text-xs text-gray-400">{subtitle}</p>}
      </div>
      {children}
    </section>
  )
}

function LineIndicatorSvg({
  data,
  min,
  max,
  referenceLines,
  color,
}: {
  data: number[]
  min: number
  max: number
  referenceLines: number[]
  color: string
}) {
  if (!data.length) {
    return <div className="flex h-28 items-center justify-center text-sm text-gray-500">데이터가 없습니다.</div>
  }

  const width = 100
  const height = 120
  const points = data
    .map((value, index) => {
      const x = data.length === 1 ? width / 2 : (index / (data.length - 1)) * width
      const y = height - ((value - min) / Math.max(max - min, 1)) * height
      return `${x},${Math.min(Math.max(y, 0), height)}`
    })
    .join(' ')

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-28 w-full">
      {referenceLines.map((line) => {
        const y = height - ((line - min) / Math.max(max - min, 1)) * height
        return (
          <line
            key={line}
            x1="0"
            x2={String(width)}
            y1={String(y)}
            y2={String(y)}
            stroke="#475569"
            strokeDasharray="3 3"
            strokeWidth="0.8"
          />
        )
      })}
      <polyline fill="none" stroke={color} strokeWidth="2" points={points} />
    </svg>
  )
}

function VolumeIndicatorSvg({ data, candles }: { data: number[]; candles: Candle[] }) {
  if (!data.length) {
    return <div className="flex h-28 items-center justify-center text-sm text-gray-500">데이터가 없습니다.</div>
  }

  const width = 100
  const height = 120
  const maxValue = Math.max(...data, 1)
  const barWidth = width / data.length

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-28 w-full">
      {data.map((value, index) => {
        const normalizedHeight = (value / maxValue) * height
        const y = height - normalizedHeight
        const candle = candles[index]
        const rising = candle ? candle.close >= candle.open : true
        return (
          <rect
            key={`${value}-${index}`}
            x={String(index * barWidth)}
            y={String(y)}
            width={String(Math.max(barWidth - 0.4, 0.8))}
            height={String(normalizedHeight)}
            fill={rising ? '#10B981' : '#EF4444'}
            opacity="0.85"
          />
        )
      })}
    </svg>
  )
}

function buildOrderMarkers(orders: OrderRecord[]): ChartMarker[] {
  return orders
    .filter((order) => ['filled', 'open', 'pending', 'cancelled'].includes(order.status))
    .map((order) => ({
      time: new Date(order.filled_at || order.updated_at || order.created_at).getTime(),
      position:
        order.side === 'buy'
          ? 'belowBar'
          : order.status === 'filled'
          ? 'aboveBar'
          : 'inBar',
      color:
        order.status === 'filled'
          ? order.side === 'buy'
            ? '#10B981'
            : '#EF4444'
          : order.status === 'cancelled'
          ? '#94A3B8'
          : '#F59E0B',
      shape:
        order.status === 'filled'
          ? order.side === 'buy'
            ? 'arrowUp'
            : 'arrowDown'
          : 'circle',
      text:
        order.status === 'filled'
          ? order.side === 'buy'
            ? '매수 체결'
            : '매도 체결'
          : order.status === 'cancelled'
          ? '주문 취소'
          : '주문 대기',
    }))
}

function buildPositionSummary(
  position: PortfolioPosition | null,
  strategy: Strategy | null,
  currentPrice: number
) {
  if (!position || !position.avg_buy_price || currentPrice <= 0) {
    return null
  }

  const quantity = position.quantity
  const avgBuyPrice = position.avg_buy_price
  const pnl = (currentPrice - avgBuyPrice) * quantity
  const pnlPct = avgBuyPrice > 0 ? ((currentPrice - avgBuyPrice) / avgBuyPrice) * 100 : 0
  const config = strategy?.order_config

  return {
    quantity,
    avgBuyPrice,
    pnl,
    pnlPct,
    strategyName: strategy?.name,
    stopLossPrice:
      config?.stop_loss_pct !== undefined ? avgBuyPrice * (1 - config.stop_loss_pct / 100) : null,
    takeProfitPrice:
      config?.take_profit_pct !== undefined ? avgBuyPrice * (1 + config.take_profit_pct / 100) : null,
    trailingStopPct: config?.trailing_stop ? config.trailing_stop_pct || null : null,
  }
}

function buildPriceBands(
  summary: ReturnType<typeof buildPositionSummary>
): ChartPriceBand[] {
  if (!summary) {
    return []
  }

  return [
    { label: '평단', value: summary.avgBuyPrice, color: '#F8FAFC' },
    ...(summary.stopLossPrice ? [{ label: '손절', value: summary.stopLossPrice, color: '#EF4444' }] : []),
    ...(summary.takeProfitPrice ? [{ label: '익절', value: summary.takeProfitPrice, color: '#10B981' }] : []),
  ]
}

function buildRsiSeries(candles: Candle[], period = 14) {
  if (candles.length <= period) {
    return []
  }

  const changes = candles.slice(1).map((candle, index) => candle.close - candles[index].close)
  let averageGain =
    changes.slice(0, period).reduce((sum, change) => sum + Math.max(change, 0), 0) / period
  let averageLoss =
    changes.slice(0, period).reduce((sum, change) => sum + Math.abs(Math.min(change, 0)), 0) / period
  const rsiValues: number[] = []

  for (let index = period; index < changes.length; index += 1) {
    const change = changes[index]
    const gain = Math.max(change, 0)
    const loss = Math.abs(Math.min(change, 0))
    averageGain = (averageGain * (period - 1) + gain) / period
    averageLoss = (averageLoss * (period - 1) + loss) / period

    if (averageLoss === 0) {
      rsiValues.push(100)
      continue
    }

    const relativeStrength = averageGain / averageLoss
    rsiValues.push(100 - 100 / (1 + relativeStrength))
  }

  return rsiValues
}

function buildVolumeSeries(candles: Candle[]) {
  return candles.map((candle) => candle.volume)
}
