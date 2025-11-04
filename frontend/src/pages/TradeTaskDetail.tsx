import { useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faArrowLeft, faPause, faPlay, faStop, faTrash, faRotateRight } from '@fortawesome/free-solid-svg-icons';
import { tradeApi } from '../services/api';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

export default function TradeTaskDetail() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['tradeTask', taskId],
    queryFn: () => tradeApi.get(taskId!),
    enabled: !!taskId,
    refetchInterval: 5000,
  });

  const pauseMutation = useMutation({
    mutationFn: async () => {
      if (!taskId) throw new Error('taskId is required');
      return tradeApi.pause(taskId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tradeTask', taskId] });
      queryClient.invalidateQueries({ queryKey: ['tradeList'] });
      refetch();
    },
    onError: (error: any) => {
      console.error('暂停任务失败:', error);
      alert(error.response?.data?.detail || '暂停任务失败');
    },
  });

  const resumeMutation = useMutation({
    mutationFn: async () => {
      if (!taskId) throw new Error('taskId is required');
      return tradeApi.resume(taskId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tradeTask', taskId] });
      queryClient.invalidateQueries({ queryKey: ['tradeList'] });
      refetch();
    },
    onError: (error: any) => {
      console.error('恢复任务失败:', error);
      alert(error.response?.data?.detail || '恢复任务失败');
    },
  });

  const stopMutation = useMutation({
    mutationFn: async () => {
      if (!taskId) throw new Error('taskId is required');
      return tradeApi.stop(taskId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tradeTask', taskId] });
      queryClient.invalidateQueries({ queryKey: ['tradeList'] });
      refetch();
    },
    onError: (error: any) => {
      console.error('停止任务失败:', error);
      alert(error.response?.data?.detail || '停止任务失败');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      if (!taskId) throw new Error('taskId is required');
      return tradeApi.delete(taskId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tradeList'] });
      setShowDeleteConfirm(false);
      navigate('/trades');
    },
    onError: (error: any) => {
      console.error('删除任务失败:', error);
      alert(error.response?.data?.detail || '删除任务失败');
      setShowDeleteConfirm(false);
    },
  });

  // 准备图表数据，包含价格和买卖点
  const chartData = useMemo(() => {
    console.log('TradeTaskDetail chartData - data:', data);
    console.log('TradeTaskDetail chartData - latest_points:', data?.latest_points);
    console.log('TradeTaskDetail chartData - latest_points length:', data?.latest_points?.length);
    
    if (!data?.latest_points || data.latest_points.length === 0) {
      console.log('No latest_points data:', data);
      return { prices: [], buyPoints: [], sellPoints: [] };
    }
    
    const prices = data.latest_points.map((p, idx) => {
      let dateStr = idx.toString();
      if (p.timestamp) {
        try {
          // 支持多种时间格式
          let date: Date;
          if (p.timestamp.includes('T') || p.timestamp.includes('+') || p.timestamp.includes('Z')) {
            // ISO格式
            date = new Date(p.timestamp.replace('Z', '+00:00'));
          } else if (p.timestamp.includes(' ')) {
            // "YYYY-MM-DD HH:MM:SS" 格式
            date = new Date(p.timestamp.replace(' ', 'T'));
          } else {
            date = new Date(p.timestamp);
          }
          
          if (!isNaN(date.getTime())) {
            dateStr = date.toLocaleString('zh-CN', {
              month: 'short',
              day: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            });
          } else {
            dateStr = p.timestamp;
          }
        } catch (e) {
          console.warn('Failed to parse timestamp:', p.timestamp, e);
          dateStr = p.timestamp || idx.toString();
        }
      }
      
      return {
        index: idx,
        date: dateStr,
        timestamp: p.timestamp || '',
        price: typeof p.price === 'number' ? p.price : (p.price !== null && p.price !== undefined ? parseFloat(p.price) : null),
      };
    }).filter(d => d.price !== null && !isNaN(d.price as number));

    // 提取买卖点（使用时间戳匹配）
    const buyPoints: Array<{ timestamp: string; price: number }> = [];
    const sellPoints: Array<{ timestamp: string; price: number }> = [];

    if (data.trade_logs) {
      data.trade_logs.forEach((log: any) => {
        if (log.type === 'trade' && log.price) {
          if (log.trade_type === 'buy') {
            buyPoints.push({
              timestamp: log.timestamp,
              price: log.price,
            });
          } else if (log.trade_type === 'sell') {
            sellPoints.push({
              timestamp: log.timestamp,
              price: log.price,
            });
          }
        }
      });
    }

    return { prices, buyPoints, sellPoints };
  }, [data]);

  // 合并图表数据，添加买卖点标记
  const mergedChartData = useMemo(() => {
    const { prices, buyPoints, sellPoints } = chartData;
    return prices.map((point) => {
      // 使用时间戳匹配买卖点
      const buyPoint = buyPoints.find(bp => bp.timestamp === point.timestamp);
      const sellPoint = sellPoints.find(sp => sp.timestamp === point.timestamp);
      return {
        ...point,
        buyMarker: buyPoint ? buyPoint.price : null,
        sellMarker: sellPoint ? sellPoint.price : null,
      };
    });
  }, [chartData]);

  const yDomain = useMemo(() => {
    const values = chartData.prices.map(d => d.price).filter((v: number | null) => typeof v === 'number') as number[];
    if (!values.length) return undefined;
    const min = Math.min(...values);
    const max = Math.max(...values);
    if (!isFinite(min) || !isFinite(max)) return undefined;
    const pad = (max - min) * 0.1 || (max || 1) * 0.1;
    return [min - pad, max + pad];
  }, [chartData]);

  const cfg = data?.config || {};
  const durationText = useMemo(() => {
    const d = cfg.duration || {};
    if (d.mode === 'permanent') return '永久';
    const parts: string[] = [];
    if (d.days) parts.push(`${d.days}天`);
    if (d.hours) parts.push(`${d.hours}时`);
    if (d.minutes) parts.push(`${d.minutes}分`);
    if (d.seconds) parts.push(`${d.seconds}秒`);
    return parts.length ? parts.join('') : '未设置';
  }, [cfg]);

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0]?.payload;
      const timestamp = data?.timestamp || label;
      return (
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-3 shadow-xl">
          <p className="text-slate-300 text-sm mb-2">时间: {formatTimestamp(timestamp)}</p>
          {payload.map((entry: any, index: number) => (
            <p key={index} className="text-white text-sm" style={{ color: entry.color }}>
              {entry.name}: {entry.value?.toFixed(3) || 'N/A'}
            </p>
          ))}
          {data?.buyMarker && (
            <p className="text-red-400 text-sm mt-1">● 买入点: {data.buyMarker.toFixed(3)}</p>
          )}
          {data?.sellMarker && (
            <p className="text-green-400 text-sm mt-1">● 卖出点: {data.sellMarker.toFixed(3)}</p>
          )}
        </div>
      );
    }
    return null;
  };

  // 展开的日志项索引
  const [expandedLogs, setExpandedLogs] = useState<Set<number>>(new Set());

  // 交易日志（后端只返回买卖交易记录）
  const tradeLogs = useMemo(() => {
    if (!data?.trade_logs) return [];
    // 后端现在只返回买卖交易记录，不需要过滤
    return data.trade_logs;
  }, [data]);

  // 切换日志项展开状态
  const toggleLogExpand = (index: number) => {
    setExpandedLogs((prev: Set<number>) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  const getLogTypeColor = (type: string) => {
    if (type === 'trade') {
      return 'text-blue-400';
    } else if (type === 'strategy_signal') {
      return 'text-purple-400';
    } else if (type === 'error') {
      return 'text-red-400';
    }
    return 'text-slate-400';
  };

  const getSignalColor = (signal: string) => {
    if (signal === 'buy') return 'text-green-400';
    if (signal === 'sell') return 'text-red-400';
    return 'text-slate-400';
  };

  // 格式化时间戳，去掉毫秒，只保留到秒
  const formatTimestamp = (timestamp: string): string => {
    if (!timestamp) return '';
    try {
      // 处理ISO格式时间戳（可能包含毫秒）
      let date: Date;
      if (timestamp.includes('T') || timestamp.includes('+') || timestamp.includes('Z')) {
        date = new Date(timestamp.replace('Z', '+00:00'));
      } else if (timestamp.includes(' ')) {
        date = new Date(timestamp.replace(' ', 'T'));
      } else {
        date = new Date(timestamp);
      }
      
      if (isNaN(date.getTime())) {
        // 如果解析失败，尝试直接去掉毫秒部分
        return timestamp.replace(/\.\d{3}/, '').replace(/\.\d+/, '');
      }
      
      // 格式化为 YYYY-MM-DD HH:MM:SS
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      const hours = String(date.getHours()).padStart(2, '0');
      const minutes = String(date.getMinutes()).padStart(2, '0');
      const seconds = String(date.getSeconds()).padStart(2, '0');
      
      return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
    } catch (e) {
      // 如果解析失败，尝试直接去掉毫秒部分
      return timestamp.replace(/\.\d{3}/, '').replace(/\.\d+/, '');
    }
  };

  // 根据交易模式获取主题颜色
  const getModeColors = (mode: 'paper' | 'live') => {
    if (mode === 'paper') {
      return {
        bgGradient: 'from-purple-500 to-violet-600',
        hoverGradient: 'hover:from-purple-600 hover:to-violet-700',
        shadow: 'shadow-purple-500/15',
        border: 'border-purple-400/40',
        hoverBorder: 'hover:border-purple-500/50',
        hoverShadow: 'hover:shadow-purple-500/10',
        hoverText: 'group-hover:text-purple-300',
        bgActive: 'bg-purple-500/80',
      };
    } else {
      return {
        bgGradient: 'from-orange-500 to-amber-600',
        hoverGradient: 'hover:from-orange-600 hover:to-amber-700',
        shadow: 'shadow-orange-500/15',
        border: 'border-orange-400/40',
        hoverBorder: 'hover:border-orange-500/50',
        hoverShadow: 'hover:shadow-orange-500/10',
        hoverText: 'group-hover:text-orange-300',
        bgActive: 'bg-orange-500/80',
      };
    }
  };

  if (isLoading || !data) {
    return <div className="text-slate-300">加载中...</div>;
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/trades')}
            className="px-4 py-2 rounded-xl bg-slate-700/60 text-white hover:bg-slate-700/80 flex items-center justify-center"
            title="返回"
          >
            <FontAwesomeIcon icon={faArrowLeft} className="w-4 h-4" />
          </button>
          <div>
            <h1 className="text-3xl font-bold text-white">交易任务详情</h1>
            <p className="text-slate-400 text-sm mt-1">任务ID：{cfg.task_id}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowDeleteConfirm(true)}
            disabled={deleteMutation.isPending}
            className="px-4 py-2 rounded-xl bg-red-600/60 border border-red-400/40 text-white hover:bg-red-600/80 flex items-center justify-center disabled:opacity-50"
            title="删除任务"
          >
            <FontAwesomeIcon icon={faTrash} className="w-4 h-4" />
          </button>
          {cfg.status === 'running' && (
            <button
              onClick={() => pauseMutation.mutate()}
              disabled={pauseMutation.isPending}
              className="px-4 py-2 rounded-xl bg-yellow-600/60 border border-yellow-400/40 text-white hover:bg-yellow-600/80 flex items-center justify-center disabled:opacity-50"
              title={pauseMutation.isPending ? '暂停中...' : '暂停'}
            >
              <FontAwesomeIcon icon={faPause} className="w-4 h-4" />
            </button>
          )}
          {cfg.status === 'paused' && (
            <button
              onClick={() => resumeMutation.mutate()}
              disabled={resumeMutation.isPending}
              className={`px-4 py-2 rounded-xl ${cfg.mode === 'paper' ? 'bg-violet-600/60 border-violet-400/40 hover:bg-violet-600/80' : 'bg-amber-600/60 border-amber-400/40 hover:bg-amber-600/80'} border text-white flex items-center justify-center transition-all disabled:opacity-50`}
              title={resumeMutation.isPending ? '恢复中...' : '恢复'}
            >
              <FontAwesomeIcon icon={faPlay} className="w-4 h-4" />
            </button>
          )}
          {cfg.status !== 'stopped' && cfg.status !== 'completed' && !cfg.status?.startsWith('error') && (
            <button
              onClick={() => stopMutation.mutate()}
              disabled={stopMutation.isPending}
              className="px-4 py-2 rounded-xl bg-red-600/60 border border-red-400/40 text-white hover:bg-red-600/80 flex items-center justify-center disabled:opacity-50"
              title={stopMutation.isPending ? '停止中...' : '停止'}
            >
              <FontAwesomeIcon icon={faStop} className="w-4 h-4" />
            </button>
          )}
          <button
            onClick={() => refetch()}
            className="px-4 py-2 rounded-xl bg-slate-700/60 border border-slate-600/50 text-white hover:bg-slate-700/80 flex items-center justify-center"
            title="刷新"
          >
            <FontAwesomeIcon icon={faRotateRight} className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* 任务配置 */}
      <div className="bg-gradient-to-br from-slate-800/40 via-slate-800/30 to-slate-900/40 backdrop-blur-xl rounded-3xl p-8 border border-slate-700/30">
        <h2 className="text-xl font-semibold text-white mb-4">任务配置</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div className="text-slate-300">
            标的：<span className="text-white font-mono">{cfg.symbol}</span>
          </div>
          <div className="text-slate-300">
            环境：<span className="text-white">{cfg.mode}</span>
          </div>
          <div className="text-slate-300">
            策略：<span className="text-white">{cfg.strategy_name}</span>
          </div>
          <div className="text-slate-300">
            状态：<span className="text-white">{cfg.status || 'running'}</span>
          </div>
          <div className="text-slate-300">
            价格间隔：<span className="text-white">{cfg.price_interval?.value} {cfg.price_interval?.unit}</span>
          </div>
          <div className="text-slate-300">
            信号间隔：<span className="text-white">{cfg.signal_interval?.value} {cfg.signal_interval?.unit}</span>
          </div>
          <div className="text-slate-300">
            缓存大小：<span className="text-white">{cfg.max_cache_size || 1000}</span>
          </div>
          <div className="text-slate-300">
            盘段：<span className="text-white">{(cfg.sessions || []).join('、') || '未限制'}</span>
          </div>
          <div className="text-slate-300">
            开始时间：<span className="text-white">{cfg.start_time ? formatTimestamp(cfg.start_time) : 'N/A'}</span>
          </div>
          <div className="text-slate-300">
            当前交易时段：<span className="text-white">{data.current_session || '未知'}</span>
          </div>
          <div className="text-slate-300">
            持续时长：<span className="text-white">{durationText}</span>
          </div>
        </div>
      </div>

      {/* 实时指标 */}
      {data.metrics && (
        <div className="bg-gradient-to-br from-slate-800/40 via-slate-800/30 to-slate-900/40 backdrop-blur-xl rounded-3xl p-8 border border-slate-700/30">
          <h2 className="text-xl font-semibold text-white mb-6">实时交易指标</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
            {/* 交易次数 */}
            <div className="bg-slate-800/60 rounded-xl p-4 border border-slate-700/50">
              <div className="text-slate-400 text-xs mb-1">交易次数</div>
              <div className="text-2xl font-bold text-white">{data.metrics.total_trades}</div>
            </div>
            
            {/* 买入次数 */}
            <div className="bg-red-500/10 rounded-xl p-4 border border-red-500/30">
              <div className="text-slate-400 text-xs mb-1">买入次数</div>
              <div className="text-2xl font-bold text-red-400">{data.metrics.buy_count}</div>
            </div>
            
            {/* 卖出次数 */}
            <div className="bg-green-500/10 rounded-xl p-4 border border-green-500/30">
              <div className="text-slate-400 text-xs mb-1">卖出次数</div>
              <div className="text-2xl font-bold text-green-400">{data.metrics.sell_count}</div>
            </div>
            
            {/* 胜率 */}
            <div className="bg-blue-500/10 rounded-xl p-4 border border-blue-500/30">
              <div className="text-slate-400 text-xs mb-1">胜率</div>
              <div className="text-2xl font-bold text-blue-400">{data.metrics.win_rate.toFixed(2)}%</div>
            </div>
            
            {/* 总收益 */}
            <div className={`rounded-xl p-4 border ${
              data.metrics.total_profit >= 0 
                ? 'bg-green-500/10 border-green-500/30' 
                : 'bg-red-500/10 border-red-500/30'
            }`}>
              <div className="text-slate-400 text-xs mb-1">总收益</div>
              <div className={`text-2xl font-bold ${
                data.metrics.total_profit >= 0 ? 'text-green-400' : 'text-red-400'
              }`}>
                {data.metrics.total_profit >= 0 ? '+' : ''}{data.metrics.total_profit.toFixed(2)}
              </div>
            </div>
            
            {/* 总收益率 */}
            <div className={`rounded-xl p-4 border ${
              data.metrics.total_return_rate >= 0 
                ? 'bg-green-500/10 border-green-500/30' 
                : 'bg-red-500/10 border-red-500/30'
            }`}>
              <div className="text-slate-400 text-xs mb-1">总收益率</div>
              <div className={`text-2xl font-bold ${
                data.metrics.total_return_rate >= 0 ? 'text-green-400' : 'text-red-400'
              }`}>
                {data.metrics.total_return_rate >= 0 ? '+' : ''}{data.metrics.total_return_rate.toFixed(2)}%
              </div>
            </div>
            
            {/* 盈亏比 */}
            <div className="bg-purple-500/10 rounded-xl p-4 border border-purple-500/30">
              <div className="text-slate-400 text-xs mb-1">盈亏比</div>
              <div className="text-2xl font-bold text-purple-400">{data.metrics.profit_loss_ratio.toFixed(2)}</div>
            </div>
            
            {/* 夏普比率 */}
            <div className="bg-amber-500/10 rounded-xl p-4 border border-amber-500/30">
              <div className="text-slate-400 text-xs mb-1">夏普比率</div>
              <div className="text-2xl font-bold text-amber-400">{data.metrics.sharpe_ratio.toFixed(4)}</div>
            </div>
            
            {/* 初始资金 */}
            <div className="bg-slate-800/60 rounded-xl p-4 border border-slate-700/50">
              <div className="text-slate-400 text-xs mb-1">初始资金</div>
              <div className="text-xl font-bold text-white">{data.metrics.initial_cash.toFixed(2)}</div>
            </div>
            
            {/* 当前现金 */}
            <div className="bg-slate-800/60 rounded-xl p-4 border border-slate-700/50">
              <div className="text-slate-400 text-xs mb-1">当前现金</div>
              <div className="text-xl font-bold text-white">{data.metrics.current_cash.toFixed(2)}</div>
            </div>
            
            {/* 当前持仓 */}
            <div className="bg-slate-800/60 rounded-xl p-4 border border-slate-700/50">
              <div className="text-slate-400 text-xs mb-1">当前持仓</div>
              <div className="text-xl font-bold text-white">{data.metrics.current_position.toFixed(4)}</div>
            </div>
            
            {/* 当前资产价值 */}
            <div className={`rounded-xl p-4 border ${
              data.metrics.current_asset_value >= data.metrics.initial_cash
                ? 'bg-green-500/10 border-green-500/30' 
                : 'bg-red-500/10 border-red-500/30'
            }`}>
              <div className="text-slate-400 text-xs mb-1">资产价值</div>
              <div className={`text-xl font-bold ${
                data.metrics.current_asset_value >= data.metrics.initial_cash ? 'text-green-400' : 'text-red-400'
              }`}>
                {data.metrics.current_asset_value.toFixed(2)}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 价格图表 */}
      <div className="bg-gradient-to-br from-slate-800/40 via-slate-800/30 to-slate-900/40 backdrop-blur-xl rounded-3xl p-8 border border-slate-700/30">
        <h2 className="text-xl font-semibold text-white mb-6">价格走势（最近{data.count || 0}条数据）</h2>
        {mergedChartData.length === 0 ? (
          <div className="text-center py-12 text-slate-400">
            <p>暂无价格数据</p>
            <p className="text-sm mt-2">等待任务开始采集价格数据...</p>
            <p className="text-xs mt-1 text-slate-500">
              {data?.config?.status === 'running' ? '任务运行中，请稍候...' : 
               data?.config?.status === 'waiting' ? '等待交易时段...' :
               data?.config?.status === 'paused' ? '任务已暂停' : '任务状态：' + (data?.config?.status || 'unknown')}
            </p>
          </div>
        ) : (
        <ResponsiveContainer width="100%" height={480}>
          <LineChart data={mergedChartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.3} />
            <XAxis
              dataKey="date"
              stroke="#94a3b8"
              angle={-45}
              textAnchor="end"
              height={80}
            />
            <YAxis stroke="#94a3b8" domain={yDomain as any} />
            <Tooltip content={<CustomTooltip />} />
            <Line type="monotone" dataKey="price" stroke="#3b82f6" dot={false} name="价格" />
            {/* 买入点 */}
            <Line
              type="monotone"
              dataKey="buyMarker"
              stroke="none"
              dot={{ fill: '#ef4444', r: 6 }}
              name="买入"
              connectNulls={false}
            />
            {/* 卖出点 */}
            <Line
              type="monotone"
              dataKey="sellMarker"
              stroke="none"
              dot={{ fill: '#22c55e', r: 6 }}
              name="卖出"
              connectNulls={false}
            />
            </LineChart>
          </ResponsiveContainer>
        )}
        <div className="flex gap-6 mt-4 text-sm text-slate-400">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-blue-500"></div>
            <span>价格</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-red-500"></div>
            <span>买入点</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-green-500"></div>
            <span>卖出点</span>
          </div>
        </div>
      </div>

      {/* 交易日志 */}
      <div className="bg-gradient-to-br from-slate-800/40 via-slate-800/30 to-slate-900/40 backdrop-blur-xl rounded-3xl p-8 border border-slate-700/30">
        <h2 className="text-xl font-semibold text-white mb-6">交易日志（按时间降序）</h2>
        {tradeLogs.length === 0 ? (
          <div className="text-center py-12 text-slate-400">暂无交易日志</div>
        ) : (
          <div className="space-y-1 max-h-96 overflow-y-auto">
            {tradeLogs.map((log: any, idx: number) => {
              const isExpanded = expandedLogs.has(idx);
              const hasDetails = (log.type === 'trade' && (log.session || log.signal_info)) ||
                                (log.type === 'strategy_signal' && log.strategy_info) ||
                                (log.type === 'error');
              
              return (
                <div
                  key={idx}
                  className={`bg-slate-800/40 rounded border border-slate-700/30 transition-all ${
                    hasDetails ? 'cursor-pointer hover:bg-slate-800/60' : ''
                  }`}
                  onClick={() => hasDetails && toggleLogExpand(idx)}
                >
                  {/* 紧凑的一行显示 */}
                  <div className="px-3 py-2 flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium whitespace-nowrap ${getLogTypeColor(log.type)}`}>
                        {log.type === 'trade' ? '交易' : log.type === 'strategy_signal' ? '策略信号' : '错误'}
                      </span>
                      <span className="text-xs text-slate-400 whitespace-nowrap">{formatTimestamp(log.timestamp)}</span>
                      
                      {/* 必要信息 */}
                      {log.type === 'trade' && (
                        <>
                          <span className={`text-xs font-medium ${getSignalColor(log.trade_type)}`}>
                            {log.trade_type === 'buy' ? '买入' : '卖出'}
                          </span>
                          <span className="text-xs text-slate-300">价格: {log.price?.toFixed(3)}</span>
                        </>
                      )}
                      
                    </div>
                    
                    {/* 展开/收起指示器 */}
                    {hasDetails && (
                      <span className="text-xs text-slate-500 whitespace-nowrap">
                        {isExpanded ? '▼ 收起' : '▶ 展开详情'}
                      </span>
                    )}
                  </div>
                  
                  {/* 展开的详细JSON信息 */}
                  {isExpanded && hasDetails && (
                    <div className="px-3 pb-3 pt-1 border-t border-slate-700/30 mt-1">
                      <pre className="text-xs text-slate-400 bg-slate-900/50 rounded p-3 overflow-x-auto">
                        {JSON.stringify(log, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 删除确认对话框 */}
      {showDeleteConfirm && data && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-gradient-to-br from-slate-800 via-slate-900 to-slate-800 rounded-2xl p-8 border border-slate-700 shadow-2xl max-w-md w-full mx-4">
            <h3 className="text-xl font-bold text-white mb-4">确认删除</h3>
            <p className="text-slate-300 mb-6">
              确定要删除交易任务 <span className="font-mono text-white">{data.task_id}</span> 吗？此操作将删除任务及其所有日志，不可恢复。
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="px-4 py-2 bg-slate-600 hover:bg-slate-700 text-white rounded-lg text-sm font-medium transition-colors"
              >
                取消
              </button>
              <button
                onClick={() => {
                  if (taskId) {
                    deleteMutation.mutate();
                  }
                }}
                disabled={deleteMutation.isPending}
                className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {deleteMutation.isPending ? '删除中...' : '确认删除'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
