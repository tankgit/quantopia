import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faPlus, faChartLine, faChartBar, faChartArea, faSatelliteDish, faPause, faPlay, faStop, faEye, faTrash } from '@fortawesome/free-solid-svg-icons';
import { dataApi, fetchApi } from '../services/api';
import DataChart from '../components/DataChart';
import type { DataFile, DataGenerateRequest, FetchTaskCreateRequest, FetchTaskSummary } from '../types';

export default function DataManagement() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null);
  const [showGenerateForm, setShowGenerateForm] = useState(false);
  const [showFetchForm, setShowFetchForm] = useState(false);
  const [chartType, setChartType] = useState<'line' | 'area' | 'bar'>('line');
  const [selectedFilters, setSelectedFilters] = useState<Set<string>>(new Set());
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [formData, setFormData] = useState<DataGenerateRequest>({
    length: 100,
    base_mean: 100.0,
    trend: 'stable',
    volatility_prob: 0.3,
    volatility_scale: 0.02,
  });

  const [fetchForm, setFetchForm] = useState<FetchTaskCreateRequest>({
    symbol: 'AAPL.US',
    mode: 'paper',
    interval: { value: 5, unit: 'seconds' },
    sessions: ['盘中'],
    duration: { mode: 'permanent' },
  });

  const { data: dataList, isLoading } = useQuery({
    queryKey: ['dataList'],
    queryFn: () => dataApi.list(),
  });

  const { data: selectedData } = useQuery({
    queryKey: ['data', selectedFileId],
    queryFn: () => dataApi.get(selectedFileId!),
    enabled: !!selectedFileId,
  });

  // 删除数据mutation
  const deleteMutation = useMutation({
    mutationFn: (fileId: string) => dataApi.delete(fileId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dataList'] });
      setSelectedFileId(null);
      setShowDeleteConfirm(false);
    },
  });

  // 筛选和排序数据
  const filteredFiles = useMemo(() => {
    if (!dataList?.files) return [];
    
    let files = dataList.files;
    
    // 筛选
    if (selectedFilters.size > 0) {
      files = files.filter((file: DataFile) => {
        // 类型筛选：如果选中了类型筛选，文件类型必须匹配其中一个
        const hasTypeFilter = selectedFilters.has('实盘') || selectedFilters.has('生成');
        let typePass = true;
        if (hasTypeFilter) {
          const matchReal = selectedFilters.has('实盘') && file.type === 'fetched';
          const matchGenerated = selectedFilters.has('生成') && file.type === 'generated';
          typePass = matchReal || matchGenerated;
        }
        
        // 符号后缀筛选：如果选中了符号筛选，符号后缀必须匹配其中一个
        const hasSymbolFilter = selectedFilters.has('US') || selectedFilters.has('HK');
        let symbolPass = true;
        if (hasSymbolFilter) {
          const matchUS = selectedFilters.has('US') && file.symbol?.endsWith('.US');
          const matchHK = selectedFilters.has('HK') && file.symbol?.endsWith('.HK');
          symbolPass = matchUS || matchHK;
        }
        
        // 趋势筛选：如果选中了趋势筛选，生成数据的趋势必须匹配其中一个
        const hasTrendFilter = selectedFilters.has('up') || selectedFilters.has('down') || selectedFilters.has('stable');
        let trendPass = true;
        if (hasTrendFilter && file.type === 'generated') {
          const matchUp = selectedFilters.has('up') && file.trend === 'up';
          const matchDown = selectedFilters.has('down') && file.trend === 'down';
          const matchStable = selectedFilters.has('stable') && file.trend === 'stable';
          trendPass = matchUp || matchDown || matchStable;
        } else if (hasTrendFilter && file.type !== 'generated') {
          // 如果选中了趋势筛选但文件不是生成数据，则过滤掉
          trendPass = false;
        }
        
        return typePass && symbolPass && trendPass;
      });
    }
    
    // 按时间降序排序
    files = [...files].sort((a, b) => {
      const dateA = new Date(a.generated_at).getTime();
      const dateB = new Date(b.generated_at).getTime();
      return dateB - dateA; // 降序
    });
    
    return files;
  }, [dataList, selectedFilters]);

  const toggleFilter = (filter: string) => {
    setSelectedFilters(prev => {
      const newSet = new Set(prev);
      if (newSet.has(filter)) {
        newSet.delete(filter);
      } else {
        newSet.add(filter);
      }
      return newSet;
    });
  };

  const { data: fetchTasks } = useQuery({
    queryKey: ['fetchTasks'],
    queryFn: () => fetchApi.list(),
    refetchInterval: 5000,
  });

  const generateMutation = useMutation({
    mutationFn: dataApi.generate,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['dataList'] });
      setSelectedFileId(data.file_id);
      setShowGenerateForm(false);
    },
  });

  const createFetchMutation = useMutation({
    mutationFn: fetchApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['fetchTasks'] });
      setShowFetchForm(false);
    },
  });

  const pauseFetchMutation = useMutation({
    mutationFn: fetchApi.pause,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['fetchTasks'] });
    },
  });

  const resumeFetchMutation = useMutation({
    mutationFn: fetchApi.resume,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['fetchTasks'] });
    },
  });

  const stopFetchMutation = useMutation({
    mutationFn: fetchApi.stop,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['fetchTasks'] });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    generateMutation.mutate(formData);
  };

  const handleFetchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createFetchMutation.mutate(fetchForm);
  };

  const trendOptions = [
    { value: 'up', label: '上涨' },
    { value: 'stable', label: '平稳' },
    { value: 'down', label: '下跌' },
  ];

  const intervalUnitOptions = [
    { value: 'seconds', label: '秒' },
    { value: 'minutes', label: '分' },
    { value: 'hours', label: '时' },
  ];

  const durationModes = [
    { value: 'permanent', label: '永久' },
    { value: 'finite', label: '自定义' },
  ];

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-bold text-white mb-2">数据管理</h1>
          <p className="text-slate-400 text-sm">生成和管理模拟股票数据，以及爬取实盘数据</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => {
              if (showGenerateForm) {
                setShowGenerateForm(false);
              }
              setShowFetchForm(!showFetchForm);
            }}
            className="px-6 py-3 bg-gradient-to-r from-emerald-500 to-teal-600 text-white rounded-2xl hover:from-emerald-600 hover:to-teal-700 transition-all duration-300 shadow-sm shadow-emerald-500/15 flex items-center gap-3 font-semibold hover:scale-105 border border-emerald-400/40"
          >
            <FontAwesomeIcon icon={faSatelliteDish} className="w-4 h-4" />
            {showFetchForm ? '取消' : '爬取实盘数据'}
          </button>
          <button
            onClick={() => {
              if (showFetchForm) {
                setShowFetchForm(false);
              }
              setShowGenerateForm(!showGenerateForm);
            }}
            className="px-6 py-3 bg-gradient-to-r from-blue-500 to-cyan-600 text-white rounded-2xl hover:from-blue-600 hover:to-cyan-700 transition-all duration-300 shadow-sm shadow-blue-500/15 flex items-center gap-3 font-semibold hover:scale-105 border border-blue-400/40"
          >
            <FontAwesomeIcon icon={faPlus} className="w-4 h-4" />
            {showGenerateForm ? '取消' : '生成新数据'}
          </button>
        </div>
      </div>

      {/* 生成表单 */}
      {showGenerateForm && (
        <div className="bg-gradient-to-br from-slate-800/40 via-slate-800/30 to-slate-900/40 backdrop-blur-xl rounded-3xl p-8 border border-slate-700/30 shadow-2xl shadow-slate-900/50 animate-fadeIn">
          <h2 className="text-2xl font-bold text-white mb-8 tracking-tight">生成模拟数据</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">数据长度</label>
                <input
                  type="number"
                  value={formData.length}
                  onChange={(e) => setFormData({ ...formData, length: parseInt(e.target.value) })}
                  className="w-full px-4 py-3 bg-slate-700/40 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-400/50 transition-all duration-300 hover:bg-slate-700/60"
                  min={10}
                  max={1000}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">基础均值</label>
                <input
                  type="number"
                  step="0.1"
                  value={formData.base_mean}
                  onChange={(e) => setFormData({ ...formData, base_mean: parseFloat(e.target.value) })}
                  className="w-full px-4 py-3 bg-slate-700/40 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-400/50 transition-all duration-300 hover:bg-slate-700/60"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">整体趋势</label>
                <select
                  value={formData.trend}
                  onChange={(e) => setFormData({ ...formData, trend: e.target.value as any })}
                  className="w-full px-4 py-3 bg-slate-700/40 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-400/50 transition-all duration-300 hover:bg-slate-700/60"
                >
                  {trendOptions.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">起始股价（可选）</label>
                <input
                  type="number"
                  step="0.1"
                  value={formData.start_price || ''}
                  onChange={(e) => setFormData({ ...formData, start_price: e.target.value ? parseFloat(e.target.value) : null })}
                  className="w-full px-4 py-3 bg-slate-700/40 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-400/50 transition-all duration-300 hover:bg-slate-700/60"
                  placeholder="留空自动生成"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">最终股价（可选）</label>
                <input
                  type="number"
                  step="0.1"
                  value={formData.end_price || ''}
                  onChange={(e) => setFormData({ ...formData, end_price: e.target.value ? parseFloat(e.target.value) : null })}
                  className="w-full px-4 py-3 bg-slate-700/40 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-400/50 transition-all duration-300 hover:bg-slate-700/60"
                  placeholder="留空自动生成"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">波动概率 (0-1)</label>
                <input
                  type="number"
                  step="0.01"
                  value={formData.volatility_prob}
                  onChange={(e) => setFormData({ ...formData, volatility_prob: parseFloat(e.target.value) })}
                  className="w-full px-4 py-3 bg-slate-700/40 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-400/50 transition-all duration-300 hover:bg-slate-700/60"
                  min={0}
                  max={1}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">波动幅度</label>
                <input
                  type="number"
                  step="0.001"
                  value={formData.volatility_scale}
                  onChange={(e) => setFormData({ ...formData, volatility_scale: parseFloat(e.target.value) })}
                  className="w-full px-4 py-3 bg-slate-700/40 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-400/50 transition-all duration-300 hover:bg-slate-700/60"
                  min={0}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">随机种子（可选）</label>
                <input
                  type="number"
                  value={formData.seed || ''}
                  onChange={(e) => setFormData({ ...formData, seed: e.target.value ? parseInt(e.target.value) : null })}
                  className="w-full px-4 py-3 bg-slate-700/40 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-400/50 transition-all duration-300 hover:bg-slate-700/60"
                  placeholder="留空随机"
                />
              </div>
            </div>
            <button
              type="submit"
              disabled={generateMutation.isPending}
              className="px-8 py-4 bg-gradient-to-r from-blue-600 to-cyan-700 text-white rounded-2xl hover:from-blue-700 hover:to-cyan-800 disabled:opacity-50 transition-all duration-300 shadow-sm shadow-blue-500/15 font-semibold hover:scale-105 active:scale-95 border border-blue-400/40"
            >
              {generateMutation.isPending ? '生成中...' : '生成数据'}
            </button>
          </form>
        </div>
      )}

      {/* 爬取实盘数据表单 */}
      {showFetchForm && (
        <div className="bg-gradient-to-br from-emerald-900/30 via-emerald-900/20 to-slate-900/40 backdrop-blur-xl rounded-3xl p-8 border border-emerald-700/30 shadow-2xl shadow-emerald-900/30 animate-fadeIn">
          <h2 className="text-2xl font-bold text-white mb-8 tracking-tight">创建爬取任务</h2>
          <form onSubmit={handleFetchSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">股票代码</label>
                <input
                  type="text"
                  value={fetchForm.symbol}
                  onChange={(e) => setFetchForm({ ...fetchForm, symbol: e.target.value })}
                  className="w-full px-4 py-3 bg-slate-700/40 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-400/50 transition-all duration-300 hover:bg-slate-700/60"
                  placeholder="如 AAPL.US 或 700.HK"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">交易环境</label>
                <select
                  value={fetchForm.mode}
                  onChange={(e) => setFetchForm({ ...fetchForm, mode: e.target.value as any })}
                  className="w-full px-4 py-3 bg-slate-700/40 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-400/50 transition-all duration-300 hover:bg-slate-700/60"
                >
                  <option value="paper">模拟盘</option>
                  <option value="live">实盘</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">时间间隔</label>
                <div className="flex gap-2">
                  <input
                    type="number"
                    min={1}
                    value={fetchForm.interval.value}
                    onChange={(e) => setFetchForm({ ...fetchForm, interval: { ...fetchForm.interval, value: parseInt(e.target.value) } })}
                    className="w-32 px-4 py-3 bg-slate-700/40 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-400/50 transition-all duration-300 hover:bg-slate-700/60"
                  />
                  <select
                    value={fetchForm.interval.unit}
                    onChange={(e) => setFetchForm({ ...fetchForm, interval: { ...fetchForm.interval, unit: e.target.value as any } })}
                    className="px-4 py-3 bg-slate-700/40 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-400/50 transition-all duration-300 hover:bg-slate-700/60"
                  >
                    {intervalUnitOptions.map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">盘段（可多选）</label>
                <div className="flex flex-wrap gap-2">
                  {['盘前','盘中','盘后','夜盘'].map((s) => {
                    const checked = fetchForm.sessions.includes(s);
                    return (
                      <button
                        key={s}
                        type="button"
                        onClick={() => {
                          setFetchForm({
                            ...fetchForm,
                            sessions: checked
                              ? fetchForm.sessions.filter(x => x !== s)
                              : [...fetchForm.sessions, s],
                          });
                        }}
                        className={`px-3 py-2 rounded-xl text-sm border transition-all ${checked ? 'bg-emerald-600/60 text-white border-emerald-400/40' : 'bg-slate-700/40 text-slate-200 border-slate-600/50 hover:bg-slate-700/60'}`}
                      >
                        {s}
                      </button>
                    );
                  })}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">爬取时长</label>
                <div className="space-y-2">
                  <select
                    value={fetchForm.duration.mode}
                    onChange={(e) => setFetchForm({ ...fetchForm, duration: { ...fetchForm.duration, mode: e.target.value as any } })}
                    className="w-full px-4 py-3 bg-slate-700/40 backdrop-blur-sm border border-slate-600/50 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-400/50 transition-all duration-300 hover:bg-slate-700/60"
                  >
                    {durationModes.map(d => (
                      <option key={d.value} value={d.value}>{d.label}</option>
                    ))}
                  </select>
                  {fetchForm.duration.mode === 'finite' && (
                    <div className="grid grid-cols-4 gap-2">
                      <input
                        type="number"
                        min={0}
                        placeholder="天"
                        onChange={(e) => setFetchForm({ ...fetchForm, duration: { ...fetchForm.duration, days: parseInt(e.target.value || '0') } })}
                        className="px-3 py-2 bg-slate-700/40 border border-slate-600/50 rounded-xl text-white"
                      />
                      <input
                        type="number"
                        min={0}
                        placeholder="时"
                        onChange={(e) => setFetchForm({ ...fetchForm, duration: { ...fetchForm.duration, hours: parseInt(e.target.value || '0') } })}
                        className="px-3 py-2 bg-slate-700/40 border border-slate-600/50 rounded-xl text-white"
                      />
                      <input
                        type="number"
                        min={0}
                        placeholder="分"
                        onChange={(e) => setFetchForm({ ...fetchForm, duration: { ...fetchForm.duration, minutes: parseInt(e.target.value || '0') } })}
                        className="px-3 py-2 bg-slate-700/40 border border-slate-600/50 rounded-xl text-white"
                      />
                      <input
                        type="number"
                        min={0}
                        placeholder="秒"
                        onChange={(e) => setFetchForm({ ...fetchForm, duration: { ...fetchForm.duration, seconds: parseInt(e.target.value || '0') } })}
                        className="px-3 py-2 bg-slate-700/40 border border-slate-600/50 rounded-xl text-white"
                      />
                    </div>
                  )}
                </div>
              </div>
            </div>
            <button
              type="submit"
              disabled={createFetchMutation.isPending}
              className="px-8 py-4 bg-gradient-to-r from-emerald-600 to-teal-700 text-white rounded-2xl hover:from-emerald-700 hover:to-teal-800 disabled:opacity-50 transition-all duration-300 shadow-sm shadow-emerald-500/15 font-semibold hover:scale-105 active:scale-95 border border-emerald-400/40"
            >
              {createFetchMutation.isPending ? '创建中...' : '开始爬取'}
            </button>
          </form>
        </div>
      )}

      {/* 爬取任务列表 */}
      <div className="bg-gradient-to-br from-slate-800/60 via-slate-800/50 to-slate-900/60 backdrop-blur-xl rounded-3xl p-8 border-2 border-slate-600/50 shadow-2xl shadow-slate-900/50">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-white tracking-tight">爬取任务</h2>
          <div className="text-sm text-slate-400">共 {fetchTasks?.count ?? 0} 个任务</div>
        </div>
        <div className="space-y-2 max-h-[300px] overflow-y-auto">
          {fetchTasks?.tasks?.map((t: FetchTaskSummary) => (
            <div key={t.task_id} className="flex items-center justify-between p-4 bg-slate-800/60 rounded-xl border border-slate-600/50">
              <div>
                <div className="text-white font-mono text-sm">{t.task_id} · {t.symbol} · {t.mode}</div>
                <div className="text-xs text-slate-400 mt-1">{new Date(t.started_at).toLocaleString('zh-CN')} · 每 {t.interval.value} {t.interval.unit}</div>
              </div>
              <div className="flex items-center gap-2">
                <span className={`px-2 py-1 text-xs rounded-full border ${t.status.startsWith('error') ? 'text-red-300 border-red-400/30' : t.status === 'running' ? 'text-emerald-300 border-emerald-400/30' : t.status === 'paused' ? 'text-yellow-300 border-yellow-400/30' : 'text-slate-300 border-slate-400/30'}`}>{t.status}</span>
                {t.status === 'running' && (
                  <button
                    onClick={() => pauseFetchMutation.mutate(t.task_id)}
                    className="px-2 py-1 rounded-lg text-xs bg-yellow-600/60 text-white hover:bg-yellow-600/80 border border-yellow-400/40"
                    title="暂停"
                  >
                    <FontAwesomeIcon icon={faPause} className="w-3 h-3" />
                  </button>
                )}
                {t.status === 'paused' && (
                  <button
                    onClick={() => resumeFetchMutation.mutate(t.task_id)}
                    className="px-2 py-1 rounded-lg text-xs bg-emerald-600/60 text-white hover:bg-emerald-600/80 border border-emerald-400/40"
                    title="恢复"
                  >
                    <FontAwesomeIcon icon={faPlay} className="w-3 h-3" />
                  </button>
                )}
                {t.status !== 'stopped' && t.status !== 'completed' && !t.status.startsWith('error') && (
                  <button
                    onClick={() => stopFetchMutation.mutate(t.task_id)}
                    className="px-2 py-1 rounded-lg text-xs bg-red-600/60 text-white hover:bg-red-600/80 border border-red-400/40"
                    title="停止"
                  >
                    <FontAwesomeIcon icon={faStop} className="w-3 h-3" />
                  </button>
                )}
                <button
                  onClick={() => navigate(`/data/fetch/${t.task_id}`)}
                  className="px-2 py-1 rounded-lg text-xs bg-blue-600/60 text-white hover:bg-blue-600/80 border border-blue-400/40"
                  title="查看详情"
                >
                  <FontAwesomeIcon icon={faEye} className="w-3 h-3" />
                </button>
              </div>
            </div>
          ))}
          {(!fetchTasks || fetchTasks.count === 0) && (
            <div className="text-slate-400 text-center py-6">暂无爬取任务</div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 数据列表 */}
        <div className="lg:col-span-1">
          <div className="bg-gradient-to-br from-slate-800/60 via-slate-800/50 to-slate-900/60 backdrop-blur-xl rounded-3xl p-8 border-2 border-slate-600/50 shadow-2xl shadow-slate-900/50">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-2xl font-bold text-white tracking-tight">数据列表</h2>
              <div className="text-sm text-slate-400">{filteredFiles.length} 个</div>
            </div>
            
            {/* 筛选标签 */}
            <div className="mb-6 flex flex-wrap gap-2">
              {['实盘', '生成', 'US', 'HK', 'up', 'down', 'stable'].map((filter) => {
                const isSelected = selectedFilters.has(filter);
                let filterLabel = filter;
                if (filter === 'up') filterLabel = '↑ up';
                else if (filter === 'down') filterLabel = '↓ down';
                else if (filter === 'stable') filterLabel = '→ stable';
                
                return (
                  <button
                    key={filter}
                    onClick={() => toggleFilter(filter)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 ${
                      isSelected
                        ? filter === '实盘'
                          ? 'bg-emerald-600/60 text-emerald-200 border border-emerald-400/40'
                          : filter === '生成'
                          ? 'bg-blue-600/60 text-blue-200 border border-blue-400/40'
                          : filter === 'US'
                          ? 'bg-purple-600/60 text-purple-200 border border-purple-400/40'
                          : filter === 'HK'
                          ? 'bg-orange-600/60 text-orange-200 border border-orange-400/40'
                          : filter === 'up'
                          ? 'bg-red-600/60 text-red-200 border border-red-400/40'
                          : filter === 'down'
                          ? 'bg-green-600/60 text-green-200 border border-green-400/40'
                          : 'bg-slate-600/60 text-slate-200 border border-slate-400/40'
                        : 'bg-slate-700/40 text-slate-300 border border-slate-600/50 hover:bg-slate-700/60'
                    }`}
                  >
                    {filterLabel}
                  </button>
                );
              })}
            </div>

            {isLoading ? (
              <div className="text-slate-400">加载中...</div>
            ) : filteredFiles.length === 0 ? (
              <div className="text-slate-400 text-center py-8">没有匹配的数据</div>
            ) : (
              <div className="space-y-2 max-h-[600px] overflow-y-auto">
                {filteredFiles.map((file: DataFile) => (
                  <button
                    key={file.file_id}
                    onClick={() => setSelectedFileId(file.file_id)}
                    className={`w-full text-left p-4 rounded-xl transition-all duration-200 ${
                      selectedFileId === file.file_id
                        ? 'bg-gradient-to-r from-blue-600 to-cyan-600 text-white shadow-sm shadow-blue-500/20 border border-blue-400/50'
                        : 'bg-slate-800/60 hover:bg-slate-800/80 text-slate-200 border border-slate-600/50 hover:border-blue-500/30'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="font-medium">{file.file_id}</div>
                      <span className={`px-2 py-0.5 text-xs rounded-full border ${
                        file.type === 'fetched' 
                          ? 'bg-emerald-600/30 text-emerald-300 border-emerald-400/40' 
                          : 'bg-blue-600/30 text-blue-300 border-blue-400/40'
                      }`}>
                        {file.type === 'fetched' ? '实盘' : '生成'}
                      </span>
                    </div>
                    <div className="text-xs mt-1">
                      <span className="font-bold">{file.length}</span> 个数据点
                      {file.type === 'generated' && file.trend && (
                        <> | <span className={file.trend === 'up' ? 'text-red-400' : file.trend === 'down' ? 'text-green-400' : ''}>
                          {file.trend === 'up' ? '↑' : file.trend === 'down' ? '↓' : '→'} {file.trend}
                        </span></>
                      )}
                      {file.type === 'fetched' && file.symbol && (
                        <> | <span className={file.symbol.toUpperCase().endsWith('.US') ? 'text-purple-300' : file.symbol.toUpperCase().endsWith('.HK') ? 'text-orange-300' : ''}>
                          {file.symbol}
                        </span></>
                      )}
                    </div>
                    <div className="text-xs mt-1">
                      {new Date(file.generated_at).toLocaleString('zh-CN')}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* 数据详情和图表 */}
        <div className="lg:col-span-2">
          {selectedData ? (
            <div className="space-y-6">
              <div className="bg-gradient-to-br from-slate-800/40 via-slate-800/30 to-slate-900/40 backdrop-blur-xl rounded-3xl p-8 border border-slate-700/30 shadow-2xl shadow-slate-900/50">
                <div className="flex items-center justify-between mb-8">
                  <h2 className="text-2xl font-bold text-white tracking-tight">数据详情</h2>
                  <button
                    onClick={() => setShowDeleteConfirm(true)}
                    className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
                  >
                    <FontAwesomeIcon icon={faTrash} className="w-4 h-4" />
                    删除数据
                  </button>
                </div>
                {selectedData.type === 'generated' ? (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div>
                      <div className="text-xs text-slate-500 mb-1">文件ID</div>
                      <div className="text-white font-mono text-sm">{selectedData.file_id}</div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-500 mb-1">数据长度</div>
                      <div className="text-white text-sm">{selectedData.data_length}</div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-500 mb-1">起始价格 ($)</div>
                      <div className="text-white text-sm">{selectedData.metadata.start_price?.toFixed(3) || 'N/A'}</div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-500 mb-1">最终价格 ($)</div>
                      <div className="text-white text-sm">{selectedData.metadata.end_price?.toFixed(3) || 'N/A'}</div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-500 mb-1">趋势</div>
                      <div className={`text-sm font-medium ${
                        selectedData.metadata.trend === 'up' 
                          ? 'text-red-400' 
                          : selectedData.metadata.trend === 'down' 
                          ? 'text-green-400' 
                          : 'text-slate-400'
                      }`}>
                        {selectedData.metadata.trend === 'up' ? '↑ 上涨' : selectedData.metadata.trend === 'down' ? '↓ 下跌' : '→ 平稳'}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-500 mb-1">波动概率</div>
                      <div className="text-white text-sm">{selectedData.metadata.volatility_prob ? (selectedData.metadata.volatility_prob * 100).toFixed(1) + '%' : 'N/A'}</div>
                    </div>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div>
                      <div className="text-xs text-slate-500 mb-1">任务ID</div>
                      <div className="text-white font-mono text-sm">{selectedData.file_id}</div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-500 mb-1">标的代码</div>
                      <div className="text-white text-sm">{selectedData.metadata.symbol || 'N/A'}</div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-500 mb-1">交易环境</div>
                      <div className="text-white text-sm">{selectedData.metadata.mode === 'live' ? '实盘' : '模拟盘'}</div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-500 mb-1">数据点数</div>
                      <div className="text-white text-sm">{selectedData.data_length}</div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-500 mb-1">开始时间</div>
                      <div className="text-white text-sm">{selectedData.metadata.start_time ? new Date(selectedData.metadata.start_time).toLocaleString('zh-CN') : 'N/A'}</div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-500 mb-1">爬取间隔</div>
                      <div className="text-white text-sm">{selectedData.metadata.interval?.value} {selectedData.metadata.interval?.unit === 'seconds' ? '秒' : selectedData.metadata.interval?.unit === 'minutes' ? '分' : '时'}</div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-500 mb-1">盘段</div>
                      <div className="text-white text-sm">{(selectedData.metadata.sessions || []).join('、') || '未限制'}</div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-500 mb-1">时区</div>
                      <div className="text-white text-sm">{selectedData.metadata.timezone || 'America/New_York'}</div>
                    </div>
                  </div>
                )}
              </div>
              
              {/* 图表类型选择 */}
              <div className="bg-gradient-to-br from-slate-800/40 via-slate-800/30 to-slate-900/40 backdrop-blur-xl rounded-3xl p-8 border border-slate-700/30 shadow-2xl shadow-slate-900/50">
                <div className="flex items-center justify-between mb-8">
                  <h3 className="text-2xl font-bold text-white tracking-tight">图表类型</h3>
                </div>
                <div className="flex gap-3 mb-6">
                  <button
                    onClick={() => setChartType('line')}
                    className={`px-6 py-3 rounded-2xl text-sm font-semibold transition-all duration-300 flex items-center gap-3 ${
                      chartType === 'line'
                        ? 'bg-gradient-to-r from-blue-500 to-cyan-600 text-white shadow-sm shadow-blue-500/15 scale-105 border border-blue-400/40'
                        : 'bg-slate-700/60 text-slate-200 hover:text-white hover:bg-slate-700/80 hover:scale-102 backdrop-blur-sm border border-slate-600/50'
                    }`}
                  >
                    <FontAwesomeIcon icon={faChartLine} className="w-5 h-5" />
                    折线图
                  </button>
                  <button
                    onClick={() => setChartType('area')}
                    className={`px-6 py-3 rounded-2xl text-sm font-semibold transition-all duration-300 flex items-center gap-3 ${
                      chartType === 'area'
                        ? 'bg-gradient-to-r from-sky-500 to-blue-600 text-white shadow-sm shadow-sky-500/15 scale-105 border border-sky-400/40'
                        : 'bg-slate-700/60 text-slate-200 hover:text-white hover:bg-slate-700/80 hover:scale-102 backdrop-blur-sm border border-slate-600/50'
                    }`}
                  >
                    <FontAwesomeIcon icon={faChartArea} className="w-5 h-5" />
                    面积图
                  </button>
                  <button
                    onClick={() => setChartType('bar')}
                    className={`px-6 py-3 rounded-2xl text-sm font-semibold transition-all duration-300 flex items-center gap-3 ${
                      chartType === 'bar'
                        ? 'bg-gradient-to-r from-indigo-500 to-cyan-600 text-white shadow-sm shadow-indigo-500/15 scale-105 border border-indigo-400/40'
                        : 'bg-slate-700/60 text-slate-200 hover:text-white hover:bg-slate-700/80 hover:scale-102 backdrop-blur-sm border border-slate-600/50'
                    }`}
                  >
                    <FontAwesomeIcon icon={faChartBar} className="w-5 h-5" />
                    柱状图
                  </button>
                </div>
                <DataChart 
                  data={selectedData} 
                  chartType={chartType}
                />
              </div>
            </div>
            ) : (
            <div className="bg-gradient-to-br from-slate-800/40 via-slate-800/30 to-slate-900/40 backdrop-blur-xl rounded-3xl p-16 border border-slate-700/30 shadow-2xl shadow-slate-900/50 text-center">
              <p className="text-slate-400 text-xl font-medium">请从左侧选择数据文件</p>
            </div>
          )}
        </div>
      </div>

      {/* 删除确认对话框 */}
      {showDeleteConfirm && selectedData && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-gradient-to-br from-slate-800 via-slate-900 to-slate-800 rounded-2xl p-8 border border-slate-700 shadow-2xl max-w-md w-full mx-4">
            <h3 className="text-xl font-bold text-white mb-4">确认删除</h3>
            <p className="text-slate-300 mb-6">
              确定要删除数据文件 <span className="font-mono text-white">{selectedData.file_id}</span> 吗？此操作不可恢复。
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
                  if (selectedData) {
                    deleteMutation.mutate(selectedData.file_id);
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

