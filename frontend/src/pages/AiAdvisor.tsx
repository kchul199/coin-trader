import { useEffect, useState } from 'react'
import { RefreshCw, Brain, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { aiAdvisorApi, AiConsultation, AiStats } from '@/api/endpoints/ai_advisor'
import { useStrategyStore } from '@/stores/strategyStore'

const DECISION_COLORS: Record<string, string> = {
  execute: 'text-emerald-400 bg-emerald-900/30 border-emerald-800',
  hold: 'text-amber-400 bg-amber-900/30 border-amber-800',
  avoid: 'text-red-400 bg-red-900/30 border-red-800',
}
const DECISION_LABELS: Record<string, string> = {
  execute: '실행 권장',
  hold: '대기',
  avoid: '회피',
}
const RISK_COLORS: Record<string, string> = {
  low: 'text-emerald-400',
  medium: 'text-amber-400',
  high: 'text-red-400',
}
const RISK_LABELS: Record<string, string> = {
  low: '낮음',
  medium: '보통',
  high: '높음',
}

function DecisionBadge({ decision }: { decision: string }) {
  const color = DECISION_COLORS[decision] || 'text-gray-400 bg-gray-700 border-gray-700'
  const label = DECISION_LABELS[decision] || decision
  return (
    <span className={`text-xs px-2.5 py-1 rounded-full font-semibold border ${color}`}>
      {label}
    </span>
  )
}

function ConsultCard({ consult, strategyName }: { consult: AiConsultation; strategyName?: string }) {
  const riskColor = RISK_COLORS[consult.risk_level] || 'text-gray-400'
  const date = new Date(consult.created_at)

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 space-y-3 hover:border-gray-600 transition-colors">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 flex-wrap">
          <DecisionBadge decision={consult.decision} />
          <span className="text-xs text-gray-400">
            신뢰도 <span className="font-semibold text-white">{consult.confidence}%</span>
          </span>
          <span className={`text-xs font-medium ${riskColor}`}>
            리스크: {RISK_LABELS[consult.risk_level] || consult.risk_level}
          </span>
        </div>
        <div className="text-right flex-shrink-0">
          {strategyName && <p className="text-xs text-blue-400 font-medium">{strategyName}</p>}
          <p className="text-xs text-gray-500">{date.toLocaleString('ko-KR')}</p>
        </div>
      </div>

      {consult.reason && (
        <p className="text-sm text-gray-300 leading-relaxed">{consult.reason}</p>
      )}

      {consult.key_concerns && consult.key_concerns.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {consult.key_concerns.map((concern, i) => (
            <span key={i} className="text-xs bg-gray-700 text-gray-300 px-2 py-0.5 rounded">
              {concern}
            </span>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between text-xs text-gray-600 pt-1 border-t border-gray-700">
        <span>{consult.model}</span>
        <span>{consult.latency_ms}ms</span>
      </div>
    </div>
  )
}

function StatsPanel({ stats }: { stats: AiStats }) {
  const total = stats.total
  const execPct = total > 0 ? Math.round((stats.decision_distribution.execute / total) * 100) : 0
  const holdPct = total > 0 ? Math.round((stats.decision_distribution.hold / total) * 100) : 0
  const avoidPct = total > 0 ? Math.round((stats.decision_distribution.avoid / total) * 100) : 0

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {[
        { label: '총 자문', value: total, color: 'text-white' },
        { label: '평균 신뢰도', value: stats.avg_confidence != null ? `${stats.avg_confidence}%` : '-', color: 'text-blue-400' },
        { label: '평균 응답', value: stats.avg_latency_ms != null ? `${stats.avg_latency_ms}ms` : '-', color: 'text-gray-300' },
        { label: '실행 권장률', value: `${execPct}%`, color: 'text-emerald-400' },
      ].map((s) => (
        <div key={s.label} className="bg-gray-800 border border-gray-700 rounded-lg p-3">
          <p className="text-xs text-gray-400 mb-1">{s.label}</p>
          <p className={`text-xl font-bold ${s.color}`}>{s.value}</p>
        </div>
      ))}
      <div className="col-span-2 sm:col-span-4 bg-gray-800 border border-gray-700 rounded-lg p-3">
        <p className="text-xs text-gray-400 mb-2">결정 분포</p>
        <div className="flex gap-4 text-sm flex-wrap">
          <span className="text-emerald-400">실행 {stats.decision_distribution.execute} ({execPct}%)</span>
          <span className="text-amber-400">대기 {stats.decision_distribution.hold} ({holdPct}%)</span>
          <span className="text-red-400">회피 {stats.decision_distribution.avoid} ({avoidPct}%)</span>
        </div>
        <div className="mt-2 h-2 bg-gray-700 rounded-full overflow-hidden flex">
          {execPct > 0 && <div className="bg-emerald-500 h-full" style={{ width: `${execPct}%` }} />}
          {holdPct > 0 && <div className="bg-amber-500 h-full" style={{ width: `${holdPct}%` }} />}
          {avoidPct > 0 && <div className="bg-red-500 h-full" style={{ width: `${avoidPct}%` }} />}
        </div>
      </div>
    </div>
  )
}

export default function AiAdvisor() {
  const { strategies, fetchStrategies } = useStrategyStore()
  const [consultations, setConsultations] = useState<AiConsultation[]>([])
  const [stats, setStats] = useState<AiStats | null>(null)
  const [loading, setLoading] = useState(false)
  const [selectedStrategy, setSelectedStrategy] = useState<string>('')
  const [decisionFilter, setDecisionFilter] = useState<string>('')
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const limit = 10
  const [refreshing, setRefreshing] = useState<string | null>(null)

  useEffect(() => {
    fetchStrategies()
  }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const [consultRes, statsRes] = await Promise.all([
        aiAdvisorApi.listConsultations({
          strategy_id: selectedStrategy || undefined,
          decision: decisionFilter || undefined,
          limit,
          offset,
        }),
        aiAdvisorApi.getStats(selectedStrategy || undefined),
      ])
      setConsultations(consultRes.data.items)
      setTotal(consultRes.data.total)
      setStats(statsRes.data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [selectedStrategy, decisionFilter, offset])

  const handleRefresh = async (strategyId: string) => {
    setRefreshing(strategyId)
    try {
      await aiAdvisorApi.refresh(strategyId)
      setTimeout(loadData, 3000) // 3초 후 갱신
    } catch (e) {
      console.error(e)
    } finally {
      setRefreshing(null)
    }
  }

  const strategyNameMap = Object.fromEntries(strategies.map((s) => [s.id, s.name]))
  const aiStrategies = strategies.filter((s) => s.ai_mode !== 'off')

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <Brain size={22} className="text-blue-400" />
          AI 자문
        </h1>
        <button
          onClick={loadData}
          disabled={loading}
          className="p-2 bg-gray-800 border border-gray-700 rounded hover:bg-gray-700 text-gray-400 disabled:opacity-50"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* AI 모드 활성 전략 */}
      {aiStrategies.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-gray-400 mb-3">AI 활성 전략</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
            {aiStrategies.map((s) => (
              <div key={s.id} className="bg-gray-800 border border-gray-700 rounded-lg p-3 flex items-center justify-between">
                <div>
                  <p className="font-medium text-white text-sm">{s.name}</p>
                  <p className="text-xs text-gray-400">{s.symbol} · AI: {s.ai_mode}</p>
                </div>
                <button
                  onClick={() => handleRefresh(s.id)}
                  disabled={refreshing === s.id}
                  className="p-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded text-xs flex items-center gap-1"
                  title="AI 자문 갱신"
                >
                  <RefreshCw size={12} className={refreshing === s.id ? 'animate-spin' : ''} />
                  갱신
                </button>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 통계 */}
      {stats && stats.total > 0 && (
        <section>
          <h2 className="text-sm font-medium text-gray-400 mb-3">자문 통계</h2>
          <StatsPanel stats={stats} />
        </section>
      )}

      {/* 필터 */}
      <section>
        <div className="flex gap-2 mb-4 flex-wrap">
          <select
            className="bg-gray-800 border border-gray-700 text-white text-sm rounded px-3 py-1.5"
            value={selectedStrategy}
            onChange={(e) => { setSelectedStrategy(e.target.value); setOffset(0) }}
          >
            <option value="">전체 전략</option>
            {strategies.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
          <select
            className="bg-gray-800 border border-gray-700 text-white text-sm rounded px-3 py-1.5"
            value={decisionFilter}
            onChange={(e) => { setDecisionFilter(e.target.value); setOffset(0) }}
          >
            <option value="">전체 결정</option>
            <option value="execute">실행 권장</option>
            <option value="hold">대기</option>
            <option value="avoid">회피</option>
          </select>
          <span className="ml-auto text-sm text-gray-400 self-center">
            총 {total}건
          </span>
        </div>

        {/* 자문 목록 */}
        {loading ? (
          <div className="flex items-center justify-center h-48 text-gray-400">
            <div className="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full mr-2" />
            로딩 중...
          </div>
        ) : consultations.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-gray-500">
            <Brain size={32} className="mb-3 opacity-40" />
            <p className="text-sm">자문 내역이 없습니다.</p>
            <p className="text-xs mt-1">전략의 AI 자문 모드를 활성화하면 자동으로 기록됩니다.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {consultations.map((c) => (
              <ConsultCard
                key={c.id}
                consult={c}
                strategyName={strategyNameMap[c.strategy_id]}
              />
            ))}
          </div>
        )}

        {/* 페이지네이션 */}
        {total > limit && (
          <div className="flex justify-center gap-2 mt-4">
            <button
              onClick={() => setOffset(Math.max(0, offset - limit))}
              disabled={offset === 0}
              className="px-3 py-1.5 bg-gray-800 border border-gray-700 text-white rounded text-sm disabled:opacity-40"
            >
              이전
            </button>
            <span className="px-3 py-1.5 text-sm text-gray-400">
              {Math.floor(offset / limit) + 1} / {Math.ceil(total / limit)}
            </span>
            <button
              onClick={() => setOffset(offset + limit)}
              disabled={offset + limit >= total}
              className="px-3 py-1.5 bg-gray-800 border border-gray-700 text-white rounded text-sm disabled:opacity-40"
            >
              다음
            </button>
          </div>
        )}
      </section>
    </div>
  )
}
