import client from '../client'

export const emergencyApi = {
  stopStrategy: (strategyId: string, reason = '사용자 요청') =>
    client.post(`/emergency/stop/${strategyId}`, { reason }),

  stopAll: (reason = '전체 긴급 정지') =>
    client.post('/emergency/stop/global', { reason }),

  clearStop: (strategyId: string) =>
    client.delete(`/emergency/stop/${strategyId}`),

  getStatus: () =>
    client.get<{
      global_stop: boolean
      global_stop_reason: string | null
      strategies: Array<{
        strategy_id: string
        strategy_name: string
        stopped: boolean
        reason: string | null
      }>
    }>('/emergency/status'),
}
