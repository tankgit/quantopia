import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faPlus, faSort, faSortUp, faSortDown, faPause, faPlay, faStop, faTrash } from '@fortawesome/free-solid-svg-icons';
import { tradeApi } from '../services/api';
import { useStrategies } from '../services/strategies';
import type { TradeTaskCreateRequest, TradeTaskSummary } from '../types';

type SortField = 'task_id' | 'symbol' | 'strategy_name' | 'status' | 'started_at';
type SortOrder = 'asc' | 'desc' | null;
type FilterTag = 'paper' | 'live' | 'US' | 'HK' | '盘中' | '非盘中';

export default function TradeManagement() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [sortField, setSortField] = useState<SortField>('started_at');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [activeFilters, setActiveFilters] = useState<Set<FilterTag>>(new Set());
  const [formData, setFormData] = useState<TradeTaskCreateRequest>({
    symbol: 'AAPL.US',
    mode: 'paper',
    strategy_name: 'MA_Strategy',
    strategy_params: { short_window: 5, long_window: 20 },
    sessions: ['盘中'],
    duration: { mode: 'permanent' },
    price_interval: { value: 5, unit: 'seconds' },
    signal_interval: { value: 30, unit: 'seconds' },
    max_cache_size: 1000,
    lot_size: 1.0,
    max_pos_ratio: 1.0,
    commission: 5.0,
  });

  const { data: tradeList } = useQuery({
    queryKey: ['tradeList'],
    queryFn: () => tradeApi.list(),
  });

  const { data: strategies } = useStrategies();
  const selectedStrategy = strategies?.find(s => s.name === formData.strategy_name);

  const createMutation = useMutation({
    mutationFn: tradeApi.create,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['tradeList'] });
      setShowCreateForm(false);
      navigate(`/trades/${data.task_id}`);
    },
  });

  const [operatingTaskId, setOperatingTaskId] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [taskToDelete, setTaskToDelete] = useState<string | null>(null);

  // 暂停任务
  const pauseMutation = useMutation({
    mutationFn: (taskId: string) => tradeApi.pause(taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tradeList'] });
      setOperatingTaskId(null);
    },
    onError: (error: any) => {
      alert(error.response?.data?.detail || '暂停任务失败');
      setOperatingTaskId(null);
    },
  });

  // 恢复任务
  const resumeMutation = useMutation({
    mutationFn: (taskId: string) => tradeApi.resume(taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tradeList'] });
      setOperatingTaskId(null);
    },
    onError: (error: any) => {
      alert(error.response?.data?.detail || '恢复任务失败');
      setOperatingTaskId(null);
    },
  });

  // 停止任务
  const stopMutation = useMutation({
    mutationFn: (taskId: string) => tradeApi.stop(taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tradeList'] });
      setOperatingTaskId(null);
    },
    onError: (error: any) => {
      alert(error.response?.data?.detail || '停止任务失败');
      setOperatingTaskId(null);
    },
  });

  // 删除任务
  const deleteMutation = useMutation({
    mutationFn: (taskId: string) => tradeApi.delete(taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tradeList'] });
      setShowDeleteConfirm(false);
      setTaskToDelete(null);
    },
    onError: (error: any) => {
      alert(error.response?.data?.detail || '删除任务失败');
      setShowDeleteConfirm(false);
      setTaskToDelete(null);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate(formData);
  };

  const updateStrategyParam = (key: string, value: number | string) => {
    if (!strategies) return;
    
    const selectedStrategy = strategies.find(s => s.name === formData.strategy_name);
    const paramSchema = selectedStrategy?.params?.[key];
    
    // 根据参数类型正确转换值
    let convertedValue: number | string = value;
    if (paramSchema?.type === 'number') {
      if (typeof value === 'string') {
        // 如果是浮点数类型的参数（如rsi_oversold），使用parseFloat
        // 如果是整数类型的参数（如short_ma），使用parseInt
        const numValue = value.includes('.') ? parseFloat(value) : parseInt(value, 10);
        if (!isNaN(numValue)) {
          convertedValue = numValue;
        } else {
          // 如果转换失败，使用默认值
          convertedValue = paramSchema.default ?? 0;
        }
      }
    }
    
    setFormData({
      ...formData,
      strategy_params: {
        ...formData.strategy_params,
        [key]: convertedValue,
      },
    });
  };

  const getStatusColor = (status: string) => {
    if (status === 'running') return 'text-green-400';
    if (status === 'paused') return 'text-yellow-400';
    if (status === 'stopped' || status === 'completed') return 'text-gray-400';
    if (status?.startsWith('error')) return 'text-red-400';
    return 'text-slate-400';
  };

  // 获取模式相关的颜色类名
  const getModeColors = (mode: 'paper' | 'live') => {
    if (mode === 'paper') {
      return {
        hoverBorder: 'hover:border-purple-500/50',
        hoverShadow: 'hover:shadow-purple-500/10',
        hoverText: 'group-hover:text-purple-300',
      };
    } else {
      return {
        hoverBorder: 'hover:border-orange-500/50',
        hoverShadow: 'hover:shadow-orange-500/10',
        hoverText: 'group-hover:text-orange-300',
      };
    }
  };

  // 处理排序
  const handleSort = (field: SortField) => {
    if (sortField === field) {
      if (sortOrder === 'asc') {
        setSortOrder('desc');
      } else if (sortOrder === 'desc') {
        setSortOrder(null);
        setSortField('started_at');
        setSortOrder('desc');
      }
    } else {
      setSortField(field);
      setSortOrder('desc');
    }
  };

  // 切换筛选tag
  const toggleFilter = (tag: FilterTag) => {
    const newFilters = new Set(activeFilters);
    if (newFilters.has(tag)) {
      newFilters.delete(tag);
    } else {
      newFilters.add(tag);
    }
    setActiveFilters(newFilters);
  };

  // 排序和筛选后的任务列表
  const sortedAndFilteredTasks = useMemo(() => {
    if (!tradeList?.tasks) return [];
    
    // 判断任务是否匹配筛选条件（并集逻辑：只要匹配任何一个筛选条件就显示）
    const matchesFilters = (task: TradeTaskSummary): boolean => {
      if (activeFilters.size === 0) return true;

      // 检查是否匹配任何一个筛选条件
      // 模式筛选
      if (activeFilters.has('paper') && task.mode === 'paper') return true;
      if (activeFilters.has('live') && task.mode === 'live') return true;

      // 地域筛选
      const isUS = task.symbol.toUpperCase().endsWith('.US');
      const isHK = task.symbol.toUpperCase().endsWith('.HK');
      if (activeFilters.has('US') && isUS) return true;
      if (activeFilters.has('HK') && isHK) return true;

      // 时段筛选
      const has盘中 = task.sessions.includes('盘中');
      if (activeFilters.has('盘中') && has盘中) return true;
      if (activeFilters.has('非盘中') && !has盘中) return true;

      // 如果没有匹配任何筛选条件，返回false
      return false;
    };
    
    let tasks = tradeList.tasks.filter(matchesFilters);
    
    if (sortOrder === null || sortField === 'started_at') {
      return tasks.sort((a, b) => 
        new Date(b.started_at).getTime() - new Date(a.started_at).getTime()
      );
    }
    
    return tasks.sort((a, b) => {
      let aValue: any;
      let bValue: any;
      
      if (sortField === 'task_id') {
        aValue = a.task_id;
        bValue = b.task_id;
      } else if (sortField === 'symbol') {
        aValue = a.symbol;
        bValue = b.symbol;
      } else if (sortField === 'strategy_name') {
        aValue = a.strategy_name;
        bValue = b.strategy_name;
      } else if (sortField === 'status') {
        aValue = a.status;
        bValue = b.status;
      } else {
        aValue = new Date(a.started_at).getTime();
        bValue = new Date(b.started_at).getTime();
      }
      
      if (typeof aValue === 'string' && typeof bValue === 'string') {
        return sortOrder === 'asc' 
          ? aValue.localeCompare(bValue)
          : bValue.localeCompare(aValue);
      } else {
        return sortOrder === 'asc' 
          ? (aValue as number) - (bValue as number)
          : (bValue as number) - (aValue as number);
      }
    });
  }, [tradeList, sortField, sortOrder, activeFilters]);

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-white">实时交易管理</h1>
                  <button
            onClick={() => setShowCreateForm(!showCreateForm)}
            className="px-6 py-3 bg-gradient-to-r from-orange-500 to-amber-600 text-white rounded-2xl hover:from-orange-600 hover:to-amber-700 transition-all duration-300 shadow-sm shadow-orange-500/15 flex items-center gap-3 font-semibold hover:scale-105 border border-orange-400/40"
          >
          <FontAwesomeIcon icon={faPlus} className="w-4 h-4" />
          {showCreateForm ? '取消' : '创建交易任务'}
        </button>
      </div>

      {/* 创建表单 */}
      {showCreateForm && (
        <div className="bg-gradient-to-br from-slate-800/40 via-slate-800/30 to-slate-900/40 backdrop-blur-xl rounded-3xl p-8 border border-slate-700/30 shadow-2xl shadow-slate-900/50">
          <h2 className="text-2xl font-bold text-white mb-8">创建实时交易任务</h2>
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="grid grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">股票代码</label>
                <input
                  type="text"
                  value={formData.symbol}
                  onChange={(e) => setFormData({ ...formData, symbol: e.target.value })}
                  placeholder="如 AAPL.US 或 700.HK"
                  className={`w-full px-4 py-3 bg-slate-700/40 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white focus:outline-none focus:ring-2 ${formData.mode === 'paper' ? 'focus:ring-purple-500/50' : 'focus:ring-orange-500/50'}`}
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">交易模式</label>
                <select
                  value={formData.mode}
                  onChange={(e) => setFormData({ ...formData, mode: e.target.value as 'paper' | 'live' })}
                  className={`w-full px-4 py-3 bg-slate-700/40 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white focus:outline-none focus:ring-2 ${formData.mode === 'paper' ? 'focus:ring-purple-500/50' : 'focus:ring-orange-500/50'}`}
                >
                  <option value="paper">模拟盘</option>
                  <option value="live">实盘</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">策略</label>
                <select
                  value={formData.strategy_name}
                  onChange={(e) => {
                    const newStrategyName = e.target.value;
                    const newStrategy = strategies?.find(s => s.name === newStrategyName);
                    // 切换策略时，使用新策略的默认参数初始化
                    const defaultParams: Record<string, any> = {};
                    if (newStrategy && newStrategy.params) {
                      Object.entries(newStrategy.params).forEach(([key, param]: [string, any]) => {
                        // 根据参数类型设置默认值
                        if (param.type === 'number') {
                          defaultParams[key] = param.default ?? 0;
                        } else {
                          defaultParams[key] = param.default ?? '';
                        }
                      });
                    }
                    setFormData({ 
                      ...formData, 
                      strategy_name: newStrategyName,
                      strategy_params: defaultParams
                    });
                  }}
                  className={`w-full px-4 py-3 bg-slate-700/40 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white focus:outline-none focus:ring-2 ${formData.mode === 'paper' ? 'focus:ring-purple-500/50' : 'focus:ring-orange-500/50'}`}
                >
                  {strategies?.map((s) => (
                    <option key={s.name} value={s.name}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">最大缓存数</label>
                <input
                  type="number"
                  value={formData.max_cache_size}
                  onChange={(e) => setFormData({ ...formData, max_cache_size: parseInt(e.target.value) })}
                  min={100}
                  max={10000}
                  className={`w-full px-4 py-3 bg-slate-700/40 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white focus:outline-none focus:ring-2 ${formData.mode === 'paper' ? 'focus:ring-purple-500/50' : 'focus:ring-orange-500/50'}`}
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">最小交易单位 (lot_size)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  value={formData.lot_size ?? 1.0}
                  onChange={(e) => setFormData({ ...formData, lot_size: parseFloat(e.target.value) })}
                  className={`w-full px-4 py-3 bg-slate-700/40 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white focus:outline-none focus:ring-2 ${formData.mode === 'paper' ? 'focus:ring-purple-500/50' : 'focus:ring-orange-500/50'}`}
                  required
                />
                <p className="text-xs text-slate-400 mt-1">每次交易数量必须是此值的倍数</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">最大持仓比率 (max_pos_ratio)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  max="1.0"
                  value={formData.max_pos_ratio ?? 1.0}
                  onChange={(e) => setFormData({ ...formData, max_pos_ratio: parseFloat(e.target.value) })}
                  className={`w-full px-4 py-3 bg-slate-700/40 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white focus:outline-none focus:ring-2 ${formData.mode === 'paper' ? 'focus:ring-purple-500/50' : 'focus:ring-orange-500/50'}`}
                  required
                />
                <p className="text-xs text-slate-400 mt-1">买入时最多使用可用资金的比例 (0-1)</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">手续费（绝对数值，单位：元）</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={formData.commission ?? 5.0}
                  onChange={(e) => setFormData({ ...formData, commission: parseFloat(e.target.value) })}
                  className={`w-full px-4 py-3 bg-slate-700/40 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white focus:outline-none focus:ring-2 ${formData.mode === 'paper' ? 'focus:ring-purple-500/50' : 'focus:ring-orange-500/50'}`}
                  required
                />
                <p className="text-xs text-slate-400 mt-1">每笔交易收取的固定手续费</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">价格采样间隔</label>
                <div className="flex gap-2">
                  <input
                    type="number"
                    value={formData.price_interval.value}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        price_interval: { ...formData.price_interval, value: parseInt(e.target.value) },
                      })
                    }
                    min={1}
                    className={`flex-1 px-4 py-3 bg-slate-700/40 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white focus:outline-none focus:ring-2 ${formData.mode === 'paper' ? 'focus:ring-purple-500/50' : 'focus:ring-orange-500/50'}`}
                    required
                  />
                  <select
                    value={formData.price_interval.unit}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        price_interval: { ...formData.price_interval, unit: e.target.value as 'seconds' | 'minutes' | 'hours' },
                      })
                    }
                    className={`px-4 py-3 bg-slate-700/40 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white focus:outline-none focus:ring-2 ${formData.mode === 'paper' ? 'focus:ring-purple-500/50' : 'focus:ring-orange-500/50'}`}
                  >
                    <option value="seconds">秒</option>
                    <option value="minutes">分钟</option>
                    <option value="hours">小时</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">信号生成间隔</label>
                <div className="flex gap-2">
                  <input
                    type="number"
                    value={formData.signal_interval.value}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        signal_interval: { ...formData.signal_interval, value: parseInt(e.target.value) },
                      })
                    }
                    min={1}
                    className={`flex-1 px-4 py-3 bg-slate-700/40 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white focus:outline-none focus:ring-2 ${formData.mode === 'paper' ? 'focus:ring-purple-500/50' : 'focus:ring-orange-500/50'}`}
                    required
                  />
                  <select
                    value={formData.signal_interval.unit}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        signal_interval: { ...formData.signal_interval, unit: e.target.value as 'seconds' | 'minutes' | 'hours' },
                      })
                    }
                    className={`px-4 py-3 bg-slate-700/40 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white focus:outline-none focus:ring-2 ${formData.mode === 'paper' ? 'focus:ring-purple-500/50' : 'focus:ring-orange-500/50'}`}
                  >
                    <option value="seconds">秒</option>
                    <option value="minutes">分钟</option>
                    <option value="hours">小时</option>
                  </select>
                </div>
              </div>
            </div>

            {/* 策略参数 */}
            {selectedStrategy && Object.keys(selectedStrategy.params || {}).length > 0 && (
              <div className="bg-slate-800/40 rounded-xl p-4 border border-slate-700/30">
                <h3 className="text-lg font-semibold text-white mb-4">策略参数</h3>
                <div className="grid grid-cols-2 gap-4">
                  {Object.entries(selectedStrategy.params).map(([key, param]: [string, any]) => (
                    <div key={key}>
                      <label className="block text-sm font-medium text-slate-300 mb-1">
                        {param.name || key}
                        {param.description && (
                          <span className="text-xs text-slate-500 ml-2">({param.description})</span>
                        )}
                      </label>
                      <input
                        type={param.type === 'number' ? 'number' : 'text'}
                        value={formData.strategy_params[key] ?? param.default ?? ''}
                        onChange={(e) => updateStrategyParam(key, e.target.value)}
                        min={param.min}
                        max={param.max}
                        step={param.default?.toString().includes('.') ? 'any' : '1'}
                        className={`w-full px-4 py-2 bg-slate-700/40 backdrop-blur-sm border border-slate-600/50 rounded-lg text-white focus:outline-none focus:ring-2 ${formData.mode === 'paper' ? 'focus:ring-purple-500/50' : 'focus:ring-orange-500/50'}`}
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 交易时段 */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">交易时段（可多选）</label>
              <div className="flex flex-wrap gap-3">
                {['盘前', '盘中', '盘后', '夜盘'].map((session) => (
                  <label key={session} className="flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={formData.sessions.includes(session)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setFormData({ ...formData, sessions: [...formData.sessions, session] });
                        } else {
                          setFormData({ ...formData, sessions: formData.sessions.filter((s) => s !== session) });
                        }
                      }}
                      className={`mr-2 w-4 h-4 ${formData.mode === 'paper' ? 'text-purple-600 focus:ring-purple-500' : 'text-orange-600 focus:ring-orange-500'} bg-slate-700 border-slate-600 rounded`}
                    />
                    <span className="text-slate-300">{session}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* 运行时长 */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">运行时长</label>
              <div className="flex items-center gap-4">
                <label className="flex items-center cursor-pointer">
                  <input
                    type="radio"
                    checked={formData.duration.mode === 'permanent'}
                    onChange={() => setFormData({ ...formData, duration: { mode: 'permanent' } })}
                    className="mr-2 w-4 h-4 text-orange-600 bg-slate-700 border-slate-600 focus:ring-orange-500"
                  />
                  <span className="text-slate-300">永久运行</span>
                </label>
                <label className="flex items-center cursor-pointer">
                  <input
                    type="radio"
                    checked={formData.duration.mode === 'finite'}
                    onChange={() => setFormData({ ...formData, duration: { mode: 'finite', days: 0, hours: 1, minutes: 0, seconds: 0 } })}
                    className="mr-2 w-4 h-4 text-orange-600 bg-slate-700 border-slate-600 focus:ring-orange-500"
                  />
                  <span className="text-slate-300">有限时长</span>
                </label>
              </div>
              {formData.duration.mode === 'finite' && (
                <div className="flex gap-2 mt-2">
                  <input
                    type="number"
                    placeholder="天"
                    value={formData.duration.days || 0}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        duration: { ...formData.duration, days: parseInt(e.target.value) || 0 },
                      })
                    }
                    min={0}
                    className="w-20 px-3 py-2 bg-slate-700/40 border border-slate-600/50 rounded-lg text-white"
                  />
                  <input
                    type="number"
                    placeholder="小时"
                    value={formData.duration.hours || 0}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        duration: { ...formData.duration, hours: parseInt(e.target.value) || 0 },
                      })
                    }
                    min={0}
                    className="w-20 px-3 py-2 bg-slate-700/40 border border-slate-600/50 rounded-lg text-white"
                  />
                  <input
                    type="number"
                    placeholder="分钟"
                    value={formData.duration.minutes || 0}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        duration: { ...formData.duration, minutes: parseInt(e.target.value) || 0 },
                      })
                    }
                    min={0}
                    className="w-20 px-3 py-2 bg-slate-700/40 border border-slate-600/50 rounded-lg text-white"
                  />
                </div>
              )}
            </div>

            <div className="flex justify-end gap-4">
              <button
                type="button"
                onClick={() => setShowCreateForm(false)}
                className="px-6 py-3 bg-slate-700/60 text-white rounded-xl hover:bg-slate-700/80 transition-all"
              >
                取消
              </button>
              <button
                type="submit"
                disabled={createMutation.isPending}
                className="px-6 py-3 bg-gradient-to-r from-orange-500 to-amber-600 text-white rounded-xl hover:from-orange-600 hover:to-amber-700 transition-all disabled:opacity-50"
              >
                {createMutation.isPending ? '创建中...' : '创建任务'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* 任务列表 */}
      <div className="bg-gradient-to-br from-slate-800/60 via-slate-800/50 to-slate-900/60 backdrop-blur-xl rounded-3xl p-8 border-2 border-slate-600/50 shadow-2xl shadow-slate-900/50">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-white tracking-tight">交易任务列表</h2>
          <div className="text-sm text-slate-400">
            共 {sortedAndFilteredTasks.length} 条记录
          </div>
        </div>

        {/* 筛选标签 */}
        <div className="mb-6 flex flex-wrap gap-2">
          <button
            onClick={() => toggleFilter('paper')}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all border-2 ${
              activeFilters.has('paper')
                ? 'border-purple-500 bg-slate-700/50 text-slate-300'
                : 'border-transparent bg-slate-700/50 text-slate-300 hover:bg-slate-700/70'
            }`}
          >
            模拟盘
          </button>
          <button
            onClick={() => toggleFilter('live')}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all border-2 ${
              activeFilters.has('live')
                ? 'border-orange-500 bg-slate-700/50 text-slate-300'
                : 'border-transparent bg-slate-700/50 text-slate-300 hover:bg-slate-700/70'
            }`}
          >
            实盘
          </button>
          <button
            onClick={() => toggleFilter('US')}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all border-2 ${
              activeFilters.has('US')
                ? 'border-orange-500 bg-slate-700/50 text-slate-300'
                : 'border-transparent bg-slate-700/50 text-slate-300 hover:bg-slate-700/70'
            }`}
          >
            US
          </button>
          <button
            onClick={() => toggleFilter('HK')}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all border-2 ${
              activeFilters.has('HK')
                ? 'border-orange-500 bg-slate-700/50 text-slate-300'
                : 'border-transparent bg-slate-700/50 text-slate-300 hover:bg-slate-700/70'
            }`}
          >
            HK
          </button>
          <button
            onClick={() => toggleFilter('盘中')}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all border-2 ${
              activeFilters.has('盘中')
                ? 'border-orange-500 bg-slate-700/50 text-slate-300'
                : 'border-transparent bg-slate-700/50 text-slate-300 hover:bg-slate-700/70'
            }`}
          >
            盘中
          </button>
          <button
            onClick={() => toggleFilter('非盘中')}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all border-2 ${
              activeFilters.has('非盘中')
                ? 'border-orange-500 bg-slate-700/50 text-slate-300'
                : 'border-transparent bg-slate-700/50 text-slate-300 hover:bg-slate-700/70'
            }`}
          >
            非盘中
          </button>
          {activeFilters.size > 0 && (
            <button
              onClick={() => setActiveFilters(new Set())}
              className="px-3 py-1.5 rounded-lg text-sm font-medium bg-slate-600/50 text-slate-300 hover:bg-slate-600/70 transition-all"
            >
              清除筛选
            </button>
          )}
        </div>

        {!tradeList || sortedAndFilteredTasks.length === 0 ? (
          <div className="text-center py-12 text-slate-400">
            {tradeList && tradeList.tasks.length > 0 ? '没有匹配筛选条件的任务' : '暂无交易任务'}
          </div>
        ) : (
          <>
            {/* 表头 */}
            <div className="grid grid-cols-12 gap-4 mb-4 pb-3 border-b border-slate-700/50 text-sm font-semibold text-slate-300">
              <div className="col-span-2">
                <button
                  onClick={() => handleSort('task_id')}
                  className="flex items-center gap-2 hover:text-white transition-colors"
                >
                  任务ID
                  {sortField === 'task_id' && (
                    <FontAwesomeIcon 
                      icon={sortOrder === 'asc' ? faSortUp : faSortDown} 
                      className="w-3 h-3"
                    />
                  )}
                  {sortField !== 'task_id' && (
                    <FontAwesomeIcon icon={faSort} className="w-3 h-3 opacity-30" />
                  )}
                </button>
              </div>
              <div className="col-span-2">
                <button
                  onClick={() => handleSort('symbol')}
                  className="flex items-center gap-2 hover:text-white transition-colors"
                >
                  标的
                  {sortField === 'symbol' && (
                    <FontAwesomeIcon 
                      icon={sortOrder === 'asc' ? faSortUp : faSortDown} 
                      className="w-3 h-3"
                    />
                  )}
                  {sortField !== 'symbol' && (
                    <FontAwesomeIcon icon={faSort} className="w-3 h-3 opacity-30" />
                  )}
                </button>
              </div>
              <div className="col-span-2">
                <button
                  onClick={() => handleSort('strategy_name')}
                  className="flex items-center gap-2 hover:text-white transition-colors"
                >
                  策略
                  {sortField === 'strategy_name' && (
                    <FontAwesomeIcon 
                      icon={sortOrder === 'asc' ? faSortUp : faSortDown} 
                      className="w-3 h-3"
                    />
                  )}
                  {sortField !== 'strategy_name' && (
                    <FontAwesomeIcon icon={faSort} className="w-3 h-3 opacity-30" />
                  )}
                </button>
              </div>
              <div className="col-span-1">
                <button
                  onClick={() => handleSort('status')}
                  className="flex items-center gap-2 hover:text-white transition-colors"
                >
                  状态
                  {sortField === 'status' && (
                    <FontAwesomeIcon 
                      icon={sortOrder === 'asc' ? faSortUp : faSortDown} 
                      className="w-3 h-3"
                    />
                  )}
                  {sortField !== 'status' && (
                    <FontAwesomeIcon icon={faSort} className="w-3 h-3 opacity-30" />
                  )}
                </button>
              </div>
              <div className="col-span-1">交易时段</div>
              <div className="col-span-2">
                <button
                  onClick={() => handleSort('started_at')}
                  className="flex items-center gap-2 hover:text-white transition-colors"
                >
                  开始时间
                  {sortField === 'started_at' && (
                    <FontAwesomeIcon 
                      icon={sortOrder === 'asc' ? faSortUp : faSortDown} 
                      className="w-3 h-3"
                    />
                  )}
                  {sortField !== 'started_at' && (
                    <FontAwesomeIcon icon={faSort} className="w-3 h-3 opacity-30" />
                  )}
                </button>
              </div>
              <div className="col-span-2">操作</div>
            </div>
            
            {/* 任务列表项 */}
            <div className="space-y-3">
              {sortedAndFilteredTasks.map((task, index) => {
                const modeColors = getModeColors(task.mode);
                const isOperating = operatingTaskId === task.task_id;
                
                return (
                <div
                  key={task.task_id}
                  onClick={() => navigate(`/trades/${task.task_id}`)}
                  className={`w-full p-6 bg-slate-700/50 hover:bg-slate-700/70 rounded-2xl border border-slate-600/50 ${modeColors.hoverBorder} transition-all duration-300 group shadow-sm hover:shadow-md ${modeColors.hoverShadow} hover:scale-[1.01] cursor-pointer`}
                  style={{ 
                    animationDelay: `${index * 50}ms`,
                    animation: 'fadeInUp 0.5s ease-out'
                  }}
                >
                  <div className="grid grid-cols-12 gap-4 items-center">
                    <div className="col-span-2">
                      <div className={`font-mono text-white text-sm font-semibold ${modeColors.hoverText} transition-colors`}>
                        {task.task_id}
                      </div>
                      <div className="text-xs text-slate-500 mt-1">
                        {task.mode === 'paper' ? '模拟盘' : '实盘'}
                      </div>
                    </div>
                    <div className="col-span-2">
                      <div className={`text-white font-semibold ${modeColors.hoverText} transition-colors`}>
                        {task.symbol}
                      </div>
                      <div className="text-xs text-slate-500 mt-1">
                        {task.symbol.toUpperCase().endsWith('.US') ? 'US' : task.symbol.toUpperCase().endsWith('.HK') ? 'HK' : ''}
                      </div>
                    </div>
                    <div className="col-span-2">
                      <div className="text-slate-200 text-sm">
                        {task.strategy_name}
                      </div>
                    </div>
                    <div className="col-span-1">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${getStatusColor(task.status)}`}>
                        {task.status}
                      </span>
                      {task.current_session && (
                        <div className="text-xs text-slate-500 mt-1">
                          {task.current_session}
                        </div>
                      )}
                    </div>
                    <div className="col-span-1">
                      <div className="text-sm text-slate-300">
                        {task.sessions.length > 0 ? task.sessions.join('、') : '全部'}
                      </div>
                    </div>
                    <div className="col-span-2">
                      <div className="text-sm text-slate-300">
                        {new Date(task.started_at).toLocaleString('zh-CN', {
                          year: 'numeric',
                          month: '2-digit',
                          day: '2-digit',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </div>
                    </div>
                    <div className="col-span-2 flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                      {/* 暂停/恢复按钮 */}
                      {task.status === 'running' && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setOperatingTaskId(task.task_id);
                            pauseMutation.mutate(task.task_id);
                          }}
                          disabled={isOperating}
                          className="px-3 py-1.5 bg-yellow-600/60 hover:bg-yellow-600/80 text-white rounded-lg transition-all disabled:opacity-50 flex items-center justify-center"
                          title="暂停"
                        >
                          <FontAwesomeIcon icon={faPause} className="w-4 h-4" />
                        </button>
                      )}
                      {task.status === 'paused' && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setOperatingTaskId(task.task_id);
                            resumeMutation.mutate(task.task_id);
                          }}
                          disabled={isOperating}
                          className={`px-3 py-1.5 text-white rounded-lg transition-all disabled:opacity-50 flex items-center justify-center ${
                            task.mode === 'paper' 
                              ? 'bg-violet-600/60 hover:bg-violet-600/80' 
                              : 'bg-amber-600/60 hover:bg-amber-600/80'
                          }`}
                          title="恢复"
                        >
                          <FontAwesomeIcon icon={faPlay} className="w-4 h-4" />
                        </button>
                      )}
                      {/* 停止按钮 */}
                      {task.status !== 'stopped' && task.status !== 'completed' && !task.status?.startsWith('error') && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            if (confirm('确定要停止这个任务吗？')) {
                              setOperatingTaskId(task.task_id);
                              stopMutation.mutate(task.task_id);
                            }
                          }}
                          disabled={isOperating}
                          className="px-3 py-1.5 bg-red-600/60 hover:bg-red-600/80 text-white rounded-lg transition-all disabled:opacity-50 flex items-center justify-center"
                          title="停止"
                        >
                          <FontAwesomeIcon icon={faStop} className="w-4 h-4" />
                        </button>
                      )}
                      {/* 删除按钮 */}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setTaskToDelete(task.task_id);
                          setShowDeleteConfirm(true);
                        }}
                        disabled={deleteMutation.isPending}
                        className="px-3 py-1.5 bg-red-600/60 hover:bg-red-600/80 text-white rounded-lg transition-all disabled:opacity-50 flex items-center justify-center"
                        title="删除任务"
                      >
                        <FontAwesomeIcon icon={faTrash} className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              );
              })}
            </div>
          </>
        )}
      </div>

      {/* 删除确认对话框 */}
      {showDeleteConfirm && taskToDelete && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-gradient-to-br from-slate-800 via-slate-900 to-slate-800 rounded-2xl p-8 border border-slate-700 shadow-2xl max-w-md w-full mx-4">
            <h3 className="text-xl font-bold text-white mb-4">确认删除</h3>
            <p className="text-slate-300 mb-6">
              确定要删除交易任务 <span className="font-mono text-white">{taskToDelete}</span> 吗？此操作将删除任务及其所有日志，不可恢复。
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => {
                  setShowDeleteConfirm(false);
                  setTaskToDelete(null);
                }}
                className="px-4 py-2 bg-slate-600 hover:bg-slate-700 text-white rounded-lg text-sm font-medium transition-colors"
              >
                取消
              </button>
              <button
                onClick={() => {
                  if (taskToDelete) {
                    deleteMutation.mutate(taskToDelete);
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
