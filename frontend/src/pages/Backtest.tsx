import { useCallback, useEffect, useRef, useState } from 'react'
import { BarChart3, Play, RefreshCw, Clock } from 'lucide-react'
import { createChart, IChartApi, ISeriesApi, LineData, UTCTimestamp } from 'lightweight-charts'
import { backtestApi, BacktestResult, BacktestJobStatus } from '@/api/endpoints/backtest'
import { useStrategyStore } from '@/stores/strategyStore'
import { getErrorMessage } from '@/utils/error'

// ─────────────────────────── MetricCard ───────────────────────────

function MetricCard({
  label,
  value,
  color = 'text-white',
  sub,
}: {
  label: string
  value: string | number
  color?: string
  sub?: string
}) {
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
      <p className="text-xs text-gray-400 mb-1">{label}</p>
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      {sub && <p className="text-xs text-gray-500 mt-1">{sub}</p>}
    </div>
  )
}

// ─────────────────────────── EquityChart ──────────────────────────

function EquityChart({ data }: { data: { time: string; value: number }[] }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Line'> | null>(null)

  useEffect(() => {
    if (!containerRef.current) return

    const chart = createChart(containerRef.current, {
      layout: { background: { color: '#1f2937' }, textColor: '#9ca3af' },
      grid: { vertLines: { color: '#374151' }, horzLines: { color: '#374151' } },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: '#374151' },
      timeScale: { borderColor: '#374151', timeVisible: true },
      width: containerRef.current.clientWidth,
      height: 300,
    })
    chartRef.current = chart

    const series = chart.addLineSeries({
      color: '#3b82f6',
      lineWidth: 2,
      priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
    })
    seriesRef.current = series

    const observer = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth })
      }
    })
    observer.observe(containerRef.current)

    return () => {
      observer.disconnect()
      chart.remove()
    }
  }, [])

  useEffect(() => {
    if (!seriesRef.current || !data.length) return

    const seen = new Set<UTCTimestamp>()
    const mapped: LineData[] = data
      .map((d) => ({
        time: Math.floor(new Date(d.time).getTime() / 1000) as UTCTimestamp,
        value: d.value,
      }))
      .sort((a, b) => Number(a.time) - Number(b.time))
      .filter((v) => {
        const timestamp = v.time as UTCTimestamp
        if (seen.has(timestamp)) return false
        seen.add(timestamp)
        return true
      })

    seriesRef.current.setData(mapped)
    chartRef.current?.timeScale().fitContent()
  }, [data])

  return <div ref={containerRef} className="w-full h-[300px]" />
}

// ─────────────────────────── TradeTable ───────────────────────────

function TradeTable({ trades }: { trades: BacktestResult['trade_history'] }) {
  if (!trades.length)
    return <p className="text-sm text-gray-500 text-center py-6">거래 내역이 없습니다.</p>

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm text-left">
        <thead>
          <tr className="text-xs text-gray-400 border-b border-gray-700">
            <th className="py-2 pr-4">진입 시간</th>
            <th className="py-2 pr-4">청산 시간</th>
            <th className="py-2 pr-4 text-right">진입가</th>
            <th className="py-2 pr-4 text-right">청산가</th>
            <th className="py-2 pr-4 text-right">수량</th>
            <th className="py-2 pr-4 text-right">손익</th>
            <th className="py-2 text-right">수익률</th>
          </tr>
        </thead>
        <tbody>
          {trades.slice(0, 50).map((t, i) => (
            <tr key={i} className="border-b border-gray-800 hover:bg-gray-800/40">
              <td className="py-2 pr-4 text-gray-400 text-xs">
                {new Date(t.entry_time).toLocaleString('ko-KR')}
              </td>
              <td className="py-2 pr-4 text-gray-400 text-xs">
                {new Date(t.exit_time).toLocaleString('ko-KR')}
              </td>
              <td className="py-2 pr-4 text-right text-white">${t.entry_price.toFixed(2)}</td>
              <td className="py-2 pr-4 text-right text-white">${t.exit_price.toFixed(2)}</td>
              <td className="py-2 pr-4 text-right text-gray-300">{t.quantity.toFixed(6)}</td>
              <td
                className={`py-2 pr-4 text-right font-medium ${t.pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}
              >
                {t.pnl >= 0 ? '+' : ''}
                {t.pnl.toFixed(2)}
              </td>
              <td
                className={`py-2 text-right font-medium ${t.pnl_pct >= 0 ? 'text-emerald-400' : 'text-red-400'}`}
              >
                {t.pnl_pct >= 0 ? '+' : ''}
                {t.pnl_pct.toFixed(2)}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {trades.length > 50 && (
        <p className="text-xs text-gray-500 text-center mt-2">
          총 {trades.length}건 중 50건 표시
        </p>
      )}
    </div>
  )
}

// ─────────────────────────── ResultPanel ──────────────────────────

function ResultPanel({ result }: { result: BacktestResult }) {
  const returnColor = result.total_return_pct >= 0 ? 'text-emerald-400' : 'text-red-400'

  return (
    <div className="space-y-6">
      <section>
        <h3 className="text-sm font-medium text-gray-400 mb-3">성과 지표</h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          <MetricCard
            label="총 수익률"
            value={`${result.total_return_pct >= 0 ? '+' : ''}${result.total_return_pct.toFixed(2)}%`}
            color={returnColor}
          />
          <MetricCard
            label="최종 자산"
            value={`$${result.final_capital.toLocaleString('en', { maximumFractionDigits: 0 })}`}
            sub={`초기 $${result.initial_capital.toLocaleString('en', { maximumFractionDigits: 0 })}`}
          />
          <MetricCard
            label="최대 낙폭"
            value={`-${result.max_drawdown_pct.toFixed(2)}%`}
            color="text-red-400"
          />
          <MetricCard
            label="샤프 비율"
            value={result.sharpe_ratio.toFixed(3)}
            color={
              result.sharpe_ratio >= 1
                ? 'text-emerald-400'
                : result.sharpe_ratio >= 0
                ? 'text-amber-400'
                : 'text-red-400'
            }
          />
          <MetricCard
            label="승률"
            value={`${result.win_rate.toFixed(1)}%`}
            color={result.win_rate >= 50 ? 'text-emerald-400' : 'text-amber-400'}
            sub={`총 ${result.total_trades}거래`}
          />
          <MetricCard
            label="손익비"
            value={result.profit_factor.toFixed(2)}
            color={result.profit_factor >= 1 ? 'text-emerald-400' : 'text-red-400'}
          />
        </div>
      </section>

      <section>
        <h3 className="text-sm font-medium text-gray-400 mb-3">자산 곡선</h3>
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
          {result.equity_curve.length > 0 ? (
            <EquityChart data={result.equity_curve} />
          ) : (
            <p className="text-sm text-gray-500 text-center py-10">데이터 없음</p>
          )}
        </div>
      </section>

      <section>
        <h3 className="text-sm font-medium text-gray-400 mb-3">거래 내역</h3>
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
          <TradeTable trades={result.trade_history} />
        </div>
      </section>
    </div>
  )
}

// ──────────────────────────── Main Page ───────────────────────────

export default function Backtest() {
  const strategies = useStrategyStore((s) => s.strategies)
  const fetchStrategies = useStrategyStore((s) => s.fetchStrategies)

  const [strategyId, setStrategyId] = useState('')
  const [startDate, setStartDate] = useState(() => {
    const d = new Date()
    d.setMonth(d.getMonth() - 3)
    return d.toISOString().slice(0, 10)
  })
  const [endDate, setEndDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [initialCapital, setInitialCapital] = useState('10000')
  const [commissionPct, setCommissionPct] = useState('0.05')
  const [slippagePct, setSlippagePct] = useState('0.02')

  const [running, setRunning] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const [jobStatus, setJobStatus] = useState<BacktestJobStatus | null>(null)
  const [result, setResult] = useState<BacktestResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [history, setHistory] = useState<BacktestResult[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<'run' | 'history'>('run')

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const loadHistory = useCallback(async (sid?: string) => {
    setHistoryLoading(true)
    try {
      const res = await backtestApi.getHistory({ strategy_id: sid, limit: 20 })
      setHistory(res.data.items)
    } catch {
      // ignore
    } finally {
      setHistoryLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchStrategies()
    void loadHistory()
  }, [fetchStrategies, loadHistory])

  useEffect(() => {
    if (!jobId) return

    pollRef.current = setInterval(async () => {
      try {
        const res = await backtestApi.getStatus(jobId)
        setJobStatus(res.data)

        if (res.data.status === 'completed' && res.data.result_id) {
          clearInterval(pollRef.current!)
          setRunning(false)
          const resultRes = await backtestApi.getResult(res.data.result_id)
          setResult(resultRes.data)
          loadHistory()
        } else if (res.data.status === 'failed') {
          clearInterval(pollRef.current!)
          setRunning(false)
          setError(res.data.error || '백테스트 실행 실패')
        }
      } catch {
        // ignore poll errors
      }
    }, 2000)

    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [jobId, loadHistory])

  const handleRun = async () => {
    if (!strategyId) return
    setError(null)
    setResult(null)
    setJobStatus(null)
    setRunning(true)

    try {
      const res = await backtestApi.run({
        strategy_id: strategyId,
        start_date: startDate,
        end_date: endDate,
        initial_capital: parseFloat(initialCapital) || 10000,
        commission_pct: parseFloat(commissionPct) || 0.05,
        slippage_pct: parseFloat(slippagePct) || 0.02,
      })
      setJobId(res.data.job_id)
    } catch (error: unknown) {
      setRunning(false)
      setError(getErrorMessage(error, '백테스트 요청 실패'))
    }
  }

  const statusLabel: Record<string, string> = {
    pending: '대기 중...',
    running: '실행 중...',
    completed: '완료',
    failed: '실패',
  }

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <BarChart3 size={22} className="text-blue-400" />
          백테스트
        </h1>
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab('run')}
            className={`px-3 py-1.5 text-sm rounded transition-colors ${
              activeTab === 'run'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
            }`}
          >
            실행
          </button>
          <button
            onClick={() => {
              setActiveTab('history')
              void loadHistory()
            }}
            className={`px-3 py-1.5 text-sm rounded transition-colors ${
              activeTab === 'history'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
            }`}
          >
            이력
          </button>
        </div>
      </div>

      {activeTab === 'run' && (
        <>
          {/* 설정 폼 */}
          <div className="bg-gray-800 border border-gray-700 rounded-xl p-6">
            <h2 className="text-sm font-medium text-gray-300 mb-4">백테스트 설정</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <div className="lg:col-span-3">
                <label className="block text-xs text-gray-400 mb-1">전략</label>
                <select
                  className="w-full bg-gray-900 border border-gray-600 text-white text-sm rounded px-3 py-2"
                  value={strategyId}
                  onChange={(e) => setStrategyId(e.target.value)}
                >
                  <option value="">전략을 선택하세요</option>
                  {strategies.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} ({s.symbol} / {s.timeframe})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs text-gray-400 mb-1">시작일</label>
                <input
                  type="date"
                  className="w-full bg-gray-900 border border-gray-600 text-white text-sm rounded px-3 py-2"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                />
              </div>

              <div>
                <label className="block text-xs text-gray-400 mb-1">종료일</label>
                <input
                  type="date"
                  className="w-full bg-gray-900 border border-gray-600 text-white text-sm rounded px-3 py-2"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                />
              </div>

              <div>
                <label className="block text-xs text-gray-400 mb-1">초기 자본 (USDT)</label>
                <input
                  type="number"
                  className="w-full bg-gray-900 border border-gray-600 text-white text-sm rounded px-3 py-2"
                  value={initialCapital}
                  onChange={(e) => setInitialCapital(e.target.value)}
                  min="100"
                  step="100"
                />
              </div>

              <div>
                <label className="block text-xs text-gray-400 mb-1">수수료 (%)</label>
                <input
                  type="number"
                  className="w-full bg-gray-900 border border-gray-600 text-white text-sm rounded px-3 py-2"
                  value={commissionPct}
                  onChange={(e) => setCommissionPct(e.target.value)}
                  min="0"
                  max="5"
                  step="0.01"
                />
              </div>

              <div>
                <label className="block text-xs text-gray-400 mb-1">슬리피지 (%)</label>
                <input
                  type="number"
                  className="w-full bg-gray-900 border border-gray-600 text-white text-sm rounded px-3 py-2"
                  value={slippagePct}
                  onChange={(e) => setSlippagePct(e.target.value)}
                  min="0"
                  max="5"
                  step="0.01"
                />
              </div>
            </div>

            <div className="mt-6 flex items-center gap-4">
              <button
                onClick={handleRun}
                disabled={running || !strategyId}
                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2.5 px-6 rounded-lg transition-colors"
              >
                {running ? (
                  <>
                    <RefreshCw size={16} className="animate-spin" />
                    실행 중...
                  </>
                ) : (
                  <>
                    <Play size={16} />
                    백테스트 실행
                  </>
                )}
              </button>

              {jobStatus && (
                <div className="flex items-center gap-2 text-sm">
                  <Clock size={14} className="text-gray-400" />
                  <span className="text-gray-400">
                    상태:{' '}
                    <span
                      className={
                        jobStatus.status === 'completed'
                          ? 'text-emerald-400'
                          : jobStatus.status === 'failed'
                          ? 'text-red-400'
                          : 'text-amber-400'
                      }
                    >
                      {statusLabel[jobStatus.status] || jobStatus.status}
                    </span>
                  </span>
                </div>
              )}
            </div>

            {error && (
              <div className="mt-3 p-3 bg-red-900/30 border border-red-800 rounded text-sm text-red-300">
                {error}
              </div>
            )}
          </div>

          {running && !result && (
            <div className="flex flex-col items-center justify-center h-48 text-gray-400 bg-gray-800 border border-gray-700 rounded-xl">
              <RefreshCw size={28} className="animate-spin mb-3 text-blue-400" />
              <p className="text-sm">백테스트를 실행 중입니다...</p>
              <p className="text-xs text-gray-500 mt-1">
                기간에 따라 최대 수 분이 소요될 수 있습니다
              </p>
            </div>
          )}

          {result && <ResultPanel result={result} />}
        </>
      )}

      {activeTab === 'history' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-400">{history.length}개의 백테스트 결과</span>
            <button
              onClick={() => loadHistory()}
              disabled={historyLoading}
              className="p-2 bg-gray-800 border border-gray-700 rounded hover:bg-gray-700 text-gray-400 disabled:opacity-50"
            >
              <RefreshCw size={14} className={historyLoading ? 'animate-spin' : ''} />
            </button>
          </div>

          {historyLoading ? (
            <div className="flex items-center justify-center h-32 text-gray-400">
              <RefreshCw size={20} className="animate-spin mr-2" />
              불러오는 중...
            </div>
          ) : history.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 text-gray-500 bg-gray-800 border border-gray-700 rounded-xl">
              <BarChart3 size={32} className="mb-3 opacity-40" />
              <p className="text-sm">백테스트 이력이 없습니다.</p>
              <p className="text-xs mt-1">백테스트를 실행하면 결과가 여기에 표시됩니다.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {history.map((r) => {
                const positive = r.total_return_pct >= 0
                return (
                  <div
                    key={r.id}
                    className="bg-gray-800 border border-gray-700 rounded-lg p-4 hover:border-gray-600 transition-colors cursor-pointer"
                    onClick={() => {
                      setActiveTab('run')
                      setResult(r)
                    }}
                  >
                    <div className="flex items-center justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-sm font-medium text-white">
                            {r.params_snapshot?.symbol as string} /{' '}
                            {r.params_snapshot?.timeframe as string}
                          </span>
                          <span className="text-xs text-gray-500">
                            {r.start_date} ~ {r.end_date}
                          </span>
                        </div>
                        <div className="flex gap-4 mt-2 text-xs text-gray-400">
                          <span>총 거래 {r.total_trades}회</span>
                          <span>승률 {r.win_rate.toFixed(1)}%</span>
                          <span>MDD {r.max_drawdown_pct.toFixed(2)}%</span>
                          <span>Sharpe {r.sharpe_ratio.toFixed(3)}</span>
                        </div>
                      </div>
                      <div className="text-right flex-shrink-0">
                        <div
                          className={`text-lg font-bold ${
                            positive ? 'text-emerald-400' : 'text-red-400'
                          }`}
                        >
                          {positive ? '+' : ''}
                          {r.total_return_pct.toFixed(2)}%
                        </div>
                        <div className="text-xs text-gray-500">
                          ${r.initial_capital.toLocaleString('en')} → $
                          {r.final_capital.toLocaleString('en', { maximumFractionDigits: 0 })}
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
