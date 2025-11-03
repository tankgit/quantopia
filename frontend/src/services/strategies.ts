import { useQuery } from '@tanstack/react-query';
import { strategiesApi } from './api';
import type { Strategy } from '../types';

// 从后端获取策略列表
export const useStrategies = () => {
  return useQuery({
    queryKey: ['strategies'],
    queryFn: async () => {
      const response = await strategiesApi.list();
      return response.strategies;
    },
  });
};

// 获取单个策略（用于兼容旧代码）
export const getStrategy = async (name: string): Promise<Strategy | undefined> => {
  const response = await strategiesApi.list();
  return response.strategies.find(s => s.name === name);
};

