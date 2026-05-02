import { useEffect, useState } from 'react'
import { Plus, RefreshCw } from 'lucide-react'
import { useStrategyStore } from '@/stores/strategyStore'
import { StrategyCard } from '@/components/strategy/StrategyCard'
import { ConditionBuilder } from '@/components/strategy/ConditionBuilder'
import { Strategy, ConditionNode, OrderConfig, SerializedConditionNode, StrategyUpsertPayload } from '@/types'
import { DEFAULT_STRATEGY_SYMBOL } from '@/utils/market'

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
    trailing_stop: false,
    trailing_stop_pct: 1.5,
    split_count: 1,
  }
}

interface StrategyTemplate {
  id: string
  name: string
  description: string
  symbol: string
  timeframe: string
  aiMode: Strategy['ai_mode']
  priority: number
  conditionTree: ConditionNode
  orderConfig: OrderConfig
}

const STRATEGY_TEMPLATES: StrategyTemplate[] = [
  {
    id: 'rsi-rebound',
    name: 'RSI 반등',
    description: '과매도 구간 진입 시 분할 매수용 기본 템플릿',
    symbol: DEFAULT_STRATEGY_SYMBOL,
    timeframe: '1h',
    aiMode: 'observe',
    priority: 5,
    conditionTree: {
      operator: 'AND',
      conditions: [
        { indicator: 'RSI', params: { timeframe: '1h', period: 14 }, compareOperator: 'lt', value: 30 },
        { indicator: 'PRICE', params: { timeframe: '1h', period: 20 }, compareOperator: 'crosses_above_ma' },
      ],
    },
    orderConfig: createDefaultOrder(),
  },
  {
    id: 'breakout',
    name: '가격 돌파',
    description: '20EMA 상향 돌파와 거래량 급증을 함께 보는 추세 템플릿',
    symbol: DEFAULT_STRATEGY_SYMBOL,
    timeframe: '1h',
    aiMode: 'observe',
    priority: 6,
    conditionTree: {
      operator: 'AND',
      conditions: [
        { indicator: 'PRICE', params: { timeframe: '1h', period: 20 }, compareOperator: 'crosses_above_ema' },
        { indicator: 'VOLUME', params: { timeframe: '1h' }, compareOperator: 'gt_multiple', value: 1.8 },
      ],
    },
    orderConfig: {
      ...createDefaultOrder(),
      take_profit_pct: 6,
      stop_loss_pct: 2.5,
      trailing_stop: true,
      trailing_stop_pct: 1.8,
      split_count: 2,
    },
  },
  {
    id: 'mean-reversion',
    name: '평균 회귀',
    description: '볼린저 하단 이탈과 RSI 확인을 묶은 눌림목 템플릿',
    symbol: DEFAULT_STRATEGY_SYMBOL,
    timeframe: '4h',
    aiMode: 'off',
    priority: 4,
    conditionTree: {
      operator: 'AND',
      conditions: [
        { indicator: 'BB', params: { timeframe: '4h', period: 20, std: 2 }, compareOperator: 'price_below_lower' },
        { indicator: 'RSI', params: { timeframe: '4h', period: 14 }, compareOperator: 'lt', value: 35 },
      ],
    },
    orderConfig: { ...createDefaultOrder(), quantity_value: 15 },
  },
]

function cloneTemplateCondition(tree: ConditionNode) {
  return JSON.parse(JSON.stringify(tree)) as ConditionNode
}

function cloneTemplateOrder(order: OrderConfig) {
  return JSON.parse(JSON.stringify(order)) as OrderConfig
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
  const [symbol, setSymbol] = useState(DEFAULT_STRATEGY_SYMBOL)
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
    setSymbol(DEFAULT_STRATEGY_SYMBOL)
    setTimeframe('1h')
    setAiMode('off')
    setPriority(5)
    setConditionTree(createDefaultCondition())
    setOrderConfig(createDefaultOrder())
    setShowModal(true)
  }

  const applyTemplate = (template: StrategyTemplate) => {
    setEditing(null)
    setName(template.name)
    setSymbol(template.symbol)
    setTimeframe(template.timeframe)
    setAiMode(template.aiMode)
    setPriority(template.priority)
    setConditionTree(cloneTemplateCondition(template.conditionTree))
    setOrderConfig(cloneTemplateOrder(template.orderConfig))
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

  const setOptionalOrderNumber = (
    field: 'take_profit_pct' | 'stop_loss_pct' | 'trailing_stop_pct',
    rawValue: string
  ) => {
    setOrderConfig((prev) => ({
      ...prev,
      [field]: rawValue === '' ? undefined : Number(rawValue),
    }))
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

      <section className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        {STRATEGY_TEMPLATES.map((template) => (
          <button
            key={template.id}
            type="button"
            onClick={() => applyTemplate(template)}
            className="rounded-xl border border-slate-800 bg-slate-900/70 p-4 text-left transition hover:border-blue-700 hover:bg-slate-900"
          >
            <p className="text-sm font-semibold text-slate-100">{template.name}</p>
            <p className="mt-1 text-xs text-slate-400">{template.description}</p>
            <p className="mt-3 text-xs text-sky-300">{template.symbol} · {template.timeframe} · AI {template.aiMode}</p>
          </button>
        ))}
      </section>

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
              {!editing && (
                <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
                  <p className="text-xs font-medium text-slate-300">빠른 시작 템플릿</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {STRATEGY_TEMPLATES.map((template) => (
                      <button
                        key={template.id}
                        type="button"
                        onClick={() => applyTemplate(template)}
                        className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300 hover:border-blue-600 hover:text-white"
                      >
                        {template.name}
                      </button>
                    ))}
                  </div>
                </div>
              )}

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
                    placeholder={DEFAULT_STRATEGY_SYMBOL}
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
                  <input type="number" step="0.1" className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-white text-sm" value={orderConfig.take_profit_pct || ''} onChange={(e) => setOptionalOrderNumber('take_profit_pct', e.target.value)} />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">손절 (%)</label>
                  <input type="number" step="0.1" className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-white text-sm" value={orderConfig.stop_loss_pct || ''} onChange={(e) => setOptionalOrderNumber('stop_loss_pct', e.target.value)} />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">분할 주문 수</label>
                  <input
                    type="number"
                    min="1"
                    max="5"
                    className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-white text-sm"
                    value={orderConfig.split_count || 1}
                    onChange={(e) => setOrderConfig({ ...orderConfig, split_count: Math.max(1, parseInt(e.target.value || '1', 10)) })}
                  />
                </div>
                <div className="space-y-2">
                  <label className="block text-xs text-gray-400">트레일링 스탑</label>
                  <label className="flex items-center gap-2 text-sm text-gray-300">
                    <input
                      type="checkbox"
                      checked={Boolean(orderConfig.trailing_stop)}
                      onChange={(e) =>
                        setOrderConfig({
                          ...orderConfig,
                          trailing_stop: e.target.checked,
                          trailing_stop_pct: orderConfig.trailing_stop_pct || 1.5,
                        })
                      }
                    />
                    활성화
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    min="0.1"
                    disabled={!orderConfig.trailing_stop}
                    className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-white text-sm disabled:opacity-50"
                    value={orderConfig.trailing_stop_pct || ''}
                    onChange={(e) => setOptionalOrderNumber('trailing_stop_pct', e.target.value)}
                    placeholder="예: 1.5"
                  />
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
