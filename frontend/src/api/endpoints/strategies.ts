import client from '../client'
import { Strategy } from '../../types'

export const strategiesApi = {
  list: () => client.get<Strategy[]>('/strategies'),
  get: (id: string) => client.get<Strategy>(`/strategies/${id}`),
  create: (data: Partial<Strategy>) => client.post<Strategy>('/strategies', data),
  update: (id: string, data: Partial<Strategy>) => client.put<Strategy>(`/strategies/${id}`, data),
  delete: (id: string) => client.delete(`/strategies/${id}`),
  toggle: (id: string) => client.post<Strategy>(`/strategies/${id}/toggle`),
}
