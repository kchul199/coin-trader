import { create } from 'zustand'

interface PriceStore {
  prices: Record<string, number>
  changes: Record<string, number>
  wsConnected: boolean
  updatePrice: (symbol: string, price: number, change: number) => void
  setWsConnected: (v: boolean) => void
}

export const usePriceStore = create<PriceStore>((set) => ({
  prices: {},
  changes: {},
  wsConnected: false,
  updatePrice: (symbol, price, change) =>
    set((s) => ({
      prices: { ...s.prices, [symbol]: price },
      changes: { ...s.changes, [symbol]: change },
    })),
  setWsConnected: (v) => set({ wsConnected: v }),
}))
