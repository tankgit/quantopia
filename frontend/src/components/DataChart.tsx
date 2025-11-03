import { useMemo } from 'react';
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  Legend, 
  ResponsiveContainer,
  ComposedChart,
  Bar,
  Area,
  AreaChart
} from 'recharts';
import type { DataFileDetail, SignalEntry, TradeEntry } from '../types';

interface DataChartProps {
  data: DataFileDetail;
  signals?: SignalEntry[];
  trades?: TradeEntry[];
  chartType?: 'line' | 'area' | 'bar';
}


export default function DataChart({ 
  data, 
  signals, 
  trades, 
  chartType = 'line'
}: DataChartProps) {
  const chartData = useMemo(() => {
    return data.prices.map((price, index) => {
      const point: any = {
        index,
        price: Number(price.toFixed(3)),
      };

      // 添加买卖信号标记
      if (signals) {
        const signal = signals.find(s => s.data_index === index);
        if (signal) {
          point.signal = signal.signal;
          if (signal.signal === 'buy') {
            point.buyMarker = price;
          } else if (signal.signal === 'sell') {
            point.sellMarker = price;
          }
        }
      }

      // 添加交易标记
      if (trades) {
        const trade = trades.find(t => t.data_index === index);
        if (trade) {
          point.trade = trade.trade_type;
          point.tradePrice = trade.price;
        }
      }

      return point;
    });
  }, [data, signals, trades]);

  // 为每个点添加买入/卖出标记
  const enhancedChartData = useMemo(() => {
    if (!trades || trades.length === 0) return chartData;
    const tradeMap = new Map();
    trades.forEach(t => {
      tradeMap.set(t.data_index, t.trade_type);
    });
    return chartData.map((point) => ({
      ...point,
      buyMarker: tradeMap.get(point.index) === 'buy' ? point.price : null,
      sellMarker: tradeMap.get(point.index) === 'sell' ? point.price : null,
    }));
  }, [chartData, trades]);


  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0]?.payload;
      if (data && data.open !== undefined) {
        return (
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-3 shadow-xl">
            <p className="text-slate-300 text-sm mb-2 font-medium">索引: {label}</p>
            <div className="space-y-1">
              <p className="text-white text-sm">
                <span className="text-slate-400">开盘 ($):</span> {data.open.toFixed(3)}
              </p>
              <p className="text-white text-sm">
                <span className="text-slate-400">收盘 ($):</span> {data.close.toFixed(3)}
              </p>
              <p className="text-white text-sm">
                <span className="text-slate-400">最高 ($):</span> {data.high.toFixed(3)}
              </p>
              <p className="text-white text-sm">
                <span className="text-slate-400">最低 ($):</span> {data.low.toFixed(3)}
              </p>
            </div>
          </div>
        );
      }
      return (
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-3 shadow-xl">
          <p className="text-slate-300 text-sm mb-2">索引: {label}</p>
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


  if (chartType === 'area') {
    return (
      <div className="bg-gradient-to-br from-slate-800/40 via-slate-800/30 to-slate-900/40 backdrop-blur-xl rounded-3xl p-8 border border-slate-700/30 shadow-2xl shadow-slate-900/50">
        <h3 className="text-2xl font-semibold text-white mb-6">面积图</h3>
        <ResponsiveContainer width="100%" height={500}>
          <AreaChart data={enhancedChartData}>
            <defs>
              <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.3} />
            <XAxis dataKey="index" stroke="#94a3b8" />
            <YAxis stroke="#94a3b8" />
            <Tooltip content={<CustomTooltip />} />
            <Legend />
            <Area
              type="monotone"
              dataKey="price"
              stroke="#0ea5e9"
              strokeWidth={2}
              fillOpacity={1}
              fill="url(#colorPrice)"
              name="价格"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (chartType === 'bar') {
    return (
      <div className="bg-gradient-to-br from-slate-800/40 via-slate-800/30 to-slate-900/40 backdrop-blur-xl rounded-3xl p-8 border border-slate-700/30 shadow-2xl shadow-slate-900/50">
        <h3 className="text-2xl font-semibold text-white mb-6">柱状图</h3>
        <ResponsiveContainer width="100%" height={500}>
          <ComposedChart data={enhancedChartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.3} />
            <XAxis dataKey="index" stroke="#94a3b8" />
            <YAxis stroke="#94a3b8" />
            <Tooltip content={<CustomTooltip />} />
            <Legend />
            <Bar dataKey="price" fill="#0ea5e9" name="价格" radius={[4, 4, 0, 0]} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    );
  }

  // 默认折线图
  return (
    <div className="bg-gradient-to-br from-slate-800/40 via-slate-800/30 to-slate-900/40 backdrop-blur-xl rounded-3xl p-8 border border-slate-700/30 shadow-2xl shadow-slate-900/50">
      <h3 className="text-2xl font-semibold text-white mb-6">价格走势图</h3>
      <ResponsiveContainer width="100%" height={500}>
        <LineChart data={enhancedChartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.3} />
          <XAxis dataKey="index" stroke="#94a3b8" />
          <YAxis stroke="#94a3b8" />
          <Tooltip content={<CustomTooltip />} />
          <Legend />
          <Line
            type="monotone"
            dataKey="price"
            stroke="#0ea5e9"
            strokeWidth={2.5}
            dot={false}
            name="价格"
          />
          {trades && trades.length > 0 && (
            <>
              <Line
                type="monotone"
                dataKey="buyMarker"
                stroke="#10b981"
                strokeWidth={0}
                dot={{ fill: '#10b981', r: 4, strokeWidth: 1, stroke: '#059669' }}
                name="买入"
                connectNulls={false}
              />
              <Line
                type="monotone"
                dataKey="sellMarker"
                stroke="#ef4444"
                strokeWidth={0}
                dot={{ fill: '#ef4444', r: 4, strokeWidth: 1, stroke: '#dc2626' }}
                name="卖出"
                connectNulls={false}
              />
            </>
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
