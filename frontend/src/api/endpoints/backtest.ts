import client from '../client'

export interface BacktestRunRequest {
  strategy_id: string
  start_date: string   // YYYY-MM-DD
  end_date: string     // YYYY-MM-DD
  initial_capital: number
  commission_pct: number
  slippage_pct: number
}

export interface BacktestJobStatus {
  job_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  result_id?: string
  error?: string
  total_return_pct?: number
}

export interface EquityPoint {
  time: string
  value: number
}

export interface TradeRecord {
  entry_time: string
  exit_time: string
  entry_price: number
  exit_price: number
  quantity: number
  side: string
  pnl: number
  pnl_pct: number
  commission: number
}

export interface BacktestResult {
  id: string
  strategy_id: string
  start_date: string
  end_date: string
  params_snapshot: Record<string, unknown>
  initial_capital: number
  final_capital: number
  total_return_pct: number
  max_drawdown_pct: number
  sharpe_ratio: number
  win_rate: number
  profit_factor: number
  total_trades: number
  ai_on_return_pct: number | null
  ai_off_return_pct: number | null
  commission_pct: number
  slippage_pct: number
  equity_curve: EquityPoint[]
  trade_history: TradeRecord[]
  created_at: string
}

export const backtestApi = {
  run: (data: BacktestRunRequest) =>
    client.post<{ job_id: string; status: string }>('/backtest/run', data),

  getStatus: (jobId: string) =>
    client.get<BacktestJobStatus>(`/backtest/status/${jobId}`),

  getResult: (backtestId: string) =>
    client.get<BacktestResult>(`/backtest/${backtestId}`),

  getHistory: (params?: { strategy_id?: string; limit?: number; offset?: number }) =>
    client.get<{ items: BacktestResult[]; total: number; limit: number; offset: number }>(
      '/backtest/history',
      { params }
    ),
}
