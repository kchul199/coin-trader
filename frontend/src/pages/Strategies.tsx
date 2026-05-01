import { useEffect, useState } from 'react'
import { Plus, RefreshCw } from 'lucide-react'
import { useStrategyStore } from '@/stores/strategyStore'
import { StrategyCard } from '@/components/strategy/StrategyCard'
import { ConditionBuilder } from '@/components/strategy/ConditionBuilder'
import { Strategy, ConditionNode, OrderConfig, SerializedConditionNode, StrategyUpsertPayload } from '@/types'

function createDefaultCondition(): ConditionNode {
  return {
    operator: 'AND',
    conditions: [
      { indicator: 'RSI', params: { timeframe: '1h', period: 14 }, compareOperator: 'lt', value: 30 },
    ],
  }
}

function createDefaultOrder(): OrderConfig {
  return {
    side: 'buy',
    type: 'market',
    quantity_type: 'balance_pct',
    quantity_value: 10,
    take_profit_pct: 4,
    stop_loss_pct: 2,
  }
}

function isGroupNode(node: ConditionNode | SerializedConditionNode | null | undefined) {
  return Array.isArray(node?.conditions)
}

function getLeafCompareTo(node: ConditionNode & { indicator?: string }) {
  if (node.compare_to) {
    return node.compare_to
  }
  if (node.indicator === 'VOLUME' && node.compareOperator === 'gt_multiple') {
    return 'volume_ma_20'
  }
  return undefined
}

function convertBuilderToTree(node: ConditionNode): SerializedConditionNode {
  if (isGroupNode(node)) {
    return {
      operator: node.operator || 'AND',
      conditions: (node.conditions || []).map(convertBuilderToTree),
    }
  }
  return {
    indicator: node.indicator,
    params: node.params || {},
    operator: node.compareOperator,
    value: node.value,
    compare_to: getLeafCompareTo(node),
  }
}

function convertTreeToBuilder(node?: SerializedConditionNode | null): ConditionNode {
  if (!node) {
    return createDefaultCondition()
  }

  if (isGroupNode(node)) {
    return {
      operator: node.operator === 'OR' ? 'OR' : 'AND',
      conditions: (node.conditions || []).map(convertTreeToBuilder),
    }
  }

  return {
    indicator: node.indicator,
    params: node.params || {},
    compareOperator: node.compareOperator || node.operator,
    value: node.value,
    compare_to: node.compare_to,
  }
}

export default function Strategies() {
  const strategies = useStrategyStore((s) => s.strategies)
  const loading = useStrategyStore((s) => s.loading)
  const fetchStrategies = useStrategyStore((s) => s.fetchStrategies)
  const createStrategy = useStrategyStore((s) => s.createStrategy)
  const updateStrategy = useStrategyStore((s) => s.updateStrategy)
  const [showModal, setShowModal] = useState(false)
  const [editing, setEditing] = useState<Strategy | null>(null)

  // Form state
  const [name, setName] = useState('')
  const [symbol, setSymbol] = useState('BTC/USDT')
  const [timeframe, setTimeframe] = useState('1h')
  const [aiMode, setAiMode] = useState<Strategy['ai_mode']>('off')
  const [priority, setPriority] = useState(5)
  const [conditionTree, setConditionTree] = useState<ConditionNode>(createDefaultCondition())
  const [orderConfig, setOrderConfig] = useState<OrderConfig>(createDefaultOrder())
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    void fetchStrategies()
  }, [fetchStrategies])

  const openCreate = () => {
    setEditing(null)
    setName('')
    setSymbol('BTC/USDT')
    setTimeframe('1h')
    setAiMode('off')
    setPriority(5)
    setConditionTree(createDefaultCondition())
    setOrderConfig(createDefaultOrder())
    setShowModal(true)
  }

  const openEdit = (s: Strategy) => {
    setEditing(s)
    setName(s.name)
    setSymbol(s.symbol)
    setTimeframe(s.timeframe)
    setAiMode(s.ai_mode)
    setPriority(s.priority)
    setConditionTree(convertTreeToBuilder(s.condition_tree))
    setOrderConfig(s.order_config || createDefaultOrder())
    setShowModal(true)
  }

  const handleSave = async () => {
    if (!name.trim()) return
    setSaving(true)
    try {
      const payload: StrategyUpsertPayload = {
        name,
        symbol,
        timeframe,
        ai_mode: aiMode,
        priority,
        condition_tree: convertBuilderToTree(conditionTree),
        order_config: orderConfig,
      }
      if (editing) {
        await updateStrategy(editing.id, payload)
      } else {
        await createStrategy(payload)
      }
      setShowModal(false)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-white">전략 관리</h1>
        <div className="flex gap-2">
          <button onClick={fetchStrategies} className="p-2 bg-gray-800 border border-gray-700 rounded hover:bg-gray-700 text-gray-400">
            <RefreshCw size={16} />
          </button>
          <button onClick={openCreate} className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded font-medium text-sm">
            <Plus size={16} /> 전략 추가
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-48 text-gray-400">
          <div className="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full mr-2" />
          로딩 중...
        </div>
      ) : strategies.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-48 text-gray-500">
          <p className="mb-3">등록된 전략이 없습니다.</p>
          <button onClick={openCreate} className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded text-sm">
            <Plus size={14} /> 첫 전략 만들기
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {strategies.map((s) => (
            <StrategyCard key={s.id} strategy={s} onEdit={openEdit} />
          ))}
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between p-5 border-b border-gray-700">
              <h2 className="text-lg font-bold text-white">{editing ? '전략 편집' : '새 전략'}</h2>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-white text-xl">✕</button>
            </div>
            <div className="p-5 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">전략 이름</label>
                  <input
                    className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="RSI 전략"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">심볼</label>
                  <input
                    className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm"
                    value={symbol}
                    onChange={(e) => setSymbol(e.target.value)}
                    placeholder="BTC/USDT"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">시간 프레임</label>
                  <select className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm" value={timeframe} onChange={(e) => setTimeframe(e.target.value)}>
                    {['1m','5m','15m','30m','1h','4h','1d'].map((t) => <option key={t}>{t}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">AI 자문 모드</label>
                  <select className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm" value={aiMode} onChange={(e) => setAiMode(e.target.value as Strategy['ai_mode'])}>
                    <option value="off">끄기</option>
                    <option value="observe">의견만 참고</option>
                    <option value="semi_auto">반자동 (승인 필요)</option>
                    <option value="auto">자동 실행</option>
                  </select>
                </div>
              </div>

              <ConditionBuilder value={conditionTree} onChange={setConditionTree} />

              <div className="grid grid-cols-2 gap-3 p-3 bg-gray-800/50 rounded-lg border border-gray-700">
                <div>
                  <label className="block text-xs text-gray-400 mb-1">매수/매도</label>
                  <select className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-white text-sm" value={orderConfig.side} onChange={(e) => setOrderConfig({ ...orderConfig, side: e.target.value as OrderConfig['side'] })}>
                    <option value="buy">매수</option>
                    <option value="sell">매도</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">주문 비율 (%)</label>
                  <input type="number" className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-white text-sm" value={orderConfig.quantity_value} onChange={(e) => setOrderConfig({ ...orderConfig, quantity_value: parseFloat(e.target.value), quantity_type: 'balance_pct' })} />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">익절 (%)</label>
                  <input type="number" step="0.1" className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-white text-sm" value={orderConfig.take_profit_pct || ''} onChange={(e) => setOrderConfig({ ...orderConfig, take_profit_pct: parseFloat(e.target.value) })} />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">손절 (%)</label>
                  <input type="number" step="0.1" className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-white text-sm" value={orderConfig.stop_loss_pct || ''} onChange={(e) => setOrderConfig({ ...orderConfig, stop_loss_pct: parseFloat(e.target.value) })} />
                </div>
              </div>
            </div>
            <div className="flex gap-3 p-5 border-t border-gray-700">
              <button onClick={() => setShowModal(false)} className="flex-1 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded text-sm">취소</button>
              <button
                onClick={handleSave}
                disabled={saving || !name.trim()}
                className="flex-1 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded text-sm font-medium"
              >
                {saving ? '저장 중...' : '저장'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
