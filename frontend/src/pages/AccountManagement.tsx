import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faSync, faArrowUp, faArrowDown, faEye, faEyeSlash } from '@fortawesome/free-solid-svg-icons';
import { accountApi } from '../services/api';
import { formatCurrency, formatPrice } from '../utils/format';
import type { AccountAssets, Order } from '../types';

type Market = 'US' | 'HK';

export default function AccountManagement() {
  const [selectedMarket, setSelectedMarket] = useState<Market>('US');
  const [mode, setMode] = useState<'paper' | 'live'>('paper');
  const [isAssetsVisible, setIsAssetsVisible] = useState<boolean>(true);

  // 获取资产信息
  const { data: assets, isLoading: assetsLoading, error: assetsError, refetch: refetchAssets } = useQuery({
    queryKey: ['accountAssets', selectedMarket, mode],
    queryFn: () => accountApi.getAssets(selectedMarket, mode),
    refetchInterval: 30000, // 每30秒刷新一次
    onError: (error) => {
      console.error('获取资产信息失败:', error);
    },
    onSuccess: (data) => {
      console.log('资产信息:', data);
    },
  });

  // 获取当日交易记录
  const { data: ordersData, isLoading: ordersLoading, error: ordersError, refetch: refetchOrders } = useQuery({
    queryKey: ['accountTodayOrders', selectedMarket, mode],
    queryFn: () => accountApi.getTodayOrders(selectedMarket, mode),
    refetchInterval: 30000, // 每30秒刷新一次
    onError: (error) => {
      console.error('获取交易记录失败:', error);
    },
    onSuccess: (data) => {
      console.log('交易记录:', data);
    },
  });

  const handleMarketChange = (market: Market) => {
    setSelectedMarket(market);
  };

  const handleRefresh = () => {
    refetchAssets();
    refetchOrders();
  };

  const formatAssetValue = (value: number | undefined, currency: string) => {
    if (!isAssetsVisible) {
      return '****';
    }
    if (value === undefined || value === null) {
      return '0.00';
    }
    return formatCurrency(value);
  };

  const getErrorMessage = (error: any, currentMode: string) => {
    if (!error) return '未知错误';
    
    // 尝试从错误响应中获取详细信息
    const errorMessage = error.response?.data?.detail || error.message || '未知错误';
    
    // 检查是否是凭证相关的错误
    if (errorMessage.includes('凭证') || errorMessage.includes('credential') || errorMessage.includes('未正确配置')) {
      return `账户凭证未正确配置，请检查${currentMode === 'paper' ? '模拟盘' : '实盘'}账户的环境变量配置`;
    }
    
    if (errorMessage.includes('验证失败') || errorMessage.includes('auth') || errorMessage.includes('unauthorized')) {
      return `账户凭证验证失败，请检查${currentMode === 'paper' ? '模拟盘' : '实盘'}账户凭证是否正确`;
    }
    
    if (errorMessage.includes('网络') || errorMessage.includes('network') || errorMessage.includes('connection')) {
      return '网络连接失败，请检查网络连接';
    }
    
    // 如果是HTTP错误，显示友好的信息
    if (error.response?.status === 400) {
      return errorMessage;
    }
    
    if (error.response?.status === 500) {
      return '服务器内部错误，请稍后重试';
    }
    
    // 默认返回原始错误信息（但限制长度）
    return errorMessage.length > 100 ? errorMessage.substring(0, 100) + '...' : errorMessage;
  };

  const formatTime = (timeStr?: string) => {
    if (!timeStr) return '-';
    try {
      const date = new Date(timeStr);
      return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
    } catch {
      return timeStr;
    }
  };

  const getOrderStatusColor = (status?: string) => {
    if (!status) return 'text-slate-300';
    const statusLower = status.toLowerCase();
    if (statusLower.includes('filled') || statusLower.includes('成交')) {
      return 'text-green-400';
    }
    if (statusLower.includes('pending') || statusLower.includes('待') || statusLower.includes('submitted')) {
      return 'text-yellow-400';
    }
    if (statusLower.includes('cancel') || statusLower.includes('取消')) {
      return 'text-red-400';
    }
    return 'text-slate-300';
  };

  const getSideColor = (side?: string) => {
    if (!side) return 'text-slate-300';
    const sideLower = side.toLowerCase();
    if (sideLower === 'buy' || sideLower === '买入') {
      return 'text-red-400';
    }
    if (sideLower === 'sell' || sideLower === '卖出') {
      return 'text-green-400';
    }
    return 'text-slate-300';
  };

  const orders = ordersData?.orders || [];

  return (
    <div className="space-y-6">
      {/* 页面标题和账户切换 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">我的资产</h1>
          <p className="text-slate-400 text-sm">按货币查看您的长桥证券账户资产和交易记录</p>
        </div>
        <div className="flex items-center gap-4">
          {/* 实盘/模拟盘切换 */}
          <div className="flex items-center gap-3 bg-slate-800/50 rounded-xl p-1 border border-slate-700">
            <button
              onClick={() => setMode('paper')}
              className={`px-6 py-2 rounded-lg font-semibold transition-all ${
                mode === 'paper'
                  ? 'bg-gradient-to-r from-purple-500 to-violet-600 text-white shadow-lg shadow-purple-500/30'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              模拟盘
            </button>
            <button
              onClick={() => setMode('live')}
              className={`px-6 py-2 rounded-lg font-semibold transition-all ${
                mode === 'live'
                  ? 'bg-gradient-to-r from-orange-500 to-amber-600 text-white shadow-lg shadow-orange-500/30'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              实盘
            </button>
          </div>
          {/* 货币切换 */}
          <div className="flex items-center gap-3 bg-slate-800/50 rounded-xl p-1 border border-slate-700">
            <button
              onClick={() => handleMarketChange('US')}
              className={`px-6 py-2 rounded-lg font-semibold transition-all ${
                selectedMarket === 'US'
                  ? 'bg-gradient-to-r from-blue-500 to-cyan-600 text-white shadow-lg shadow-blue-500/30'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              USD
            </button>
            <button
              onClick={() => handleMarketChange('HK')}
              className={`px-6 py-2 rounded-lg font-semibold transition-all ${
                selectedMarket === 'HK'
                  ? 'bg-gradient-to-r from-red-500 to-rose-600 text-white shadow-lg shadow-red-500/30'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              HKD
            </button>
          </div>
          <button
            onClick={() => setIsAssetsVisible(!isAssetsVisible)}
            className="px-4 py-2 bg-slate-800/50 hover:bg-slate-700/50 text-slate-300 hover:text-white rounded-lg transition-all border border-slate-700 hover:border-slate-600"
            title={isAssetsVisible ? '隐藏资产' : '显示资产'}
          >
            <FontAwesomeIcon icon={isAssetsVisible ? faEye : faEyeSlash} className="w-5 h-5" />
          </button>
          <button
            onClick={handleRefresh}
            className="px-4 py-2 bg-slate-800/50 hover:bg-slate-700/50 text-slate-300 hover:text-white rounded-lg transition-all border border-slate-700 hover:border-slate-600"
          >
            <FontAwesomeIcon icon={faSync} className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* 错误提示 */}
      {(assetsError || ordersError) && (
        <div className="bg-red-500/20 border border-red-500/50 rounded-xl p-4 text-red-300">
          <div className="font-semibold mb-1">加载失败</div>
          <div className="text-sm space-y-1">
            {assetsError && (
              <div>
                <span className="font-medium">资产信息: </span>
                {getErrorMessage(assetsError, mode)}
              </div>
            )}
            {ordersError && (
              <div>
                <span className="font-medium">交易记录: </span>
                {getErrorMessage(ordersError, mode)}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 资产信息卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/80 backdrop-blur-sm rounded-2xl p-6 border border-slate-700/50 shadow-xl">
          <div className="text-slate-400 text-sm mb-2">总资产</div>
          <div className="text-3xl font-bold text-white mb-1">
            {assetsLoading ? (
              <span className="text-slate-500">加载中...</span>
            ) : assetsError ? (
              <span className="text-red-400">加载失败</span>
            ) : assets ? (
              formatAssetValue(assets.total_asset, assets.currency || (selectedMarket === 'US' ? 'USD' : 'HKD'))
            ) : (
              <span className="text-slate-400">暂无数据</span>
            )}
          </div>
          <div className="text-xs text-slate-500">
            {selectedMarket === 'US' ? 'USD' : 'HKD'} · {mode === 'paper' ? '模拟盘' : '实盘'}
          </div>
        </div>

        <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/80 backdrop-blur-sm rounded-2xl p-6 border border-slate-700/50 shadow-xl">
          <div className="text-slate-400 text-sm mb-2">可用资金</div>
          <div className="text-3xl font-bold text-white mb-1">
            {assetsLoading ? (
              <span className="text-slate-500">加载中...</span>
            ) : assetsError ? (
              <span className="text-red-400">-</span>
            ) : assets ? (
              formatAssetValue(assets.available_cash, assets.currency || (selectedMarket === 'US' ? 'USD' : 'HKD'))
            ) : (
              <span className="text-slate-400">暂无数据</span>
            )}
          </div>
          <div className="text-xs text-slate-500">可交易金额</div>
        </div>

        <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/80 backdrop-blur-sm rounded-2xl p-6 border border-slate-700/50 shadow-xl">
          <div className="text-slate-400 text-sm mb-2">持仓市值</div>
          <div className="text-3xl font-bold text-white mb-1">
            {assetsLoading ? (
              <span className="text-slate-500">加载中...</span>
            ) : assetsError ? (
              <span className="text-red-400">-</span>
            ) : assets ? (
              formatAssetValue(assets.market_value, assets.currency || (selectedMarket === 'US' ? 'USD' : 'HKD'))
            ) : (
              <span className="text-slate-400">暂无数据</span>
            )}
          </div>
          <div className="text-xs text-slate-500">
            {assets ? (isAssetsVisible ? (assets.position_count || 0) : '**') : 0} 只股票
          </div>
        </div>

        <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/80 backdrop-blur-sm rounded-2xl p-6 border border-slate-700/50 shadow-xl">
          <div className="text-slate-400 text-sm mb-2">总现金</div>
          <div className="text-3xl font-bold text-white mb-1">
            {assetsLoading ? (
              <span className="text-slate-500">加载中...</span>
            ) : assetsError ? (
              <span className="text-red-400">-</span>
            ) : assets ? (
              formatAssetValue(assets.total_cash, assets.currency || (selectedMarket === 'US' ? 'USD' : 'HKD'))
            ) : (
              <span className="text-slate-400">暂无数据</span>
            )}
          </div>
          <div className="text-xs text-slate-500">
            冻结: {assets ? (isAssetsVisible ? formatCurrency(assets.frozen_cash || 0) : '****') : '0.00'}
          </div>
        </div>
      </div>

      {/* 当日交易记录 */}
      <div className="bg-slate-800/50 backdrop-blur-sm rounded-2xl border border-slate-700/50 shadow-xl overflow-hidden">
        <div className="p-6 border-b border-slate-700/50">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold text-white">当日交易记录</h2>
            <div className="text-sm text-slate-400">
              {ordersLoading ? (
                '加载中...'
              ) : (
                `共 ${orders.length} 笔交易`
              )}
            </div>
          </div>
        </div>

        <div className="overflow-x-auto">
          {ordersLoading ? (
            <div className="p-12 text-center text-slate-400">加载中...</div>
          ) : orders.length === 0 ? (
            <div className="p-12 text-center text-slate-400">
              暂无当日交易记录
            </div>
          ) : (
            <table className="w-full">
              <thead className="bg-slate-900/50 border-b border-slate-700/50">
                <tr>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    时间
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    代码
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    方向
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    数量
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    价格
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    成交价
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    状态
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    订单ID
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/30">
                {orders.map((order: Order, index: number) => (
                  <tr
                    key={order.order_id || index}
                    className="hover:bg-slate-800/50 transition-colors"
                  >
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                      {formatTime(order.submitted_at || order.created_at || order.timestamp)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-white">
                      {order.symbol || '-'}
                    </td>
                    <td className={`px-6 py-4 whitespace-nowrap text-sm font-semibold ${getSideColor(order.side)}`}>
                      {order.side ? (
                        <span className="flex items-center gap-1">
                          {order.side.toLowerCase() === 'buy' || order.side === '买入' ? (
                            <FontAwesomeIcon icon={faArrowUp} className="w-3 h-3" />
                          ) : (
                            <FontAwesomeIcon icon={faArrowDown} className="w-3 h-3" />
                          )}
                          {order.side === 'Buy' || order.side === '买入' ? '买入' : 
                           order.side === 'Sell' || order.side === '卖出' ? '卖出' : order.side}
                        </span>
                      ) : (
                        '-'
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                      {order.quantity ? formatPrice(order.quantity, 2) : '-'}
                      {order.filled_quantity && order.filled_quantity !== order.quantity && (
                        <span className="text-slate-500 ml-1">
                          / {formatPrice(order.filled_quantity, 2)}
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                      {order.price ? formatCurrency(order.price) : '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                      {order.executed_price ? formatCurrency(order.executed_price) : '-'}
                    </td>
                    <td className={`px-6 py-4 whitespace-nowrap text-sm font-medium ${getOrderStatusColor(order.status)}`}>
                      {order.status || '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-400 font-mono">
                      {order.order_id ? order.order_id.substring(0, 8) + '...' : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

