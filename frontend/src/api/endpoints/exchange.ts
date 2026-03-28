import client from '../client'

export const exchangeApi = {
  listAccounts: () => client.get('/exchange/accounts'),
  createAccount: (data: any) => client.post('/exchange/accounts', data),
  deleteAccount: (id: string) => client.delete(`/exchange/accounts/${id}`),
  getBalance: () => client.get('/exchange/balance'),
  syncBalance: () => client.post('/exchange/balance/sync'),
}
