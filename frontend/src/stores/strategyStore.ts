import { create } from 'zustand'
import { Strategy } from '@/types'
import { strategiesApi } from '@/api/endpoints/strategies'

interface StrategyStore {
  strategies: Strategy[]
  loading: boolean
  error: string | null
  fetchStrategies: () => Promise<void>
  createStrategy: (data: Partial<Strategy>) => Promise<Strategy>
  updateStrategy: (id: string, data: Partial<Strategy>) => Promise<Strategy>
  deleteStrategy: (id: string) => Promise<void>
  toggleStrategy: (id: string) => Promise<void>
}

export const useStrategyStore = create<StrategyStore>((set) => ({
  strategies: [],
  loading: false,
  error: null,

  fetchStrategies: async () => {
    set({ loading: true, error: null })
    try {
      const res = await strategiesApi.list()
      set({ strategies: res.data, loading: false })
    } catch (e: any) {
      set({ error: e.message, loading: false })
    }
  },

  createStrategy: async (data) => {
    const res = await strategiesApi.create(data)
    set((s) => ({ strategies: [res.data, ...s.strategies] }))
    return res.data
  },

  updateStrategy: async (id, data) => {
    const res = await strategiesApi.update(id, data)
    set((s) => ({
      strategies: s.strategies.map((st) => (st.id === id ? res.data : st)),
    }))
    return res.data
  },

  deleteStrategy: async (id) => {
    await strategiesApi.delete(id)
    set((s) => ({ strategies: s.strategies.filter((st) => st.id !== id) }))
  },

  toggleStrategy: async (id) => {
    const res = await strategiesApi.toggle(id)
    set((s) => ({
      strategies: s.strategies.map((st) => (st.id === id ? res.data : st)),
    }))
  },
}))
