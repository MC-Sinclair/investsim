export type Direction = 'up' | 'down'
export type Horizon = '1D' | '1W' | '1M'
export type PredictionStatus = 'open' | 'settled'

export interface RecommendationOut {
  symbol: string
  direction: Direction
  confidence: number
  suggested_amount: number
  horizon: Horizon
  rationale: string
}

export interface OpenPredictionIn {
  symbol: string
  amount: number
  direction: Direction
  confidence: number
  horizon: Horizon
  rationale: string
}

export interface PredictionOut {
  id: number
  symbol: string
  created_at: string
  entry_price: number
  amount: number
  shares: number
  horizon: string
  evaluate_at: string
  expected_direction: string
  confidence: number
  rationale: string
  status: PredictionStatus
  exit_price: number | null
  final_value: number | null
  pnl_pct: number | null
  hit: boolean | null
  current_value: number | null
}

export interface PortfolioOut {
  cash_balance: number
  initial_capital: number
  open_predictions_value: number
  total_value: number
}

export interface MetricsOut {
  total_predictions: number
  settled: number
  hits: number
  hit_rate_pct: number
  total_invested: number
  total_final_value: number
  total_return_pct: number
}
