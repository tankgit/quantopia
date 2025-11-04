import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faPlus, faPlay, faSort, faSortUp, faSortDown, faTrash } from '@fortawesome/free-solid-svg-icons';
import { backtestApi, dataApi } from '../services/api';
import { useStrategies } from '../services/strategies';
import { getValueColor } from '../utils/format';
import type { BacktestCreateRequest, BacktestListItem } from '../types';

type SortField = 'total_return_pct' | 'win_rate' | 'total_trades' | 'start_time';
type SortOrder = 'asc' | 'desc' | null;

export default function BacktestManagement() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [sortField, setSortField] = useState<SortField>('start_time');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [backtestToDelete, setBacktestToDelete] = useState<string | null>(null);
  const [formData, setFormData] = useState<BacktestCreateRequest>({
    data_file_id: '',
    strategy_name: 'MA_Strategy',
    strategy_params: { short_window: 5, long_window: 20 },
    initial_cash: 100000.0,
    commission_rate: 0.001,
  });

  const { data: backtestList } = useQuery({
    queryKey: ['backtestList'],
    queryFn: () => backtestApi.list(),
  });

  const { data: dataList } = useQuery({
    queryKey: ['dataList'],
    queryFn: () => dataApi.list(),
  });

  const { data: strategies } = useStrategies();
  
  const selectedStrategy = strategies?.find(s => s.name === formData.strategy_name);

  const createMutation = useMutation({
    mutationFn: backtestApi.create,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['backtestList'] });
      setShowCreateForm(false);
      navigate(`/backtests/${data.run_id}`);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (runId: string) => backtestApi.delete(runId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['backtestList'] });
      setShowDeleteConfirm(false);
      setBacktestToDelete(null);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate(formData);
  };

  const updateStrategyParam = (key: string, value: number | string) => {
    setFormData({
      ...formData,
      strategy_params: {
        ...formData.strategy_params,
        [key]: value,
      },
    });
  };

  // 处理排序
  const handleSort = (field: SortField) => {
    if (sortField === field) {
      // 切换排序顺序：asc -> desc -> null -> asc
      if (sortOrder === 'asc') {
        setSortOrder('desc');
      } else if (sortOrder === 'desc') {
        setSortOrder(null);
        setSortField('start_time');
        setSortOrder('desc');
      }
    } else {
      setSortField(field);
      setSortOrder('desc');
    }
  };

  // 排序后的回测列表
  const sortedBacktests = useMemo(() => {
    if (!backtestList?.backtests) return [];
    
    const backtests = [...backtestList.backtests];
    
    if (sortOrder === null || sortField === 'start_time') {
      // 默认按时间倒序
      return backtests.sort((a, b) => 
        new Date(b.start_time).getTime() - new Date(a.start_time).getTime()
      );
    }
    
    return backtests.sort((a, b) => {
      let aValue: number;
      let bValue: number;
      
      if (sortField === 'total_return_pct') {
        aValue = a.stats.total_return_pct;
        bValue = b.stats.total_return_pct;
      } else if (sortField === 'win_rate') {
        aValue = a.stats.win_rate ?? 0;
        bValue = b.stats.win_rate ?? 0;
      } else if (sortField === 'total_trades') {
        aValue = a.stats.total_trades;
        bValue = b.stats.total_trades;
      } else {
        return 0;
      }
      
      if (sortOrder === 'asc') {
        return aValue - bValue;
      } else {
        return bValue - aValue;
      }
    });
  }, [backtestList, sortField, sortOrder]);

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-bold text-white mb-2">回测管理</h1>
          <p className="text-slate-400 text-sm">创建和管理策略回测任务</p>
        </div>
        <button
          onClick={() => setShowCreateForm(!showCreateForm)}
          className="px-6 py-3 bg-gradient-to-r from-purple-500 to-violet-600 text-white rounded-2xl hover:from-purple-600 hover:to-violet-700 transition-all duration-300 shadow-sm shadow-purple-500/15 flex items-center gap-3 font-semibold hover:scale-105 active:scale-95 border border-purple-400/40"
        >
          <FontAwesomeIcon icon={faPlus} className={`w-5 h-5 transition-transform duration-300 ${showCreateForm ? 'rotate-45' : ''}`} />
          {showCreateForm ? '取消' : '新建回测'}
        </button>
      </div>

      {/* 创建回测表单 */}
      {showCreateForm && (
        <div className="bg-gradient-to-br from-slate-800/40 via-slate-800/30 to-slate-900/40 backdrop-blur-xl rounded-3xl p-8 border border-slate-700/30 shadow-2xl shadow-slate-900/50 animate-fadeIn">
          <h2 className="text-2xl font-semibold text-white mb-6">新建回测任务</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">选择数据文件</label>
              <select
                value={formData.data_file_id}
                onChange={(e) => setFormData({ ...formData, data_file_id: e.target.value })}
                className="w-full px-4 py-2.5 bg-slate-800/50 border border-slate-700 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
                required
              >
                <option value="">请选择...</option>
                {dataList?.files.map((file) => (
                  <option key={file.file_id} value={file.file_id}>
                    {file.file_id} - {file.length}个数据点 - {file.trend}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">选择策略</label>
              <select
                value={formData.strategy_name}
                onChange={(e) => {
                  const newStrategy = strategies?.find(s => s.name === e.target.value);
                  const defaultParams: Record<string, any> = {};
                  if (newStrategy) {
                    Object.entries(newStrategy.params).forEach(([key, param]: [string, any]) => {
                      defaultParams[key] = param.default;
                    });
                  }
                  setFormData({ ...formData, strategy_name: e.target.value, strategy_params: defaultParams });
                }}
                className="w-full px-4 py-2.5 bg-slate-800/50 border border-slate-700 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
              >
                {strategies?.map((s) => (
                  <option key={s.name} value={s.name}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>

            {selectedStrategy && (
              <div className="bg-slate-800/50 rounded-xl p-6 border border-slate-700/50">
                <h3 className="text-sm font-medium text-white mb-4">策略参数</h3>
                <div className="grid grid-cols-2 gap-4">
                  {Object.entries(selectedStrategy.params).map(([key, param]: [string, any]) => (
                    <div key={key}>
                      <label className="block text-sm font-medium text-slate-300 mb-2">
                        {param.name}
                      </label>
                      <input
                        type="number"
                        value={formData.strategy_params[key] ?? param.default}
                        onChange={(e) => {
                          const value = param.type === 'number' 
                            ? (param.default % 1 === 0 ? parseInt(e.target.value) : parseFloat(e.target.value))
                            : e.target.value;
                          updateStrategyParam(key, value);
                        }}
                        className="w-full px-4 py-2.5 bg-slate-700/50 border border-slate-600 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
                        min={param.min}
                        max={param.max}
                        step={param.default % 1 === 0 ? 1 : 0.1}
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">初始资金</label>
                <input
                  type="number"
                  step="1000"
                  value={formData.initial_cash}
                  onChange={(e) => setFormData({ ...formData, initial_cash: parseFloat(e.target.value) })}
                  className="w-full px-4 py-3 bg-slate-700/40 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-400/50 transition-all duration-300 hover:bg-slate-700/60"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">手续费率</label>
                <input
                  type="number"
                  step="0.0001"
                  value={formData.commission_rate}
                  onChange={(e) => setFormData({ ...formData, commission_rate: parseFloat(e.target.value) })}
                  className="w-full px-4 py-3 bg-slate-700/40 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-400/50 transition-all duration-300 hover:bg-slate-700/60"
                  required
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={createMutation.isPending || !formData.data_file_id}
              className="px-8 py-4 bg-gradient-to-r from-purple-600 to-violet-700 text-white rounded-2xl hover:from-purple-700 hover:to-violet-800 disabled:opacity-50 transition-all duration-300 shadow-sm shadow-purple-500/15 font-semibold flex items-center gap-3 hover:scale-105 active:scale-95 border border-purple-400/40"
            >
              <FontAwesomeIcon icon={faPlay} className="w-5 h-5" />
              {createMutation.isPending ? '运行中...' : '开始回测'}
            </button>
          </form>
        </div>
      )}

      {/* 回测列表 */}
      <div className="bg-gradient-to-br from-slate-800/60 via-slate-800/50 to-slate-900/60 backdrop-blur-xl rounded-3xl p-8 border-2 border-slate-600/50 shadow-2xl shadow-slate-900/50">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-white tracking-tight">回测记录</h2>
          <div className="text-sm text-slate-400">
            共 {sortedBacktests.length} 条记录
          </div>
        </div>
        
        {sortedBacktests.length === 0 ? (
          <div className="text-slate-400 text-center py-12">暂无回测记录</div>
        ) : (
          <>
            {/* 表头 */}
            <div className="grid grid-cols-12 gap-4 mb-4 pb-3 border-b border-slate-700/50 text-sm font-semibold text-slate-300">
              <div className="col-span-2">运行ID</div>
              <div className="col-span-2">
                <button
                  onClick={() => handleSort('total_return_pct')}
                  className="flex items-center gap-2 hover:text-white transition-colors"
                >
                  总收益率
                  {sortField === 'total_return_pct' && (
                    <FontAwesomeIcon 
                      icon={sortOrder === 'asc' ? faSortUp : faSortDown} 
                      className="w-3 h-3"
                    />
                  )}
                  {sortField !== 'total_return_pct' && (
                    <FontAwesomeIcon icon={faSort} className="w-3 h-3 opacity-30" />
                  )}
                </button>
              </div>
              <div className="col-span-2">
                <button
                  onClick={() => handleSort('win_rate')}
                  className="flex items-center gap-2 hover:text-white transition-colors"
                >
                  胜率
                  {sortField === 'win_rate' && (
                    <FontAwesomeIcon 
                      icon={sortOrder === 'asc' ? faSortUp : faSortDown} 
                      className="w-3 h-3"
                    />
                  )}
                  {sortField !== 'win_rate' && (
                    <FontAwesomeIcon icon={faSort} className="w-3 h-3 opacity-30" />
                  )}
                </button>
              </div>
              <div className="col-span-2">
                <button
                  onClick={() => handleSort('total_trades')}
                  className="flex items-center gap-2 hover:text-white transition-colors"
                >
                  交易次数
                  {sortField === 'total_trades' && (
                    <FontAwesomeIcon 
                      icon={sortOrder === 'asc' ? faSortUp : faSortDown} 
                      className="w-3 h-3"
                    />
                  )}
                  {sortField !== 'total_trades' && (
                    <FontAwesomeIcon icon={faSort} className="w-3 h-3 opacity-30" />
                  )}
                </button>
              </div>
              <div className="col-span-2">数据文件</div>
              <div className="col-span-1">策略</div>
              <div className="col-span-1 text-right">操作</div>
            </div>
            
            {/* 回测列表项 */}
            <div className="space-y-3">
              {sortedBacktests.map((backtest, index) => (
                <div
                  key={backtest.run_id}
                  className="w-full text-left p-6 bg-slate-700/50 hover:bg-slate-700/70 rounded-2xl border border-slate-600/50 hover:border-purple-500/50 transition-all duration-300 group shadow-sm hover:shadow-md hover:shadow-purple-500/10 hover:scale-[1.01]"
                  style={{ 
                    animationDelay: `${index * 50}ms`,
                    animation: 'fadeInUp 0.5s ease-out'
                  }}
                >
                  <div className="grid grid-cols-12 gap-4 items-center">
                    <div 
                      className="col-span-11 cursor-pointer"
                      onClick={() => navigate(`/backtests/${backtest.run_id}`)}
                    >
                      <div className="grid grid-cols-12 gap-4 items-center">
                        <div className="col-span-2">
                          <div className="font-mono text-white text-sm font-semibold group-hover:text-purple-300 transition-colors">
                            {backtest.run_id}
                          </div>
                          <div className="text-xs text-slate-500 mt-1">
                            {new Date(backtest.start_time).toLocaleDateString('zh-CN')}
                          </div>
                        </div>
                        <div className={`col-span-2 text-lg font-bold ${getValueColor(backtest.stats.total_return_pct)}`}>
                          {backtest.stats.total_return_pct.toFixed(2)}%
                        </div>
                        <div className="col-span-2">
                          <div className="text-lg font-bold text-cyan-300">
                            {backtest.stats.win_rate?.toFixed(2) ?? '0.00'}%
                          </div>
                        </div>
                        <div className="col-span-2">
                          <div className="text-lg font-bold text-slate-200">
                            {backtest.stats.total_trades}
                          </div>
                        </div>
                        <div className="col-span-2">
                          <div className="text-sm text-slate-300 font-mono">
                            {backtest.data_file_id}
                          </div>
                        </div>
                        <div className="col-span-1">
                          <div className="text-sm text-slate-300">
                            {backtest.strategy_name}
                          </div>
                        </div>
                      </div>
                    </div>
                    <div className="col-span-1 flex justify-end" onClick={(e) => e.stopPropagation()}>
                      <button
                        onClick={() => {
                          setBacktestToDelete(backtest.run_id);
                          setShowDeleteConfirm(true);
                        }}
                        className="px-2 py-2 rounded-lg bg-red-600/60 border border-red-400/40 text-white hover:bg-red-600/80 flex items-center justify-center"
                        title="删除回测"
                      >
                        <FontAwesomeIcon icon={faTrash} className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {/* 删除确认对话框 */}
      {showDeleteConfirm && backtestToDelete && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-gradient-to-br from-slate-800 via-slate-900 to-slate-800 rounded-2xl p-8 border border-slate-700 shadow-2xl max-w-md w-full mx-4">
            <h3 className="text-xl font-bold text-white mb-4">确认删除回测记录</h3>
            <p className="text-slate-300 mb-6">
              确定要删除回测记录 <span className="font-mono text-white">{backtestToDelete}</span> 吗？此操作将删除回测及其所有数据，且不可恢复。
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => {
                  setShowDeleteConfirm(false);
                  setBacktestToDelete(null);
                }}
                className="px-4 py-2 bg-slate-600 hover:bg-slate-700 text-white rounded-lg text-sm font-medium transition-colors"
              >
                取消
              </button>
              <button
                onClick={() => {
                  if (backtestToDelete) {
                    deleteMutation.mutate(backtestToDelete);
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

