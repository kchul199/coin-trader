import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { RefreshCw } from 'lucide-react'
import { axios } from '@/api/client'
import { chartApi } from '@/api/endpoints/chart'
import { exchangeApi } from '@/api/endpoints/exchange'
import { portfolioApi } from '@/api/endpoints/portfolio'
import type { Balance, PortfolioPosition } from '@/types'
import { getErrorMessage } from '@/utils/error'
import { formatQuoteCurrency, getTickerSymbolForAsset, toCompactSymbol } from '@/utils/market'

interface BalanceMeta {
  exchangeId: string
  isTestnet: boolean
  syncedAt: string
}

function formatQuantity(value: number) {
  return value.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 8,
  })
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString('ko-KR')
}

function getPnlClasses(value: number | null) {
  if (value === null) {
    return 'text-slate-300'
  }

  if (value > 0) {
    return 'text-emerald-300'
  }

  if (value < 0) {
    return 'text-rose-300'
  }

  return 'text-slate-300'
}

export default function Portfolio() {
  const [positions, setPositions] = useState<PortfolioPosition[]>([])
  const [balances, setBalances] = useState<Balance[]>([])
  const [balanceMeta, setBalanceMeta] = useState<BalanceMeta | null>(null)
  const [prices, setPrices] = useState<Record<string, number>>({})
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [balanceError, setBalanceError] = useState('')

  const loadPortfolio = async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true)
    } else {
      setLoading(true)
    }

    setError('')
    setBalanceError('')

    try {
      const positionsResponse = await portfolioApi.list()
      setPositions(positionsResponse.data)

      let latestBalances: Balance[] = []

      try {
        const balanceResponse = await exchangeApi.getBalance()
        latestBalances = balanceResponse.data.balances
        setBalances(balanceResponse.data.balances)
        setBalanceMeta({
          exchangeId: balanceResponse.data.exchange_id,
          isTestnet: balanceResponse.data.is_testnet,
          syncedAt: balanceResponse.data.synced_at,
        })
      } catch (balanceErr) {
        if (axios.isAxiosError(balanceErr) && balanceErr.response?.status === 404) {
          setBalances([])
          setBalanceMeta(null)
        } else {
          setBalances([])
          setBalanceMeta(null)
          setBalanceError(getErrorMessage(balanceErr, '거래소 잔고를 불러오지 못했습니다.'))
        }
      }

      const tickerSymbols = new Set<string>()

      positionsResponse.data.forEach((position) => {
        tickerSymbols.add(toCompactSymbol(position.symbol))
      })

      latestBalances.forEach((balance) => {
        if (balance.total <= 0) {
          return
        }

        const tickerSymbol = getTickerSymbolForAsset(balance.symbol)
        if (tickerSymbol) {
          tickerSymbols.add(tickerSymbol)
        }
      })

      if (tickerSymbols.size === 0) {
        setPrices({})
        return
      }

      const priceEntries = await Promise.allSettled(
        [...tickerSymbols].map(async (symbol) => {
          const response = await chartApi.ticker(symbol)
          return [symbol, response.data.price] as const
        }),
      )

      const nextPrices: Record<string, number> = {}
      priceEntries.forEach((entry) => {
        if (entry.status === 'fulfilled') {
          const [symbol, price] = entry.value
          nextPrices[symbol] = price
        }
      })

      setPrices(nextPrices)
    } catch (err) {
      setError(getErrorMessage(err, '포트폴리오 데이터를 불러오지 못했습니다.'))
    } finally {
      if (isRefresh) {
        setRefreshing(false)
      } else {
        setLoading(false)
      }
    }
  }

  useEffect(() => {
    void loadPortfolio()
  }, [])

  const handleSyncBalance = async () => {
    setRefreshing(true)
    setBalanceError('')

    try {
      const response = await exchangeApi.syncBalance()
      setBalances(response.data.balances)
      setBalanceMeta({
        exchangeId: response.data.exchange_id,
        isTestnet: response.data.is_testnet,
        syncedAt: response.data.synced_at,
      })
      await loadPortfolio(true)
    } catch (err) {
      setBalanceError(getErrorMessage(err, '잔고 동기화에 실패했습니다.'))
      setRefreshing(false)
    }
  }

  const evaluatedPositions = positions.map((position) => {
    const tickerSymbol = toCompactSymbol(position.symbol)
    const currentPrice = prices[tickerSymbol] ?? null
    const currentValue = currentPrice === null ? null : position.quantity * currentPrice
    const investedCapital =
      position.initial_capital ??
      (position.avg_buy_price === null ? null : position.quantity * position.avg_buy_price)
    const pnl =
      currentValue === null || investedCapital === null
        ? null
        : currentValue - investedCapital

    return {
      ...position,
      currentPrice,
      currentValue,
      investedCapital,
      pnl,
    }
  })

  const evaluatedBalances = balances.map((balance) => {
    const tickerSymbol = getTickerSymbolForAsset(balance.symbol)
    const currentPrice = tickerSymbol === null ? 1 : (prices[tickerSymbol] ?? null)
    const estimatedValue = currentPrice === null ? null : balance.total * currentPrice

    return {
      ...balance,
      currentPrice,
      estimatedValue,
    }
  })

  const investedCapital = evaluatedPositions.reduce(
    (sum, position) => sum + (position.investedCapital ?? 0),
    0,
  )
  const estimatedPositionValue = evaluatedPositions.reduce(
    (sum, position) => sum + (position.currentValue ?? 0),
    0,
  )
  const unrealizedPnl = estimatedPositionValue - investedCapital
  const estimatedBalanceValue = evaluatedBalances.reduce(
    (sum, balance) => sum + (balance.estimatedValue ?? 0),
    0,
  )
  const assetsWithoutPrice = evaluatedBalances.filter(
    (balance) => balance.total > 0 && balance.estimatedValue === null,
  ).length

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-100">포트폴리오</h2>
          <p className="text-slate-400">
            전략 포지션과 거래소 잔고를 함께 보면서 현재 노출을 확인합니다.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => void loadPortfolio(true)}
            disabled={refreshing}
            className="btn-secondary inline-flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RefreshCw size={16} className={refreshing ? 'animate-spin' : ''} />
            {refreshing ? '새로고침 중...' : '새로고침'}
          </button>
          <button
            type="button"
            onClick={() => void handleSyncBalance()}
            disabled={refreshing}
            className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            잔고 동기화
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-700 bg-red-900/40 px-4 py-3 text-sm text-red-100">
          {error}
        </div>
      )}

      {balanceError && (
        <div className="rounded-lg border border-amber-700 bg-amber-900/30 px-4 py-3 text-sm text-amber-100">
          {balanceError}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="card">
          <p className="text-sm text-slate-400">전략 포지션 평가금액</p>
          <p className="mt-2 text-3xl font-bold text-slate-100">{formatQuoteCurrency(estimatedPositionValue)}</p>
        </div>
        <div className="card">
          <p className="text-sm text-slate-400">투입 원금</p>
          <p className="mt-2 text-3xl font-bold text-slate-100">{formatQuoteCurrency(investedCapital)}</p>
        </div>
        <div className="card">
          <p className="text-sm text-slate-400">미실현 손익</p>
          <p className={`mt-2 text-3xl font-bold ${getPnlClasses(unrealizedPnl)}`}>
            {formatQuoteCurrency(unrealizedPnl)}
          </p>
        </div>
        <div className="card">
          <p className="text-sm text-slate-400">거래소 잔고 추정 가치</p>
          <p className="mt-2 text-3xl font-bold text-slate-100">{formatQuoteCurrency(estimatedBalanceValue)}</p>
          <p className="mt-1 text-xs text-slate-500">
            평가 불가 자산 {assetsWithoutPrice}개
          </p>
        </div>
      </div>

      {loading ? (
        <div className="card text-sm text-slate-400">포트폴리오 데이터를 불러오는 중...</div>
      ) : (
        <>
          <section className="card">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-slate-100">전략 포지션</h3>
                <p className="text-sm text-slate-400">
                  자동매매 엔진이 추적 중인 포지션 기준입니다.
                </p>
              </div>
              <span className="text-sm text-slate-400">{evaluatedPositions.length}개</span>
            </div>

            {evaluatedPositions.length === 0 ? (
              <div className="rounded-lg border border-dashed border-slate-800 px-4 py-6 text-sm text-slate-400">
                아직 기록된 포지션이 없습니다. 주문이 체결되면 포지션이 누적됩니다.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-800 text-sm">
                  <thead className="bg-slate-900/80 text-slate-400">
                    <tr>
                      <th className="px-4 py-3 text-left font-medium">심볼</th>
                      <th className="px-4 py-3 text-right font-medium">수량</th>
                      <th className="px-4 py-3 text-right font-medium">평균 매수가</th>
                      <th className="px-4 py-3 text-right font-medium">현재가</th>
                      <th className="px-4 py-3 text-right font-medium">평가금액</th>
                      <th className="px-4 py-3 text-right font-medium">손익</th>
                      <th className="px-4 py-3 text-left font-medium">업데이트</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800 bg-slate-950/40">
                    {evaluatedPositions.map((position) => (
                      <tr key={position.id}>
                        <td className="px-4 py-3">
                          <div>
                            <p className="font-medium text-slate-100">{position.symbol}</p>
                            <p className="text-xs text-slate-500">{position.exchange_id.toUpperCase()}</p>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right text-slate-300">{formatQuantity(position.quantity)}</td>
                        <td className="px-4 py-3 text-right text-slate-300">{formatQuoteCurrency(position.avg_buy_price)}</td>
                        <td className="px-4 py-3 text-right text-slate-300">{formatQuoteCurrency(position.currentPrice)}</td>
                        <td className="px-4 py-3 text-right text-slate-100">{formatQuoteCurrency(position.currentValue)}</td>
                        <td className={`px-4 py-3 text-right font-medium ${getPnlClasses(position.pnl)}`}>
                          {formatQuoteCurrency(position.pnl)}
                        </td>
                        <td className="px-4 py-3 text-slate-400">{formatDateTime(position.last_updated)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="card">
            <div className="mb-4 flex items-center justify-between gap-4">
              <div>
                <h3 className="text-lg font-semibold text-slate-100">거래소 잔고 스냅샷</h3>
                <p className="text-sm text-slate-400">
                  Settings에서 연결한 활성 거래소 계정 기준입니다.
                </p>
              </div>
              {balanceMeta && (
                <div className="text-right text-xs text-slate-500">
                  <p>{balanceMeta.exchangeId.toUpperCase()} · {balanceMeta.isTestnet ? 'Testnet' : 'Live'}</p>
                  <p>{formatDateTime(balanceMeta.syncedAt)}</p>
                </div>
              )}
            </div>

            {evaluatedBalances.length === 0 ? (
              <div className="rounded-lg border border-dashed border-slate-800 px-4 py-6 text-sm text-slate-400">
                잔고 데이터가 없습니다. 거래소 계정이 아직 없다면{' '}
                <Link to="/settings" className="text-blue-400 hover:text-blue-300">
                  설정 페이지
                </Link>
                에서 먼저 연결해 주세요.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-800 text-sm">
                  <thead className="bg-slate-900/80 text-slate-400">
                    <tr>
                      <th className="px-4 py-3 text-left font-medium">자산</th>
                      <th className="px-4 py-3 text-right font-medium">가용</th>
                      <th className="px-4 py-3 text-right font-medium">주문중</th>
                      <th className="px-4 py-3 text-right font-medium">합계</th>
                      <th className="px-4 py-3 text-right font-medium">현재가</th>
                      <th className="px-4 py-3 text-right font-medium">추정 가치</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800 bg-slate-950/40">
                    {evaluatedBalances.map((balance) => (
                      <tr key={balance.symbol}>
                        <td className="px-4 py-3 font-medium text-slate-100">{balance.symbol}</td>
                        <td className="px-4 py-3 text-right text-slate-300">{formatQuantity(balance.available)}</td>
                        <td className="px-4 py-3 text-right text-slate-300">{formatQuantity(balance.locked)}</td>
                        <td className="px-4 py-3 text-right text-slate-100">{formatQuantity(balance.total)}</td>
                        <td className="px-4 py-3 text-right text-slate-300">{formatQuoteCurrency(balance.currentPrice)}</td>
                        <td className="px-4 py-3 text-right text-slate-100">{formatQuoteCurrency(balance.estimatedValue)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  )
}
