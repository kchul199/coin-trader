import client from '../client'
import { OrderRecord } from '@/types'

export const ordersApi = {
  list: (page = 1, size = 50, symbol?: string) =>
    client.get<OrderRecord[]>('/orders', { params: { page, size, symbol } }),
}
