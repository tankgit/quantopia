import { useState, useMemo, useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams, useNavigate } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faArrowLeft, faChartLine, faRobot, faEye, faEyeSlash, faCog, faDownload } from '@fortawesome/free-solid-svg-icons';
import { backtestApi, dataApi } from '../services/api';
import DataChart from '../components/DataChart';
import { formatCurrency, getValueColor } from '../utils/format';
import type { BacktestDetail, TradeEntry } from '../types';

export default function BacktestDetail() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [chartType, setChartType] = useState<'line'>('line');
  const [showAIAnalysis, setShowAIAnalysis] = useState(false);
  
  // 从 localStorage 加载缓存的配置
  const loadCachedConfig = () => {
    try {
      const cached = localStorage.getItem('ai_analysis_config');
      if (cached) {
        const config = JSON.parse(cached);
        return {
          apiKey: config.apiKey || '',
          apiUrl: config.apiUrl || 'https://api.openai.com/v1/chat/completions',
          modelName: config.modelName || 'gpt-4',
        };
      }
    } catch (error) {
      console.error('Failed to load cached AI config:', error);
    }
    return {
      apiKey: '',
      apiUrl: 'https://api.openai.com/v1/chat/completions',
      modelName: 'gpt-4',
    };
  };

  const cachedConfig = loadCachedConfig();
  const [apiKey, setApiKey] = useState(cachedConfig.apiKey);
  const [apiUrl, setApiUrl] = useState(cachedConfig.apiUrl);
  const [modelName, setModelName] = useState(cachedConfig.modelName);
  const [showApiKey, setShowApiKey] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [showParams, setShowParams] = useState(false);
  const [selectedTradeSummary, setSelectedTradeSummary] = useState<string | null>(null);
  const [analysisProgress, setAnalysisProgress] = useState<{
    status: string;
    progress: number;
    message: string;
    total: number;
    current: number;
  } | null>(null);
  const progressIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const { data: backtest, isLoading } = useQuery({
    queryKey: ['backtest', runId],
    queryFn: () => backtestApi.get(runId!),
    enabled: !!runId,
  });

  const { data: stockData } = useQuery({
    queryKey: ['data', backtest?.config.data_file_id],
    queryFn: () => dataApi.get(backtest!.config.data_file_id),
    enabled: !!backtest,
  });

  // 计算每笔交易的盈亏（用于显示win/loss）
  const tradePairs = useMemo(() => {
    if (!backtest) return new Map<number, 'win' | 'loss'>();
    
    const pairs = new Map<number, 'win' | 'loss'>();
    const buyStack: Array<{ entry: TradeEntry; quantity: number; price: number }> = [];
    
    for (const trade of backtest.trades) {
      if (trade.trade_type === 'buy') {
        buyStack.push({
          entry: trade,
          quantity: trade.quantity,
          price: trade.price,
        });
      } else if (trade.trade_type === 'sell') {
        if (buyStack.length > 0) {
          const buyInfo = buyStack.shift()!;
          // 简单计算：卖出价格是否高于买入价格（考虑手续费）
          const commission = trade.price * trade.quantity * backtest.config.commission_rate;
          const buyCommission = buyInfo.price * buyInfo.quantity * backtest.config.commission_rate;
          const profit = (trade.price - buyInfo.price) * trade.quantity - commission - buyCommission;
          pairs.set(trade.data_index, profit >= 0 ? 'win' : 'loss');
        }
      }
    }
    
    return pairs;
  }, [backtest]);

  const startProgressPolling = () => {
    if (!runId) return;
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current);
    }
    progressIntervalRef.current = setInterval(async () => {
      try {
        const progress = await backtestApi.getAnalysisProgress(runId);
        setAnalysisProgress((prev) => {
          if (
            prev &&
            prev.progress === progress.progress &&
            prev.status === progress.status &&
            prev.message === progress.message &&
            prev.current === progress.current &&
            prev.total === progress.total
          ) {
            return prev; // 无变化不触发重渲染
          }
          return progress;
        });
        
        if (progress.status === 'completed' || progress.status === 'error') {
          if (progressIntervalRef.current) {
            clearInterval(progressIntervalRef.current);
            progressIntervalRef.current = null;
          }
          setAnalyzing(false);
          if (progress.status === 'completed') {
            await queryClient.invalidateQueries({ queryKey: ['backtest', runId] });
          }
        }
      } catch (error) {
        // 忽略查询错误
      }
    }, 1500);
  };

  const handleAnalyze = async () => {
    if (!runId || !apiKey || !apiUrl || !modelName) {
      alert('请填写完整的AI分析配置信息');
      return;
    }
    
    setAnalyzing(true);
    setAnalysisProgress(null);
    
    try {
      await backtestApi.analyze(runId, {
        api_key: apiKey,
        api_url: apiUrl,
        model_name: modelName,
      });
      
      // 开始查询进度
      startProgressPolling();
    } catch (error: any) {
      alert(`AI分析启动失败: ${error.response?.data?.detail || error.message}`);
      setAnalyzing(false);
    }
  };

  // 缓存配置到 localStorage
  useEffect(() => {
    try {
      localStorage.setItem('ai_analysis_config', JSON.stringify({
        apiKey,
        apiUrl,
        modelName,
      }));
    } catch (error) {
      console.error('Failed to save AI config to localStorage:', error);
    }
  }, [apiKey, apiUrl, modelName]);

  // 清理定时器
  useEffect(() => {
    return () => {
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
      }
    };
  }, []);

  // 当切换不同的 runId 时，重置进度与定时器，避免显示上一个回测的进度
  useEffect(() => {
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current);
      progressIntervalRef.current = null;
    }
    setAnalysisProgress(null);
    setAnalyzing(false);
  }, [runId]);

  // 进入页面或切换 runId 时，尝试恢复正在进行的AI任务进度
  useEffect(() => {
    const restore = async () => {
      if (!runId) return;
      try {
        const progress = await backtestApi.getAnalysisProgress(runId);
        setAnalysisProgress(progress);
        if (progress.status === 'running') {
          setAnalyzing(true);
          startProgressPolling();
        }
      } catch (error) {
        // 若无任务会返回404，忽略
      }
    };
    restore();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  const stats = backtest?.final_stats;

  // 重型区块：统计指标
  const StatsSection = useMemo(() => {
    if (!stats) return null;
    return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div className="bg-gradient-to-br from-slate-800/60 via-slate-800/50 to-slate-900/60 backdrop-blur-xl rounded-2xl p-6 border-2 border-slate-600/50 hover:border-purple-500/50 shadow-sm hover:shadow-md hover:shadow-purple-500/10 transition-all duration-300">
        <div className="text-xs text-slate-300 mb-2 font-medium">总收益率</div>
        <div className={`text-3xl font-bold drop-shadow-lg ${getValueColor(stats.total_return_pct)}`}>
          {stats.total_return_pct.toFixed(2)}%
        </div>
      </div>
      <div className="bg-gradient-to-br from-slate-800/60 via-slate-800/50 to-slate-900/60 backdrop-blur-xl rounded-2xl p-6 border-2 border-slate-600/50 hover:border-purple-500/50 shadow-sm hover:shadow-md hover:shadow-purple-500/10 transition-all duration-300">
        <div className="text-xs text-slate-300 mb-2 font-medium">总收益 ($)</div>
        <div className={`text-3xl font-bold drop-shadow-lg ${getValueColor(stats.total_return)}`}>
          {formatCurrency(stats.total_return)}
        </div>
      </div>
      <div className="bg-gradient-to-br from-slate-800/60 via-slate-800/50 to-slate-900/60 backdrop-blur-xl rounded-2xl p-6 border-2 border-slate-600/50 hover:border-purple-500/50 shadow-sm hover:shadow-md hover:shadow-purple-500/10 transition-all duration-300">
        <div className="text-xs text-slate-300 mb-2 font-medium">最终价值 ($)</div>
        <div className="text-3xl font-bold text-slate-100 drop-shadow-lg">{formatCurrency(stats.final_value)}</div>
      </div>
      <div className="bg-gradient-to-br from-slate-800/60 via-slate-800/50 to-slate-900/60 backdrop-blur-xl rounded-2xl p-6 border-2 border-slate-600/50 hover:border-purple-500/50 shadow-sm hover:shadow-md hover:shadow-purple-500/10 transition-all duration-300">
        <div className="text-xs text-slate-300 mb-2 font-medium">最大回撤</div>
        <div className="text-3xl font-bold text-green-300 drop-shadow-lg">
          {stats.max_drawdown_pct.toFixed(2)}%
        </div>
      </div>
      <div className="bg-gradient-to-br from-slate-800/60 via-slate-800/50 to-slate-900/60 backdrop-blur-xl rounded-2xl p-6 border-2 border-slate-600/50 hover:border-purple-500/50 shadow-sm hover:shadow-md hover:shadow-purple-500/10 transition-all duration-300">
        <div className="text-xs text-slate-300 mb-2 font-medium">交易次数</div>
        <div className="text-3xl font-bold text-slate-100 drop-shadow-lg">{stats.total_trades}</div>
      </div>
      <div className="bg-gradient-to-br from-slate-800/60 via-slate-800/50 to-slate-900/60 backdrop-blur-xl rounded-2xl p-6 border-2 border-slate-600/50 hover:border-purple-500/50 shadow-sm hover:shadow-md hover:shadow-purple-500/10 transition-all duration-300">
        <div className="text-xs text-slate-300 mb-2 font-medium">买入次数</div>
        <div className="text-3xl font-bold text-red-300 drop-shadow-lg">{stats.buy_count}</div>
      </div>
      <div className="bg-gradient-to-br from-slate-800/60 via-slate-800/50 to-slate-900/60 backdrop-blur-xl rounded-2xl p-6 border-2 border-slate-600/50 hover:border-purple-500/50 shadow-sm hover:shadow-md hover:shadow-purple-500/10 transition-all duration-300">
        <div className="text-xs text-slate-300 mb-2 font-medium">卖出次数</div>
        <div className="text-3xl font-bold text-green-300 drop-shadow-lg">{stats.sell_count}</div>
      </div>
      <div className="bg-gradient-to-br from-slate-800/60 via-slate-800/50 to-slate-900/60 backdrop-blur-xl rounded-2xl p-6 border-2 border-slate-600/50 hover:border-purple-500/50 shadow-sm hover:shadow-md hover:shadow-purple-500/10 transition-all duration-300">
        <div className="text-xs text-slate-300 mb-2 font-medium">价格变化</div>
        <div className={`text-3xl font-bold drop-shadow-lg ${getValueColor(stats.price_change_pct)}`}>
          {stats.price_change_pct.toFixed(2)}%
        </div>
      </div>
      {stats.win_rate !== undefined && (
        <div className="bg-gradient-to-br from-slate-800/60 via-slate-800/50 to-slate-900/60 backdrop-blur-xl rounded-2xl p-6 border-2 border-purple-500/60 shadow-sm hover:shadow-md hover:shadow-purple-500/10 transition-all duration-300">
          <div className="text-xs text-slate-300 mb-2 font-medium">胜率</div>
          <div className="text-3xl font-bold text-purple-300 drop-shadow-lg">
            {stats.win_rate.toFixed(2)}%
          </div>
        </div>
      )}
      {stats.profit_loss_ratio !== undefined && (
        <div className="bg-gradient-to-br from-slate-800/60 via-slate-800/50 to-slate-900/60 backdrop-blur-xl rounded-2xl p-6 border-2 border-slate-600/50 hover:border-purple-500/50 shadow-sm hover:shadow-md hover:shadow-purple-500/10 transition-all duration-300">
          <div className="text-xs text-slate-300 mb-2 font-medium">盈亏比</div>
          <div className="text-3xl font-bold text-slate-100 drop-shadow-lg">
            {stats.profit_loss_ratio === 999.999 ? '∞' : stats.profit_loss_ratio.toFixed(2)}
          </div>
        </div>
      )}
      {stats.sharpe_ratio !== undefined && (
        <div className="bg-gradient-to-br from-slate-800/60 via-slate-800/50 to-slate-900/60 backdrop-blur-xl rounded-2xl p-6 border-2 border-slate-600/50 hover:border-purple-500/50 shadow-sm hover:shadow-md hover:shadow-purple-500/10 transition-all duration-300">
          <div className="text-xs text-slate-300 mb-2 font-medium">夏普比率</div>
          <div className="text-3xl font-bold text-slate-100 drop-shadow-lg">
            {stats.sharpe_ratio.toFixed(3)}
          </div>
        </div>
      )}
      {stats.total_trade_pairs !== undefined && stats.total_trade_pairs > 0 && (
        <>
          <div className="bg-gradient-to-br from-slate-800/60 via-slate-800/50 to-slate-900/60 backdrop-blur-xl rounded-2xl p-6 border-2 border-slate-600/50 hover:border-purple-500/50 shadow-sm hover:shadow-md hover:shadow-purple-500/10 transition-all duration-300">
            <div className="text-xs text-slate-300 mb-2 font-medium">盈利交易</div>
            <div className="text-3xl font-bold text-red-300 drop-shadow-lg">
              {stats.winning_trades || 0}
            </div>
          </div>
          <div className="bg-gradient-to-br from-slate-800/60 via-slate-800/50 to-slate-900/60 backdrop-blur-xl rounded-2xl p-6 border-2 border-slate-600/50 hover:border-purple-500/50 shadow-sm hover:shadow-md hover:shadow-purple-500/10 transition-all duration-300">
            <div className="text-xs text-slate-300 mb-2 font-medium">亏损交易</div>
            <div className="text-3xl font-bold text-green-300 drop-shadow-lg">
              {stats.losing_trades || 0}
            </div>
          </div>
          {stats.avg_holding_period !== undefined && (
            <div className="bg-gradient-to-br from-slate-800/60 via-slate-800/50 to-slate-900/60 backdrop-blur-xl rounded-2xl p-6 border-2 border-slate-600/50 hover:border-purple-500/50 shadow-sm hover:shadow-md hover:shadow-purple-500/10 transition-all duration-300">
              <div className="text-xs text-slate-300 mb-2 font-medium">平均持仓周期</div>
              <div className="text-3xl font-bold text-slate-100 drop-shadow-lg">
                {stats.avg_holding_period.toFixed(1)}
              </div>
            </div>
          )}
        </>
      )}
    </div>
    );
  }, [stats]);

  // 重型区块：图表
  const ChartSection = useMemo(() => {
    if (!stockData || !backtest) return null;
    return (
      <DataChart
        data={stockData}
        signals={backtest.signals}
        trades={backtest.trades}
        chartType={chartType}
      />
    );
  }, [stockData, backtest, chartType]);

  // 重型区块：交易表格
  const TradesTable = useMemo(() => {
    if (!backtest) return null;
    return (
    <div className="bg-gradient-to-br from-slate-800/40 via-slate-800/30 to-slate-900/40 backdrop-blur-xl rounded-3xl p-8 border border-slate-700/30 shadow-2xl shadow-slate-900/50">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-semibold text-white">交易日志</h2>
        <button
          type="button"
          title="导出交易JSON"
          className="text-slate-300 hover:text-white transition-colors p-2 border border-slate-600/60 rounded-lg hover:border-slate-500"
          onClick={() => {
            try {
              const dataStr = JSON.stringify(backtest.trades, null, 2);
              const blob = new Blob([dataStr], { type: 'application/json' });
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = `${backtest.run_id || 'backtest'}-trades.json`;
              document.body.appendChild(a);
              a.click();
              a.remove();
              URL.revokeObjectURL(url);
            } catch (e) {
              // ignore
            }
          }}
        >
          <FontAwesomeIcon icon={faDownload} className="w-5 h-5" />
        </button>
      </div>
      <div className="max-h-96 overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-slate-700">
            <tr>
              <th className="text-left p-2 text-slate-300">时间</th>
              <th className="text-left p-2 text-slate-300">索引</th>
              <th className="text-left p-2 text-slate-300">类型</th>
              <th className="text-left p-2 text-slate-300">价格 ($)</th>
              <th className="text-left p-2 text-slate-300">数量</th>
              <th className="text-left p-2 text-slate-300">现金 ($)</th>
              <th className="text-left p-2 text-slate-300">持仓</th>
              <th className="text-left p-2 text-slate-300">结果</th>
            </tr>
          </thead>
          <tbody>
            {backtest.trades.map((trade, idx) => {
              const tradeResult = trade.trade_type === 'sell' ? tradePairs.get(trade.data_index) : null;
              const timeStr = new Date(trade.timestamp).toLocaleTimeString('zh-CN');
              return (
                <tr key={idx} className="border-t border-slate-700">
                  <td className="p-2 text-slate-400">{timeStr}</td>
                  <td className="p-2 text-white">{trade.data_index}</td>
                  <td className={`p-2 font-medium ${
                    trade.trade_type === 'buy' ? 'text-red-400' : 'text-green-400'
                  }`}>
                    {trade.trade_type === 'buy' ? '买入' : '卖出'}
                  </td>
                  <td className="p-2 text-white">{trade.price.toFixed(3)}</td>
                  <td className="p-2 text-white">{trade.quantity.toFixed(3)}</td>
                  <td className="p-2 text-white">{formatCurrency(trade.cash_after)}</td>
                  <td className="p-2 text-white">{trade.position_after.toFixed(3)}</td>
                  <td className="p-2">
                    {tradeResult && (
                      <span
                        className={`px-2 py-1 rounded cursor-pointer transition-all ${
                          tradeResult === 'win'
                            ? 'bg-green-500/20 text-green-400 hover:bg-green-500/30'
                            : 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
                        }`}
                        onClick={() => {
                          if (tradeResult === 'loss') {
                            setSelectedTradeSummary(trade.summary || null);
                          }
                        }}
                      >
                        {tradeResult === 'win' ? 'WIN' : 'LOSS'}
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
    );
  }, [backtest, tradePairs]);

  if (isLoading) {
    return <div className="text-white text-center py-8">加载中...</div>;
  }

  if (!backtest) {
    return <div className="text-white text-center py-8">回测记录不存在</div>;
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <button
            onClick={() => navigate('/backtests')}
            className="text-slate-400 hover:text-white mb-3 flex items-center gap-2 transition-colors"
          >
            <FontAwesomeIcon icon={faArrowLeft} className="w-4 h-4" />
            返回列表
          </button>
          <h1 className="text-4xl font-bold text-white mb-2">回测详情</h1>
          <div className="text-slate-500 font-mono text-sm">{runId}</div>
        </div>
        <div className="flex gap-3">
          <button
            className="px-6 py-3 rounded-2xl bg-gradient-to-r from-purple-500 to-violet-600 text-white shadow-sm shadow-purple-500/15 flex items-center gap-3 font-semibold transition-all duration-300 border border-purple-400/40"
          >
            <FontAwesomeIcon icon={faChartLine} className="w-5 h-5" />
            折线图
          </button>
        </div>
      </div>

      {/* 统计指标 */}
      {StatsSection}

      {/* 图表 */}
      {ChartSection}

      {/* 配置信息 */}
      <div className="bg-gradient-to-br from-slate-800/40 via-slate-800/30 to-slate-900/40 backdrop-blur-xl rounded-3xl p-8 border border-slate-700/30 shadow-2xl shadow-slate-900/50">
        <h2 className="text-2xl font-semibold text-white mb-6">回测配置</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
          <div>
            <div className="text-slate-400">策略名称</div>
            <div className="text-white">{backtest.config.strategy_name}</div>
          </div>
          <div>
            <div className="text-slate-400">数据文件</div>
            <div className="text-white font-mono">{backtest.config.data_file_id}</div>
          </div>
          <div>
            <div className="text-slate-400">初始资金 ($)</div>
            <div className="text-white">{formatCurrency(backtest.config.initial_cash)}</div>
          </div>
          <div>
            <div className="text-slate-400">手续费率</div>
            <div className="text-white">{(backtest.config.commission_rate * 100).toFixed(2)}%</div>
          </div>
          <div>
            <div className="text-slate-400">开始时间</div>
            <div className="text-white">{new Date(backtest.start_time).toLocaleString('zh-CN')}</div>
          </div>
          <div>
            <div className="text-slate-400">结束时间</div>
            <div className="text-white">{new Date(backtest.end_time).toLocaleString('zh-CN')}</div>
          </div>
        </div>
        {Object.keys(backtest.config.strategy_params).length > 0 && (
          <div className="mt-4">
            <div className="flex items-center gap-3">
              <div className="text-slate-400">策略参数（{Object.keys(backtest.config.strategy_params).length}）</div>
              <button
                type="button"
                onClick={() => setShowParams((v) => !v)}
                className="text-slate-300 hover:text-white text-sm px-3 py-1 rounded-lg border border-slate-600/60 hover:border-slate-500 transition-colors"
              >
                {showParams ? '收起' : '展开'}
              </button>
            </div>
            {showParams && (
              <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
                {Object.entries(backtest.config.strategy_params).map(([key, value]) => (
                  <div key={key} className="rounded-xl border border-slate-700/60 bg-slate-800/40 p-3">
                    <div className="text-slate-400 text-xs mb-1 break-all">{key}</div>
                    <div className="text-white break-words">{String(value)}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* AI分析配置和按钮 */}
      <div className="bg-gradient-to-br from-slate-800/40 via-slate-800/30 to-slate-900/40 backdrop-blur-xl rounded-3xl p-8 border border-slate-700/30 shadow-2xl shadow-slate-900/50">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-semibold text-white">AI分析</h2>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowAIAnalysis(!showAIAnalysis)}
              className="text-slate-400 hover:text-white transition-colors p-2"
              title={showAIAnalysis ? '隐藏配置' : '显示配置'}
            >
              <FontAwesomeIcon icon={faCog} className="w-5 h-5" />
            </button>
            <button
              onClick={handleAnalyze}
              disabled={analyzing}
              className="px-6 py-3 rounded-2xl bg-gradient-to-r from-purple-500 to-violet-600 text-white shadow-sm shadow-purple-500/15 flex items-center gap-3 font-semibold transition-all duration-300 border border-purple-400/40 hover:shadow-md hover:shadow-purple-500/30 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <FontAwesomeIcon icon={faRobot} className="w-5 h-5" />
              {analyzing ? '分析中...' : '开始AI分析'}
            </button>
          </div>
        </div>
        
        {/* 已存在的AI整体总结 */}
        {!analysisProgress && (() => {
          const end = (backtest.logs as any[]).find((e) => e.type === 'backtest_end');
          const summary = end?.overall_summary;
          if (!summary) return null;
          return (
            <div className="mb-4 whitespace-pre-wrap leading-relaxed text-slate-200">
              {summary}
            </div>
          );
        })()}

        {/* 进度条 */}
        {analysisProgress && (
          <div className="mb-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-slate-300">{analysisProgress.message}</span>
              <span className="text-sm text-slate-400">
                {analysisProgress.total > 0 && `${analysisProgress.current}/${analysisProgress.total}`}
              </span>
            </div>
            <div className="w-full bg-slate-700 rounded-full h-2.5">
              <div
                className={`h-2.5 rounded-full transition-all duration-300 ${
                  analysisProgress.status === 'error'
                    ? 'bg-red-500'
                    : analysisProgress.status === 'completed'
                    ? 'bg-green-500'
                    : analysisProgress.status === 'cancelled'
                    ? 'bg-slate-500'
                    : 'bg-blue-500'
                }`}
                style={{ width: `${analysisProgress.progress}%` }}
              />
            </div>
            {analysisProgress.status === 'running' && (
              <div className="mt-3 flex justify-end">
                <button
                  onClick={async () => {
                    if (!runId) return;
                    try {
                      await backtestApi.stopAnalyze(runId);
                      // 本地立即标记为已停止，避免后端取消处理的延时
                      setAnalysisProgress((prev) => prev ? {
                        ...prev,
                        status: 'cancelled',
                        message: '分析任务已停止'
                      } : {
                        status: 'cancelled', progress: 0, message: '分析任务已停止', total: 0, current: 0
                      });
                      if (progressIntervalRef.current) {
                        clearInterval(progressIntervalRef.current);
                        progressIntervalRef.current = null;
                      }
                      setAnalyzing(false);
                    } catch (e: any) {
                      alert(e?.response?.data?.detail || '停止任务失败');
                    }
                  }}
                  className="px-4 py-2 rounded-lg bg-red-600/80 text-white border border-red-500/60 hover:bg-red-600 transition-colors text-sm"
                >
                  停止分析
                </button>
              </div>
            )}
          </div>
        )}
        {showAIAnalysis && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm text-slate-300 mb-2">API Key</label>
                <div className="relative">
                  <input
                    type={showApiKey ? 'text' : 'password'}
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="请输入API Key"
                    className="w-full px-4 py-2 rounded-lg bg-slate-700/50 border border-slate-600 text-white placeholder-slate-400 focus:outline-none focus:border-blue-500"
                  />
                  <button
                    type="button"
                    onClick={() => setShowApiKey(!showApiKey)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
                  >
                    <FontAwesomeIcon icon={showApiKey ? faEyeSlash : faEye} />
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-sm text-slate-300 mb-2">API URL</label>
                <input
                  type="text"
                  value={apiUrl}
                  onChange={(e) => setApiUrl(e.target.value)}
                  placeholder="https://api.openai.com/v1/chat/completions"
                  className="w-full px-4 py-2 rounded-lg bg-slate-700/50 border border-slate-600 text-white placeholder-slate-400 focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-300 mb-2">Model Name</label>
                <input
                  type="text"
                  value={modelName}
                  onChange={(e) => setModelName(e.target.value)}
                  placeholder="gpt-4"
                  className="w-full px-4 py-2 rounded-lg bg-slate-700/50 border border-slate-600 text-white placeholder-slate-400 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 交易日志 */}
      {TradesTable}

      {/* AI总结Modal */}
      {selectedTradeSummary !== null && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setSelectedTradeSummary(null)}>
          <div
            className="bg-gradient-to-br from-slate-800 via-slate-800 to-slate-900 rounded-3xl p-8 border border-slate-700 max-w-2xl w-full mx-4 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-2xl font-semibold text-white">AI交易分析</h3>
              <button
                onClick={() => setSelectedTradeSummary(null)}
                className="text-slate-400 hover:text-white transition-colors"
              >
                ✕
              </button>
            </div>
            <div className="text-slate-300 whitespace-pre-wrap leading-relaxed">
              {selectedTradeSummary || '请先点击`AI分析`按钮进行回测结果的分析'}
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

