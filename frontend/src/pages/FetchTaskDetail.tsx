import { useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
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

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['fetchTask', taskId],
    queryFn: () => fetchApi.get(taskId!),
    enabled: !!taskId,
    refetchInterval: 5000,
  });

  const chartData = useMemo(() => {
    if (!data?.latest_points) return [];
    return data.latest_points.map((p, idx) => ({ index: idx, price: p.price ?? null, ts: p.timestamp }));
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

  if (isLoading || !data) {
    return <div className="text-slate-300">加载中...</div>;
  }

  const cfg = data.config || {};
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

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">爬取任务详情</h1>
          <p className="text-slate-400 text-sm mt-1">任务ID：{cfg.task_id}</p>
        </div>
        <button
          onClick={() => refetch()}
          className="px-4 py-2 rounded-xl bg-slate-700/60 border border-slate-600/50 text-white hover:bg-slate-700/80"
        >
          刷新
        </button>
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
            <XAxis dataKey="index" stroke="#94a3b8" />
            <YAxis stroke="#94a3b8" domain={yDomain as any} />
            <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155' }} />
            <Line type="monotone" dataKey="price" stroke="#22c55e" dot={false} name="价格" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}


