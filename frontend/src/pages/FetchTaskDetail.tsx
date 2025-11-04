import { useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faArrowLeft, faPause, faPlay, faStop, faRotateRight } from '@fortawesome/free-solid-svg-icons';
import { fetchApi } from '../services/api';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

export default function FetchTaskDetail() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['fetchTask', taskId],
    queryFn: () => fetchApi.get(taskId!),
    enabled: !!taskId,
    refetchInterval: 5000,
  });

  const pauseMutation = useMutation({
    mutationFn: fetchApi.pause,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['fetchTask', taskId] });
      queryClient.invalidateQueries({ queryKey: ['fetchTasks'] });
      refetch(); // 立即刷新数据
    },
  });

  const resumeMutation = useMutation({
    mutationFn: fetchApi.resume,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['fetchTask', taskId] });
      queryClient.invalidateQueries({ queryKey: ['fetchTasks'] });
      refetch(); // 立即刷新数据
    },
  });

  const stopMutation = useMutation({
    mutationFn: fetchApi.stop,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['fetchTask', taskId] });
      queryClient.invalidateQueries({ queryKey: ['fetchTasks'] });
      refetch(); // 立即刷新数据
    },
  });

  const chartData = useMemo(() => {
    if (!data?.latest_points) return [];
    return data.latest_points.map((p, idx) => {
      // 解析时间戳，支持 "YYYY-MM-DD HH:MM:SS" 格式
      let dateStr = idx.toString();
      if (p.timestamp) {
        try {
          // 尝试解析时间戳
          const date = new Date(p.timestamp.replace(' ', 'T'));
          if (!isNaN(date.getTime())) {
            dateStr = date.toLocaleString('zh-CN', { 
              month: 'short', 
              day: 'numeric', 
              hour: '2-digit', 
              minute: '2-digit' 
            });
          }
        } catch (e) {
          // 如果解析失败，使用原始时间戳
          dateStr = p.timestamp;
        }
      }
      
      return {
        index: idx,
        date: dateStr,
        timestamp: p.timestamp,
        price: p.price ?? null,
      };
    }).filter(d => d.price !== null);
  }, [data]);

  const yDomain = useMemo(() => {
    const values = chartData.map(d => d.price).filter((v: number | null) => typeof v === 'number') as number[];
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
          <p className="text-slate-300 text-sm mb-2">时间: {timestamp}</p>
          {payload.map((entry: any, index: number) => (
            <p key={index} className="text-white text-sm" style={{ color: entry.color }}>
              {entry.name} ($): {entry.value?.toFixed(3) || 'N/A'}
            </p>
          ))}
        </div>
      );
    }
    return null;
  };

  if (isLoading || !data) {
    return <div className="text-slate-300">加载中...</div>;
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/data')}
            className="px-4 py-2 rounded-xl bg-slate-700/60 text-white hover:bg-slate-700/80 flex items-center justify-center"
            title="返回"
          >
            <FontAwesomeIcon icon={faArrowLeft} className="w-4 h-4" />
          </button>
          <div>
            <h1 className="text-3xl font-bold text-white">爬取任务详情</h1>
            <p className="text-slate-400 text-sm mt-1">任务ID：{cfg.task_id}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {cfg.status === 'running' && (
            <button
              onClick={() => pauseMutation.mutate(taskId!)}
              className="px-4 py-2 rounded-xl bg-yellow-600/60 border border-yellow-400/40 text-white hover:bg-yellow-600/80 flex items-center justify-center"
              title="暂停"
            >
              <FontAwesomeIcon icon={faPause} className="w-4 h-4" />
            </button>
          )}
          {cfg.status === 'paused' && (
            <button
              onClick={() => resumeMutation.mutate(taskId!)}
              className="px-4 py-2 rounded-xl bg-emerald-600/60 border border-emerald-400/40 text-white hover:bg-emerald-600/80 flex items-center justify-center"
              title="恢复"
            >
              <FontAwesomeIcon icon={faPlay} className="w-4 h-4" />
            </button>
          )}
          {cfg.status !== 'stopped' && cfg.status !== 'completed' && !cfg.status?.startsWith('error') && (
            <button
              onClick={() => stopMutation.mutate(taskId!)}
              className="px-4 py-2 rounded-xl bg-red-600/60 border border-red-400/40 text-white hover:bg-red-600/80 flex items-center justify-center"
              title="停止"
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

      <div className="bg-gradient-to-br from-slate-800/40 via-slate-800/30 to-slate-900/40 backdrop-blur-xl rounded-3xl p-8 border border-slate-700/30">
        <h2 className="text-xl font-semibold text-white mb-4">基础配置</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div className="text-slate-300">标的：<span className="text-white font-mono">{cfg.symbol}</span></div>
          <div className="text-slate-300">环境：<span className="text-white">{cfg.mode}</span></div>
          <div className="text-slate-300">间隔：<span className="text-white">{cfg.interval?.value} {cfg.interval?.unit}</span></div>
          <div className="text-slate-300">盘段：<span className="text-white">{(cfg.sessions||[]).join('、') || '未限制'}</span></div>
          <div className="text-slate-300">开始时间：<span className="text-white">{cfg.start_time}</span></div>
          <div className="text-slate-300">状态：<span className="text-white">{cfg.status || 'running'}</span></div>
          <div className="text-slate-300">当前交易时段：<span className="text-white">{data.current_session || '未知'}</span></div>
          <div className="text-slate-300">持续时长：<span className="text-white">{durationText}</span></div>
        </div>
      </div>

      <div className="bg-gradient-to-br from-slate-800/40 via-slate-800/30 to-slate-900/40 backdrop-blur-xl rounded-3xl p-8 border border-slate-700/30">
        <h2 className="text-xl font-semibold text-white mb-6">最新价格（最近100条）</h2>
        <ResponsiveContainer width="100%" height={480}>
          <LineChart data={chartData}>
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
            <Line type="monotone" dataKey="price" stroke="#22c55e" dot={false} name="价格" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}


