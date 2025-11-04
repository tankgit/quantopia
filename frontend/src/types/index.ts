// API类型定义

export interface DataFile {
  file_id: string;
  type: 'generated' | 'fetched';
  length: number;
  base_mean?: number;
  trend?: 'up' | 'stable' | 'down';
  start_price?: number;
  end_price?: number;
  volatility_prob?: number;
  volatility_scale?: number;
  generated_at: string;
  seed?: number | null;
  // 爬取数据特有字段
  symbol?: string;
  mode?: string;
  start_time?: string;
}

export interface DataFileDetail extends DataFile {
  prices: number[];
  data_length: number;
  points?: Array<{ timestamp: string; quote_session: string; price: number | null }>;
}

export interface DataGenerateRequest {
  length: number;
  base_mean: number;
  trend: 'up' | 'stable' | 'down';
  start_price?: number | null;
  end_price?: number | null;
  volatility_prob: number;
  volatility_scale: number;
  seed?: number | null;
}

export interface Strategy {
  name: string;
  description: string;
  params: Record<string, any>;
}

export interface BacktestCreateRequest {
  data_file_id: string;
  strategy_name: string;
  strategy_params: Record<string, any>;
  initial_cash: number;
  commission_rate: number;
}

export interface BacktestResult {
  run_id: string;
  strategy_name: string;
  data_file_id: string;
  stats: BacktestStats;
  history_length: number;
}

export interface BacktestListItem {
  run_id: string;
  data_file_id: string;
  strategy_name: string;
  start_time: string;
  stats: {
    total_return_pct: number;
    win_rate: number;
    total_trades: number;
    total_return: number;
    final_value: number;
    max_drawdown_pct: number;
    buy_count: number;
    sell_count: number;
  };
}

export interface BacktestStats {
  run_id: string;
  final_cash: number;
  final_position: number;
  final_value: number;
  initial_cash: number;
  total_return: number;
  total_return_pct: number;
  final_price: number;
  buy_count: number;
  sell_count: number;
  total_trades: number;
  max_drawdown: number;
  max_drawdown_pct: number;
  price_change: number;
  price_change_pct: number;
  max_price: number;
  min_price: number;
  initial_price: number;
  // 新增指标
  win_rate?: number;  // 胜率 (%)
  winning_trades?: number;  // 盈利交易数
  losing_trades?: number;  // 亏损交易数
  profit_loss_ratio?: number;  // 盈亏比
  sharpe_ratio?: number;  // 夏普比率
  avg_holding_period?: number;  // 平均持仓周期（数据点）
  total_trade_pairs?: number;  // 交易对数量
}

export interface BacktestDetail {
  run_id: string;
  config: {
    strategy_name: string;
    strategy_params: Record<string, any>;
    data_file_id: string;
    data_metadata: DataFile;
    initial_cash: number;
    commission_rate: number;
  };
  start_time: string;
  end_time: string;
  final_stats: BacktestStats;
  total_signals: number;
  total_trades: number;
  logs: LogEntry[];
  signals: SignalEntry[];
  trades: TradeEntry[];
}

export interface LogEntry {
  timestamp: string;
  type: string;
  [key: string]: any;
}

export interface SignalEntry {
  timestamp: string;
  type: 'strategy_signal';
  data_index: number;
  price: number;
  signal: 'buy' | 'sell' | 'hold';
  strategy_info: Record<string, any>;
}

export interface TradeEntry {
  timestamp: string;
  type: 'trade';
  data_index: number;
  trade_type: 'buy' | 'sell';
  price: number;
  quantity: number;
  cash_after: number;
  position_after: number;
  trade_info: Record<string, any>;
  summary?: string;  // AI分析的总结
}

// 实盘数据爬取任务类型
export interface FetchInterval {
  value: number;
  unit: 'seconds' | 'minutes' | 'hours';
}

export interface FetchDuration {
  mode: 'permanent' | 'finite';
  days?: number;
  hours?: number;
  minutes?: number;
  seconds?: number;
}

export interface FetchTaskCreateRequest {
  symbol: string;
  mode: 'paper' | 'live';
  interval: FetchInterval;
  sessions: string[];
  duration: FetchDuration;
}

export interface FetchTaskSummary {
  task_id: string;
  symbol: string;
  mode: 'paper' | 'live';
  interval: FetchInterval;
  sessions: string[];
  status: string;
  started_at: string;
}

export interface FetchTaskDetailResponse {
  config: any;
  latest_points: { timestamp: string; price: number | null }[];
  count: number;
}

