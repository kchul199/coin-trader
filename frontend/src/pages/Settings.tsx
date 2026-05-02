import { useEffect, useState } from 'react'
import { authApi, type TotpSetupResponse } from '@/api/endpoints/auth'
import { axios } from '@/api/client'
import { exchangeApi } from '@/api/endpoints/exchange'
import { useAuthStore } from '@/stores/authStore'
import type { Balance, ExchangeAccount } from '@/types'
import { getErrorMessage } from '@/utils/error'
import { DEFAULT_EXCHANGE_ID } from '@/utils/market'

const EXCHANGE_OPTIONS = [
  { value: 'upbit', label: 'Upbit' },
  { value: 'binance', label: 'Binance' },
  { value: 'bithumb', label: 'Bithumb' },
] as const

function formatDateTime(value: string) {
  return new Date(value).toLocaleString('ko-KR')
}

export default function Settings() {
  const user = useAuthStore((state) => state.user)
  const fetchMe = useAuthStore((state) => state.fetchMe)

  const [refreshKey, setRefreshKey] = useState(0)
  const [pageLoading, setPageLoading] = useState(true)
  const [pageError, setPageError] = useState('')

  const [accounts, setAccounts] = useState<ExchangeAccount[]>([])
  const [balances, setBalances] = useState<Balance[]>([])
  const [balanceMeta, setBalanceMeta] = useState<{ exchangeId: string; isTestnet: boolean; syncedAt: string } | null>(null)
  const [balanceError, setBalanceError] = useState('')
  const [balanceMessage, setBalanceMessage] = useState('')

  const [exchangeId, setExchangeId] = useState<'binance' | 'upbit' | 'bithumb'>(DEFAULT_EXCHANGE_ID)
  const [apiKey, setApiKey] = useState('')
  const [apiSecret, setApiSecret] = useState('')
  const [isTestnet, setIsTestnet] = useState(false)
  const [accountLoading, setAccountLoading] = useState(false)
  const [accountMessage, setAccountMessage] = useState('')
  const [accountError, setAccountError] = useState('')
  const [deletingAccountId, setDeletingAccountId] = useState<string | null>(null)
  const [syncingBalance, setSyncingBalance] = useState(false)

  const [totpSetup, setTotpSetup] = useState<TotpSetupResponse | null>(null)
  const [totpCode, setTotpCode] = useState('')
  const [securityLoading, setSecurityLoading] = useState(false)
  const [securityMessage, setSecurityMessage] = useState('')
  const [securityError, setSecurityError] = useState('')

  useEffect(() => {
    let cancelled = false

    async function loadSettings() {
      setPageLoading(true)
      setPageError('')

      try {
        await fetchMe().catch(() => undefined)

        const accountsResponse = await exchangeApi.listAccounts()
        if (cancelled) {
          return
        }

        setAccounts(accountsResponse.data)

        try {
          const balanceResponse = await exchangeApi.getBalance()
          if (cancelled) {
            return
          }

          setBalances(balanceResponse.data.balances)
          setBalanceMeta({
            exchangeId: balanceResponse.data.exchange_id,
            isTestnet: balanceResponse.data.is_testnet,
            syncedAt: balanceResponse.data.synced_at,
          })
          setBalanceError('')
        } catch (error) {
          if (cancelled) {
            return
          }

          if (axios.isAxiosError(error) && error.response?.status === 404) {
            setBalances([])
            setBalanceMeta(null)
            setBalanceError('')
          } else {
            setBalances([])
            setBalanceMeta(null)
            setBalanceError(getErrorMessage(error, '잔고를 불러오지 못했습니다.'))
          }
        }
      } catch (error) {
        if (!cancelled) {
          setPageError(getErrorMessage(error, '설정 정보를 불러오지 못했습니다.'))
        }
      } finally {
        if (!cancelled) {
          setPageLoading(false)
        }
      }
    }

    void loadSettings()

    return () => {
      cancelled = true
    }
  }, [fetchMe, refreshKey])

  useEffect(() => {
    if (exchangeId !== 'binance' && isTestnet) {
      setIsTestnet(false)
    }
  }, [exchangeId, isTestnet])

  const handleCreateAccount = async (e: React.FormEvent) => {
    e.preventDefault()
    setAccountLoading(true)
    setAccountError('')
    setAccountMessage('')

    try {
      await exchangeApi.createAccount({
        exchange_id: exchangeId,
        api_key: apiKey,
        api_secret: apiSecret,
        is_testnet: isTestnet,
      })

      setApiKey('')
      setApiSecret('')
      setAccountMessage('거래소 계정이 연결되었습니다.')
      setRefreshKey((value) => value + 1)
    } catch (error) {
      setAccountError(getErrorMessage(error, '거래소 계정을 연결하지 못했습니다.'))
    } finally {
      setAccountLoading(false)
    }
  }

  const handleDeleteAccount = async (accountId: string) => {
    setDeletingAccountId(accountId)
    setAccountError('')
    setAccountMessage('')

    try {
      await exchangeApi.deleteAccount(accountId)
      setAccountMessage('거래소 계정이 삭제되었습니다.')
      setRefreshKey((value) => value + 1)
    } catch (error) {
      setAccountError(getErrorMessage(error, '거래소 계정을 삭제하지 못했습니다.'))
    } finally {
      setDeletingAccountId(null)
    }
  }

  const handleSyncBalance = async () => {
    setSyncingBalance(true)
    setBalanceMessage('')
    setBalanceError('')

    try {
      const response = await exchangeApi.syncBalance()
      setBalances(response.data.balances)
      setBalanceMeta({
        exchangeId: response.data.exchange_id,
        isTestnet: response.data.is_testnet,
        syncedAt: response.data.synced_at,
      })
      setBalanceMessage('잔고를 거래소에서 다시 읽어왔습니다.')
    } catch (error) {
      setBalanceError(getErrorMessage(error, '잔고 동기화에 실패했습니다.'))
    } finally {
      setSyncingBalance(false)
    }
  }

  const handleSetup2fa = async () => {
    setSecurityLoading(true)
    setSecurityError('')
    setSecurityMessage('')

    try {
      const response = await authApi.setup2fa()
      setTotpSetup(response.data)
      setSecurityMessage('인증 앱에 Secret 또는 otpauth URI를 등록한 뒤 6자리 코드를 입력해 주세요.')
    } catch (error) {
      setSecurityError(getErrorMessage(error, '2FA 설정을 시작하지 못했습니다.'))
    } finally {
      setSecurityLoading(false)
    }
  }

  const handleVerify2fa = async (e: React.FormEvent) => {
    e.preventDefault()
    setSecurityLoading(true)
    setSecurityError('')
    setSecurityMessage('')

    try {
      await authApi.verify2fa(totpCode)
      await fetchMe()
      setTotpCode('')
      setTotpSetup(null)
      setSecurityMessage('2FA가 활성화되었습니다. 다음 로그인부터 6자리 코드를 함께 입력하세요.')
    } catch (error) {
      setSecurityError(getErrorMessage(error, '2FA 활성화에 실패했습니다.'))
    } finally {
      setSecurityLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-100">설정</h2>
          <p className="text-slate-400">
            계정 보안, 거래소 연결, 잔고 동기화를 여기서 관리합니다.
          </p>
        </div>
      </div>

      {pageError && (
        <div className="rounded-lg border border-red-700 bg-red-900/40 px-4 py-3 text-sm text-red-100">
          {pageError}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-6">
          <section className="card space-y-4">
            <div>
              <h3 className="text-lg font-semibold text-slate-100">계정 보안</h3>
              <p className="text-sm text-slate-400">
                현재 로그인 계정 상태와 2FA 활성화 여부를 확인합니다.
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
                <p className="text-xs uppercase tracking-wide text-slate-500">이메일</p>
                <p className="mt-2 text-sm font-medium text-slate-100">{user?.email ?? '불러오는 중...'}</p>
              </div>
              <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
                <p className="text-xs uppercase tracking-wide text-slate-500">2FA 상태</p>
                <p className="mt-2 text-sm font-medium text-slate-100">
                  {user?.has_2fa ? '활성화됨' : '비활성화됨'}
                </p>
              </div>
            </div>

            {securityMessage && (
              <div className="rounded-lg border border-emerald-700 bg-emerald-900/30 px-4 py-3 text-sm text-emerald-100">
                {securityMessage}
              </div>
            )}

            {securityError && (
              <div className="rounded-lg border border-red-700 bg-red-900/40 px-4 py-3 text-sm text-red-100">
                {securityError}
              </div>
            )}

            {user?.has_2fa ? (
              <div className="rounded-lg border border-slate-800 bg-slate-950/50 px-4 py-3 text-sm text-slate-300">
                이 계정은 이미 2FA가 활성화되어 있습니다. 로그인할 때 이메일, 비밀번호와 함께 6자리 코드를 입력하세요.
              </div>
            ) : (
              <div className="space-y-4">
                <button
                  type="button"
                  onClick={handleSetup2fa}
                  disabled={securityLoading}
                  className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {securityLoading ? '2FA 준비 중...' : '2FA 설정 시작'}
                </button>

                {totpSetup && (
                  <div className="space-y-4 rounded-xl border border-slate-800 bg-slate-950/50 p-4">
                    <div>
                      <p className="text-sm font-medium text-slate-100">1. 인증 앱에 아래 Secret 등록</p>
                      <p className="mt-2 break-all rounded-lg bg-slate-900 px-3 py-2 text-sm text-sky-300">
                        {totpSetup.secret}
                      </p>
                    </div>
                    <div>
                      <p className="text-sm font-medium text-slate-100">2. 또는 otpauth URI 사용</p>
                      <textarea
                        readOnly
                        value={totpSetup.qr_uri}
                        className="input mt-2 min-h-24 w-full resize-none text-xs"
                      />
                    </div>
                    <form onSubmit={handleVerify2fa} className="space-y-3">
                      <div>
                        <label htmlFor="totpVerifyCode" className="block text-sm font-medium text-slate-300 mb-2">
                          3. 인증 앱의 6자리 코드 입력
                        </label>
                        <input
                          id="totpVerifyCode"
                          type="text"
                          inputMode="numeric"
                          value={totpCode}
                          onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                          placeholder="123456"
                          className="input w-full"
                          maxLength={6}
                          required
                          disabled={securityLoading}
                        />
                      </div>
                      <button
                        type="submit"
                        disabled={securityLoading}
                        className="btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {securityLoading ? '2FA 활성화 중...' : '2FA 활성화 완료'}
                      </button>
                    </form>
                  </div>
                )}
              </div>
            )}
          </section>

          <section className="card space-y-4">
            <div>
              <h3 className="text-lg font-semibold text-slate-100">거래소 계정 연결</h3>
              <p className="text-sm text-slate-400">
                업비트 KRW 마켓 연결을 기본으로 사용합니다. 저장 시 서버에서 즉시 잔고 조회를 시도해 키 유효성을 검사합니다. 업비트 KRW 마켓의 최소 주문 가능 금액은 5,000원입니다.
              </p>
            </div>

            {accountMessage && (
              <div className="rounded-lg border border-emerald-700 bg-emerald-900/30 px-4 py-3 text-sm text-emerald-100">
                {accountMessage}
              </div>
            )}

            {accountError && (
              <div className="rounded-lg border border-red-700 bg-red-900/40 px-4 py-3 text-sm text-red-100">
                {accountError}
              </div>
            )}

            <form onSubmit={handleCreateAccount} className="grid gap-4 md:grid-cols-2">
              <div>
                <label htmlFor="exchangeId" className="mb-2 block text-sm font-medium text-slate-300">
                  거래소
                </label>
                <select
                  id="exchangeId"
                  value={exchangeId}
                  onChange={(e) => setExchangeId(e.target.value as 'binance' | 'upbit' | 'bithumb')}
                  className="input w-full"
                  disabled={accountLoading}
                >
                  {EXCHANGE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>

              <label className="flex items-center gap-3 rounded-lg border border-slate-800 bg-slate-950/50 px-4 py-3 text-sm text-slate-300 md:mt-7">
                <input
                  type="checkbox"
                  checked={isTestnet}
                  onChange={(e) => setIsTestnet(e.target.checked)}
                  disabled={accountLoading || exchangeId !== 'binance'}
                />
                테스트넷 사용 (Binance 전용)
              </label>

              <div className="md:col-span-2">
                <label htmlFor="apiKey" className="mb-2 block text-sm font-medium text-slate-300">
                  API Key
                </label>
                <input
                  id="apiKey"
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  className="input w-full"
                  placeholder="거래소 API Key"
                  autoComplete="off"
                  required
                  disabled={accountLoading}
                />
              </div>

              <div className="md:col-span-2">
                <label htmlFor="apiSecret" className="mb-2 block text-sm font-medium text-slate-300">
                  API Secret
                </label>
                <input
                  id="apiSecret"
                  type="password"
                  value={apiSecret}
                  onChange={(e) => setApiSecret(e.target.value)}
                  className="input w-full"
                  placeholder="거래소 API Secret"
                  autoComplete="off"
                  required
                  disabled={accountLoading}
                />
              </div>

              <div className="md:col-span-2">
                <button
                  type="submit"
                  disabled={accountLoading}
                  className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {accountLoading ? '연결 확인 중...' : '거래소 계정 저장'}
                </button>
              </div>
            </form>
          </section>
        </div>

        <div className="space-y-6">
          <section className="card space-y-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h3 className="text-lg font-semibold text-slate-100">연결된 계정</h3>
                <p className="text-sm text-slate-400">
                  현재 사용자에 연결된 거래소 계정 목록입니다.
                </p>
              </div>
            </div>

            {pageLoading ? (
              <div className="text-sm text-slate-400">설정 정보를 불러오는 중...</div>
            ) : accounts.length === 0 ? (
              <div className="rounded-lg border border-dashed border-slate-800 px-4 py-6 text-sm text-slate-400">
                아직 연결된 거래소 계정이 없습니다.
              </div>
            ) : (
              <div className="space-y-3">
                {accounts.map((account) => (
                  <div
                    key={account.id}
                    className="rounded-xl border border-slate-800 bg-slate-950/50 p-4"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-slate-100">
                          {account.exchange_id.toUpperCase()}
                        </p>
                        <p className="mt-1 text-xs text-slate-400">
                          {account.is_testnet ? 'Testnet' : 'Live'} · 생성일 {formatDateTime(account.created_at)}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleDeleteAccount(account.id)}
                        disabled={deletingAccountId === account.id}
                        className="text-sm text-red-300 hover:text-red-200 disabled:opacity-50"
                      >
                        {deletingAccountId === account.id ? '삭제 중...' : '삭제'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="card space-y-4">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <h3 className="text-lg font-semibold text-slate-100">잔고 동기화</h3>
                <p className="text-sm text-slate-400">
                  활성 거래소 계정 기준으로 현재 잔고를 읽어옵니다.
                </p>
              </div>
              <button
                type="button"
                onClick={handleSyncBalance}
                disabled={syncingBalance}
                className="btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {syncingBalance ? '동기화 중...' : '지금 동기화'}
              </button>
            </div>

            {balanceMessage && (
              <div className="rounded-lg border border-emerald-700 bg-emerald-900/30 px-4 py-3 text-sm text-emerald-100">
                {balanceMessage}
              </div>
            )}

            {balanceError && (
              <div className="rounded-lg border border-red-700 bg-red-900/40 px-4 py-3 text-sm text-red-100">
                {balanceError}
              </div>
            )}

            {balanceMeta ? (
              <div className="rounded-lg border border-slate-800 bg-slate-950/50 px-4 py-3 text-sm text-slate-300">
                {balanceMeta.exchangeId.toUpperCase()} · {balanceMeta.isTestnet ? 'Testnet' : 'Live'} · 최근 동기화 {formatDateTime(balanceMeta.syncedAt)}
              </div>
            ) : (
              <div className="rounded-lg border border-dashed border-slate-800 px-4 py-6 text-sm text-slate-400">
                활성 거래소 계정이 없거나 아직 잔고를 읽어오지 않았습니다.
              </div>
            )}

            {balances.length > 0 && (
              <div className="overflow-hidden rounded-xl border border-slate-800">
                <table className="min-w-full divide-y divide-slate-800 text-sm">
                  <thead className="bg-slate-900/80 text-slate-400">
                    <tr>
                      <th className="px-4 py-3 text-left font-medium">자산</th>
                      <th className="px-4 py-3 text-right font-medium">가용</th>
                      <th className="px-4 py-3 text-right font-medium">주문중</th>
                      <th className="px-4 py-3 text-right font-medium">합계</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800 bg-slate-950/40">
                    {balances.map((balance) => (
                      <tr key={balance.symbol}>
                        <td className="px-4 py-3 text-slate-100">{balance.symbol}</td>
                        <td className="px-4 py-3 text-right text-slate-300">{balance.available}</td>
                        <td className="px-4 py-3 text-right text-slate-300">{balance.locked}</td>
                        <td className="px-4 py-3 text-right text-slate-100">{balance.total}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}
