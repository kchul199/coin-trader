export interface Candle {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export type ConditionParamValue = string | number | boolean | null | undefined;

export interface SerializedConditionNode {
  operator?: string;
  conditions?: SerializedConditionNode[];
  indicator?: string;
  params?: Record<string, ConditionParamValue>;
  compareOperator?: string;
  value?: number;
  compare_to?: string;
}

export interface Strategy {
  id: string;
  name: string;
  symbol: string;
  timeframe: string;
  condition_tree: SerializedConditionNode;
  order_config: OrderConfig;
  exit_condition?: SerializedConditionNode;
  ai_mode: 'off' | 'auto' | 'semi_auto' | 'observe';
  priority: number;
  hold_retry_interval: number;
  hold_max_retry: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ConditionNode {
  operator?: 'AND' | 'OR';
  conditions?: ConditionNode[];
  indicator?: string;
  params?: Record<string, ConditionParamValue>;
  compareOperator?: string;
  value?: number;
  compare_to?: string;
}

export interface StrategyUpsertPayload {
  name: string;
  symbol: string;
  timeframe: string;
  condition_tree: SerializedConditionNode;
  order_config: OrderConfig;
  exit_condition?: SerializedConditionNode;
  ai_mode: Strategy['ai_mode'];
  priority: number;
  hold_retry_interval?: number;
  hold_max_retry?: number;
  is_active?: boolean;
}

export type StrategyUpdatePayload = Partial<StrategyUpsertPayload>;

export interface OrderConfig {
  side: 'buy' | 'sell';
  type: 'market' | 'limit';
  quantity_type: 'fixed_amount' | 'balance_pct' | 'fixed_qty';
  quantity_value: number;
  take_profit_pct?: number;
  stop_loss_pct?: number;
  trailing_stop?: boolean;
  trailing_stop_pct?: number;
  split_count?: number;
}

export interface PriceUpdate {
  type: 'price_update';
  symbol: string;
  price: number;
  change_24h: number;
  volume_24h: number;
  timestamp: number;
}

export interface Balance {
  symbol: string;
  available: number;
  locked: number;
  total: number;
}

export interface ExchangeAccount {
  id: string;
  exchange_id: string;
  is_testnet: boolean;
  is_active: boolean;
  created_at: string;
}

export interface TickerSnapshot {
  symbol: string;
  price: number;
  change_24h: number;
  volume_24h: number;
  bid: number;
  ask: number;
}

export interface OrderRecord {
  id: string;
  exchange_id: string;
  symbol: string;
  side: 'buy' | 'sell';
  order_type: string;
  price: number | null;
  quantity: number;
  filled_quantity: number;
  avg_fill_price: number | null;
  status: string;
  created_at: string;
  filled_at: string | null;
  updated_at: string;
}

export interface PortfolioPosition {
  id: string;
  symbol: string;
  exchange_id: string;
  quantity: number;
  avg_buy_price: number | null;
  initial_capital: number | null;
  last_updated: string;
}
