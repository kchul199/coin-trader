import client from '../client'
import { Strategy, StrategyUpsertPayload, StrategyUpdatePayload } from '../../types'

export const strategiesApi = {
  list: () => client.get<Strategy[]>('/strategies'),
  get: (id: string) => client.get<Strategy>(`/strategies/${id}`),
  create: (data: StrategyUpsertPayload) => client.post<Strategy>('/strategies', data),
  update: (id: string, data: StrategyUpdatePayload) => client.put<Strategy>(`/strategies/${id}`, data),
  delete: (id: string) => client.delete(`/strategies/${id}`),
  toggle: (id: string) => client.post<Strategy>(`/strategies/${id}/toggle`),
}
