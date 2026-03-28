import { useState } from 'react'
import { ConditionNode } from '@/types'
import { Plus, Trash2 } from 'lucide-react'

const INDICATORS = ['RSI', 'MACD', 'BB', 'MA', 'EMA', 'STOCH', 'CCI', 'VOLUME']
const TIMEFRAMES = ['1m', '5m', '15m', '30m', '1h', '4h', '1d']
const OPERATORS_NUMERIC = [
  { value: 'lt', label: '<' },
  { value: 'lte', label: '<=' },
  { value: 'gt', label: '>' },
  { value: 'gte', label: '>=' },
]
const OPERATORS_SPECIAL: Record<string, Array<{ value: string; label: string }>> = {
  MACD: [
    { value: 'golden_cross', label: '골든크로스' },
    { value: 'dead_cross', label: '데드크로스' },
  ],
  BB: [
    { value: 'price_below_lower', label: '하단 밴드 하향 돌파' },
    { value: 'price_above_upper', label: '상단 밴드 상향 돌파' },
  ],
  VOLUME: [
    { value: 'gt', label: '>' },
    { value: 'gt_multiple', label: '이평 대비 N배 초과' },
  ],
}

interface LeafEditorProps {
  node: ConditionNode
  onChange: (n: ConditionNode) => void
  onDelete: () => void
}

function LeafEditor({ node, onChange, onDelete }: LeafEditorProps) {
  const indicator = node.indicator || 'RSI'
  const specials = OPERATORS_SPECIAL[indicator] || OPERATORS_NUMERIC

  return (
    <div className="flex items-center gap-2 p-2 bg-gray-900 rounded border border-gray-700">
      <select
        className="bg-gray-800 text-white text-sm rounded px-2 py-1 border border-gray-700"
        value={indicator}
        onChange={(e) => onChange({ ...node, indicator: e.target.value, compareOperator: undefined, value: undefined })}
      >
        {INDICATORS.map((i) => <option key={i}>{i}</option>)}
      </select>

      <select
        className="bg-gray-800 text-white text-sm rounded px-2 py-1 border border-gray-700"
        value={node.params?.timeframe || '1h'}
        onChange={(e) => onChange({ ...node, params: { ...node.params, timeframe: e.target.value } })}
      >
        {TIMEFRAMES.map((t) => <option key={t}>{t}</option>)}
      </select>

      {(indicator === 'RSI' || indicator === 'MA' || indicator === 'EMA' || indicator === 'STOCH' || indicator === 'CCI') && (
        <input
          type="number"
          placeholder="기간"
          className="bg-gray-800 text-white text-sm rounded px-2 py-1 border border-gray-700 w-16"
          value={node.params?.period || ''}
          onChange={(e) => onChange({ ...node, params: { ...node.params, period: parseInt(e.target.value) } })}
        />
      )}

      <select
        className="bg-gray-800 text-white text-sm rounded px-2 py-1 border border-gray-700"
        value={node.compareOperator || ''}
        onChange={(e) => onChange({ ...node, compareOperator: e.target.value })}
      >
        <option value="">조건 선택</option>
        {specials.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>

      {(node.compareOperator === 'lt' || node.compareOperator === 'lte' || node.compareOperator === 'gt' || node.compareOperator === 'gte' || node.compareOperator === 'gt_multiple') && (
        <input
          type="number"
          step="any"
          placeholder="값"
          className="bg-gray-800 text-white text-sm rounded px-2 py-1 border border-gray-700 w-20"
          value={node.value ?? ''}
          onChange={(e) => onChange({ ...node, value: parseFloat(e.target.value) })}
        />
      )}

      <button onClick={onDelete} className="ml-auto text-red-500 hover:text-red-400">
        <Trash2 size={14} />
      </button>
    </div>
  )
}

interface GroupEditorProps {
  node: ConditionNode
  onChange: (n: ConditionNode) => void
  onDelete?: () => void
  depth?: number
}

function GroupEditor({ node, onChange, onDelete, depth = 0 }: GroupEditorProps) {
  const addCondition = () => {
    onChange({
      ...node,
      conditions: [
        ...(node.conditions || []),
        { indicator: 'RSI', params: { timeframe: '1h', period: 14 }, compareOperator: 'lt', value: 30 },
      ],
    })
  }

  const addGroup = () => {
    onChange({
      ...node,
      conditions: [
        ...(node.conditions || []),
        { operator: 'AND', conditions: [] },
      ],
    })
  }

  const updateChild = (idx: number, child: ConditionNode) => {
    const updated = [...(node.conditions || [])]
    updated[idx] = child
    onChange({ ...node, conditions: updated })
  }

  const deleteChild = (idx: number) => {
    onChange({ ...node, conditions: (node.conditions || []).filter((_, i) => i !== idx) })
  }

  const borderColors = ['border-blue-700', 'border-purple-700', 'border-amber-700']
  const borderColor = borderColors[depth % borderColors.length]

  return (
    <div className={`border ${borderColor} rounded-lg p-3 space-y-2 bg-gray-800/30`}>
      <div className="flex items-center gap-2 mb-2">
        <select
          className="bg-gray-800 text-white text-sm font-semibold rounded px-2 py-1 border border-gray-700"
          value={node.operator || 'AND'}
          onChange={(e) => onChange({ ...node, operator: e.target.value as 'AND' | 'OR' })}
        >
          <option value="AND">AND (모두 충족)</option>
          <option value="OR">OR (하나 충족)</option>
        </select>
        {onDelete && (
          <button onClick={onDelete} className="ml-auto text-red-500 hover:text-red-400">
            <Trash2 size={14} />
          </button>
        )}
      </div>

      {(node.conditions || []).map((child, idx) =>
        child.operator ? (
          <GroupEditor
            key={idx}
            node={child}
            onChange={(n) => updateChild(idx, n)}
            onDelete={() => deleteChild(idx)}
            depth={depth + 1}
          />
        ) : (
          <LeafEditor
            key={idx}
            node={child}
            onChange={(n) => updateChild(idx, n)}
            onDelete={() => deleteChild(idx)}
          />
        )
      )}

      <div className="flex gap-2 pt-1">
        <button
          onClick={addCondition}
          className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 px-2 py-1 border border-blue-800 rounded hover:bg-blue-900/20"
        >
          <Plus size={12} /> 조건 추가
        </button>
        <button
          onClick={addGroup}
          className="flex items-center gap-1 text-xs text-purple-400 hover:text-purple-300 px-2 py-1 border border-purple-800 rounded hover:bg-purple-900/20"
        >
          <Plus size={12} /> 그룹 추가
        </button>
      </div>
    </div>
  )
}

interface Props {
  value: ConditionNode
  onChange: (v: ConditionNode) => void
}

export function ConditionBuilder({ value, onChange }: Props) {
  return (
    <div>
      <label className="block text-sm text-gray-400 mb-2">매수 조건 트리</label>
      <GroupEditor node={value} onChange={onChange} />
    </div>
  )
}
