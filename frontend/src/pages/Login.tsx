import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { getErrorMessage } from '@/utils/error'

type AuthMode = 'login' | 'register'

function getModeFromPath(pathname: string): AuthMode {
  return pathname === '/register' ? 'register' : 'login'
}

export default function Login() {
  const location = useLocation()
  const navigate = useNavigate()
  const login = useAuthStore((state) => state.login)
  const register = useAuthStore((state) => state.register)

  const [mode, setMode] = useState<AuthMode>(() => getModeFromPath(location.pathname))
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [totpCode, setTotpCode] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setMode(getModeFromPath(location.pathname))
    setError('')
  }, [location.pathname])

  const switchMode = (nextMode: AuthMode) => {
    navigate(nextMode === 'login' ? '/login' : '/register')
  }

  const resetAuthFields = () => {
    setPassword('')
    setConfirmPassword('')
    setTotpCode('')
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (mode === 'register' && password !== confirmPassword) {
      setError('비밀번호 확인이 일치하지 않습니다.')
      return
    }

    setLoading(true)

    try {
      if (mode === 'register') {
        await register(email, password)
      } else {
        await login({
          email,
          password,
          totpCode: totpCode.trim() || undefined,
        })
      }

      resetAuthFields()
      navigate('/')
    } catch (err) {
      setError(
        getErrorMessage(
          err,
          mode === 'register'
            ? '회원가입에 실패했습니다.'
            : '로그인에 실패했습니다.',
        ),
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <p className="text-xs font-semibold tracking-[0.3em] text-sky-400 uppercase mb-3">
            Coin Trader
          </p>
          <h1 className="text-4xl font-bold text-slate-100 mb-2">
            테스트넷 자동매매 워크스페이스
          </h1>
          <p className="text-slate-400">
            회원가입부터 2FA, 거래소 연결까지 한 흐름으로 시작할 수 있습니다.
          </p>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-2 mb-6 grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => switchMode('login')}
            className={`rounded-xl px-4 py-3 text-sm font-medium ${
              mode === 'login'
                ? 'bg-blue-600 text-white'
                : 'text-slate-400 hover:bg-slate-800'
            }`}
          >
            로그인
          </button>
          <button
            type="button"
            onClick={() => switchMode('register')}
            className={`rounded-xl px-4 py-3 text-sm font-medium ${
              mode === 'register'
                ? 'bg-blue-600 text-white'
                : 'text-slate-400 hover:bg-slate-800'
            }`}
          >
            회원가입
          </button>
        </div>

        <form
          onSubmit={handleSubmit}
          className="bg-slate-900 border border-slate-800 rounded-2xl p-8 space-y-5"
        >
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-slate-300 mb-2">
              이메일
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="user@example.com"
              className="input w-full"
              required
              disabled={loading}
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-slate-300 mb-2">
              비밀번호
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="8자 이상 입력"
              className="input w-full"
              required
              minLength={8}
              disabled={loading}
            />
          </div>

          {mode === 'register' && (
            <div>
              <label htmlFor="confirmPassword" className="block text-sm font-medium text-slate-300 mb-2">
                비밀번호 확인
              </label>
              <input
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="비밀번호를 다시 입력"
                className="input w-full"
                required
                minLength={8}
                disabled={loading}
              />
            </div>
          )}

          {mode === 'login' && (
            <div>
              <label htmlFor="totpCode" className="block text-sm font-medium text-slate-300 mb-2">
                2FA 코드
                <span className="text-slate-500 ml-2 text-xs">(설정한 계정만 입력)</span>
              </label>
              <input
                id="totpCode"
                type="text"
                inputMode="numeric"
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="6자리 코드"
                className="input w-full"
                maxLength={6}
                disabled={loading}
              />
            </div>
          )}

          {error && (
            <div className="bg-red-900/50 border border-red-700 rounded-lg p-3 text-red-200 text-sm">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading
              ? mode === 'register'
                ? '계정 생성 중...'
                : '로그인 중...'
              : mode === 'register'
                ? '회원가입 후 시작하기'
                : '로그인'}
          </button>
        </form>

        <div className="mt-6 card space-y-2 text-sm text-slate-400">
          <p className="text-slate-200 font-medium">처음 시작할 때 추천 순서</p>
          <p>1. 회원가입 후 바로 로그인</p>
          <p>2. 설정 화면에서 Binance Testnet API 키 등록</p>
          <p>3. 필요하면 2FA를 활성화하고 다시 로그인 테스트</p>
        </div>
      </div>
    </div>
  )
}
