import client from '../client'
import { Balance, ExchangeAccount } from '@/types'

export interface ExchangeAccountCreateRequest {
  exchange_id: 'binance' | 'upbit' | 'bithumb'
  api_key: string
  api_secret: string
  is_testnet?: boolean
}

export interface BalanceResponse {
  exchange_id: string
  is_testnet: boolean
  balances: Balance[]
  synced_at: string
}

export const exchangeApi = {
  listAccounts: () => client.get<ExchangeAccount[]>('/exchange/accounts'),
  createAccount: (data: ExchangeAccountCreateRequest) =>
    client.post<ExchangeAccount>('/exchange/accounts', data),
  deleteAccount: (id: string) => client.delete(`/exchange/accounts/${id}`),
  getBalance: () => client.get<BalanceResponse>('/exchange/balance'),
  syncBalance: () => client.post<BalanceResponse>('/exchange/balance/sync'),
}
