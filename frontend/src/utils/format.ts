// 格式化工具函数

export const formatCurrency = (value: number): string => {
  return value.toFixed(2);
};

export const formatPrice = (value: number, decimals: number = 3): string => {
  return value.toFixed(decimals);
};

// 根据涨跌返回颜色类名（红色上涨，绿色下跌）
export const getPriceChangeColor = (change: number): string => {
  if (change > 0) return 'text-red-300'; // 上涨用红色 - 更亮更醒目
  if (change < 0) return 'text-green-300'; // 下跌用绿色 - 更亮更醒目
  return 'text-slate-300';
};

// 根据是否为正值返回颜色类名
export const getValueColor = (value: number, inverse: boolean = false): string => {
  if (inverse) {
    // 反向：正值绿色，负值红色
    return value >= 0 ? 'text-green-300' : 'text-red-300';
  }
  // 正向：正值红色，负值绿色 - 使用更亮的颜色提高对比度
  return value >= 0 ? 'text-red-300' : 'text-green-300';
};

