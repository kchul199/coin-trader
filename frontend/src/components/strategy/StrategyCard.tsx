import { Strategy } from '@/types'
import { useStrategyStore } from '@/stores/strategyStore'

interface Props {
  strategy: Strategy
  onEdit: (s: Strategy) => void
}

const AI_MODE_LABELS = {
  off: 'AI 꺼짐',
  auto: '자동',
  semi_auto: '반자동',
  observe: '참고',
}

export function StrategyCard({ strategy, onEdit }: Props) {
  const { toggleStrategy, deleteStrategy } = useStrategyStore()

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 hover:border-gray-600 transition-colors">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-semibold text-white">{strategy.name}</h3>
          <p className="text-sm text-gray-400 mt-0.5">
            {strategy.symbol} · {strategy.timeframe} · 우선순위 {strategy.priority}
          </p>
        </div>
        <button
          onClick={() => toggleStrategy(strategy.id)}
          className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
            strategy.is_active ? 'bg-emerald-500' : 'bg-gray-600'
          }`}
        >
          <span
            className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
              strategy.is_active ? 'translate-x-6' : 'translate-x-1'
            }`}
          />
        </button>
      </div>

      <div className="flex items-center gap-2 mb-4">
        <span className={`px-2 py-0.5 rounded text-xs font-medium ${
          strategy.is_active
            ? 'bg-emerald-900/50 text-emerald-400 border border-emerald-800'
            : 'bg-gray-700 text-gray-400'
        }`}>
          {strategy.is_active ? '● 활성' : '○ 정지'}
        </span>
        <span className="px-2 py-0.5 rounded text-xs bg-blue-900/30 text-blue-400 border border-blue-800">
          AI: {AI_MODE_LABELS[strategy.ai_mode]}
        </span>
        <span className="px-2 py-0.5 rounded text-xs bg-gray-700 text-gray-400">
          {strategy.order_config?.side === 'buy' ? '매수' : '매도'}
        </span>
      </div>

      <div className="flex gap-2">
        <button
          onClick={() => onEdit(strategy)}
          className="flex-1 py-1.5 text-sm bg-gray-700 hover:bg-gray-600 text-white rounded transition-colors"
        >
          편집
        </button>
        <button
          onClick={() => {
            if (confirm(`"${strategy.name}" 전략을 삭제할까요?`)) {
              deleteStrategy(strategy.id)
            }
          }}
          className="px-3 py-1.5 text-sm bg-red-900/30 hover:bg-red-900/60 text-red-400 rounded transition-colors"
        >
          삭제
        </button>
      </div>
    </div>
  )
}
