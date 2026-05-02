import { useEffect, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { ordersApi } from '@/api/endpoints/orders'
import type { OrderRecord } from '@/types'
import { getErrorMessage } from '@/utils/error'

const OPEN_STATUSES = new Set(['pending', 'open', 'partially_filled'])
const SUCCESS_STATUSES = new Set(['filled', 'closed', 'completed'])
const FAILED_STATUSES = new Set(['cancelled', 'failed', 'rejected'])

function formatCurrency(value: number | null) {
  if (value === null) {
    return '-'
  }

  return `$${value.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

function formatQuantity(value: number) {
  return value.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 8,
  })
}

function formatDateTime(value: string | null) {
  if (!value) {
    return '-'
  }

  return new Date(value).toLocaleString('ko-KR')
}

function getStatusClasses(status: string) {
  if (OPEN_STATUSES.has(status)) {
    return 'bg-amber-900/30 text-amber-300 border-amber-700'
  }

  if (SUCCESS_STATUSES.has(status)) {
    return 'bg-emerald-900/30 text-emerald-300 border-emerald-700'
  }

  if (FAILED_STATUSES.has(status)) {
    return 'bg-red-900/30 text-red-300 border-red-700'
  }

  return 'bg-slate-800 text-slate-300 border-slate-700'
}

export default function Orders() {
  const [orders, setOrders] = useState<OrderRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')

  const loadOrders = async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true)
    } else {
      setLoading(true)
    }

    setError('')

    try {
      const response = await ordersApi.list(1, 50)
      setOrders(response.data)
    } catch (err) {
      setError(getErrorMessage(err, '주문 데이터를 불러오지 못했습니다.'))
    } finally {
      if (isRefresh) {
        setRefreshing(false)
      } else {
        setLoading(false)
      }
    }
  }

  useEffect(() => {
    void loadOrders()
  }, [])

  const openOrders = orders.filter((order) => OPEN_STATUSES.has(order.status))
  const filledOrders = orders.filter((order) => SUCCESS_STATUSES.has(order.status))
  const failedOrders = orders.filter((order) => FAILED_STATUSES.has(order.status))
  const buyOrders = orders.filter((order) => order.side === 'buy')
  const sellOrders = orders.filter((order) => order.side === 'sell')

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-100">주문</h2>
          <p className="text-slate-400">
            최근 주문 상태와 체결 흐름을 한 화면에서 확인합니다.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void loadOrders(true)}
          disabled={refreshing}
          className="btn-secondary inline-flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <RefreshCw size={16} className={refreshing ? 'animate-spin' : ''} />
          {refreshing ? '새로고침 중...' : '새로고침'}
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-700 bg-red-900/40 px-4 py-3 text-sm text-red-100">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {[
          { label: '최근 주문 수', value: orders.length, tone: 'text-slate-100' },
          { label: '진행 중', value: openOrders.length, tone: 'text-amber-300' },
          { label: '체결 완료', value: filledOrders.length, tone: 'text-emerald-300' },
          { label: '취소/실패', value: failedOrders.length, tone: 'text-red-300' },
        ].map((item) => (
          <div key={item.label} className="card">
            <p className="text-sm text-slate-400">{item.label}</p>
            <p className={`mt-2 text-3xl font-bold ${item.tone}`}>{item.value}</p>
          </div>
        ))}
      </div>

      {loading ? (
        <div className="card text-sm text-slate-400">주문 데이터를 불러오는 중...</div>
      ) : orders.length === 0 ? (
        <div className="card text-sm text-slate-400">
          아직 주문 이력이 없습니다. 전략이 실제로 평가되고 주문이 발생하면 이 화면에 표시됩니다.
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <div className="card">
              <div className="mb-4 flex items-center justify-between">
                <h3 className="text-lg font-semibold text-slate-100">진행 중인 주문</h3>
                <span className="text-sm text-slate-400">{openOrders.length}건</span>
              </div>
              {openOrders.length === 0 ? (
                <p className="text-sm text-slate-400">현재 열려 있는 주문이 없습니다.</p>
              ) : (
                <div className="space-y-3">
                  {openOrders.map((order) => (
                    <div
                      key={order.id}
                      className="rounded-xl border border-slate-800 bg-slate-950/50 p-4"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-slate-100">
                            {order.symbol} · {order.exchange_id.toUpperCase()}
                          </p>
                          <p className="mt-1 text-xs text-slate-400">
                            {order.side.toUpperCase()} · {order.order_type.toUpperCase()} · 생성 {formatDateTime(order.created_at)}
                          </p>
                        </div>
                        <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${getStatusClasses(order.status)}`}>
                          {order.status}
                        </span>
                      </div>
                      <div className="mt-3 grid gap-3 sm:grid-cols-3">
                        <div>
                          <p className="text-xs text-slate-500">주문가</p>
                          <p className="mt-1 text-sm text-slate-200">{formatCurrency(order.price)}</p>
                        </div>
                        <div>
                          <p className="text-xs text-slate-500">수량</p>
                          <p className="mt-1 text-sm text-slate-200">{formatQuantity(order.quantity)}</p>
                        </div>
                        <div>
                          <p className="text-xs text-slate-500">체결 진행</p>
                          <p className="mt-1 text-sm text-slate-200">
                            {formatQuantity(order.filled_quantity)} / {formatQuantity(order.quantity)}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="card">
              <div className="mb-4 flex items-center justify-between">
                <h3 className="text-lg font-semibold text-slate-100">주문 방향 분포</h3>
                <span className="text-sm text-slate-400">최근 50건 기준</span>
              </div>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-4">
                  <p className="text-sm text-slate-400">매수 주문</p>
                  <p className="mt-2 text-3xl font-bold text-emerald-300">{buyOrders.length}</p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-4">
                  <p className="text-sm text-slate-400">매도 주문</p>
                  <p className="mt-2 text-3xl font-bold text-rose-300">{sellOrders.length}</p>
                </div>
              </div>
            </div>
          </div>

          <div className="card overflow-hidden">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-slate-100">최근 주문 내역</h3>
              <span className="text-sm text-slate-400">{orders.length}건 표시</span>
            </div>

            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-800 text-sm">
                <thead className="bg-slate-900/80 text-slate-400">
                  <tr>
                    <th className="px-4 py-3 text-left font-medium">심볼</th>
                    <th className="px-4 py-3 text-left font-medium">방향</th>
                    <th className="px-4 py-3 text-left font-medium">상태</th>
                    <th className="px-4 py-3 text-right font-medium">주문가</th>
                    <th className="px-4 py-3 text-right font-medium">체결가</th>
                    <th className="px-4 py-3 text-right font-medium">수량</th>
                    <th className="px-4 py-3 text-left font-medium">생성 시각</th>
                    <th className="px-4 py-3 text-left font-medium">최근 변경</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800 bg-slate-950/40">
                  {orders.map((order) => (
                    <tr key={order.id}>
                      <td className="px-4 py-3">
                        <div>
                          <p className="font-medium text-slate-100">{order.symbol}</p>
                          <p className="text-xs text-slate-500">{order.exchange_id.toUpperCase()}</p>
                        </div>
                      </td>
                      <td className={`px-4 py-3 font-medium ${order.side === 'buy' ? 'text-emerald-300' : 'text-rose-300'}`}>
                        {order.side.toUpperCase()}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${getStatusClasses(order.status)}`}>
                          {order.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right text-slate-300">{formatCurrency(order.price)}</td>
                      <td className="px-4 py-3 text-right text-slate-300">{formatCurrency(order.avg_fill_price)}</td>
                      <td className="px-4 py-3 text-right text-slate-300">
                        {formatQuantity(order.filled_quantity)} / {formatQuantity(order.quantity)}
                      </td>
                      <td className="px-4 py-3 text-slate-400">{formatDateTime(order.created_at)}</td>
                      <td className="px-4 py-3 text-slate-400">
                        {order.filled_at ? formatDateTime(order.filled_at) : formatDateTime(order.updated_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
