import client from '../client'
import { PortfolioPosition } from '@/types'

export const portfolioApi = {
  list: () => client.get<PortfolioPosition[]>('/portfolio'),
}
