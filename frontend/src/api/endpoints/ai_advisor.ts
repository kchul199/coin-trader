import client from '../client'

export interface AiConsultation {
  id: string
  strategy_id: string
  order_id: string | null
  model: string
  decision: 'execute' | 'hold' | 'avoid'
  confidence: number
  reason: string
  risk_level: 'low' | 'medium' | 'high'
  key_concerns: string[]
  user_approved: boolean | null
  latency_ms: number
  created_at: string
}

export interface AiStats {
  total: number
  decision_distribution: { execute: number; hold: number; avoid: number }
  avg_confidence: number | null
  avg_latency_ms: number | null
  risk_distribution: { low: number; medium: number; high: number }
}

export interface ApprovalRequest {
  strategy_id: string
  strategy_name: string
  symbol: string
  decision: 'execute' | 'hold' | 'avoid'
  confidence: number
  reason: string
  risk_level: 'low' | 'medium' | 'high'
  key_concerns: string[]
  status: 'pending' | 'approved' | 'rejected'
  created_at: string | null
  updated_at: string | null
}

export const aiAdvisorApi = {
  listConsultations: (params?: {
    strategy_id?: string
    decision?: string
    limit?: number
    offset?: number
  }) =>
    client.get<{ items: AiConsultation[]; total: number; limit: number; offset: number }>(
      '/ai-advisor/consultations',
      { params }
    ),

  getLatest: (strategyId: string) =>
    client.get(`/ai-advisor/consultations/${strategyId}/latest`),

  refresh: (strategyId: string) =>
    client.post(`/ai-advisor/refresh/${strategyId}`),

  listApprovals: (status = 'pending') =>
    client.get<{ items: ApprovalRequest[]; total: number }>('/ai-advisor/approvals', {
      params: { status },
    }),

  approve: (strategyId: string) =>
    client.post(`/ai-advisor/approvals/${strategyId}/approve`),

  reject: (strategyId: string) =>
    client.post(`/ai-advisor/approvals/${strategyId}/reject`),

  getStats: (strategyId?: string) =>
    client.get<AiStats>('/ai-advisor/stats', { params: strategyId ? { strategy_id: strategyId } : undefined }),
}
