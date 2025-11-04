import axios from 'axios';
import type {
  DataFile,
  DataFileDetail,
  DataGenerateRequest,
  BacktestCreateRequest,
  BacktestResult,
  BacktestDetail,
  BacktestListItem,
  Strategy,
  FetchTaskCreateRequest,
  FetchTaskSummary,
  FetchTaskDetailResponse,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:15000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 数据相关API
export const dataApi = {
  list: async (): Promise<{ files: DataFile[]; count: number }> => {
    const response = await api.get('/api/data/list');
    return response.data;
  },

  get: async (fileId: string): Promise<DataFileDetail> => {
    const response = await api.get(`/api/data/${fileId}`);
    return response.data;
  },

  generate: async (request: DataGenerateRequest): Promise<{ file_id: string; metadata: DataFile }> => {
    const response = await api.post('/api/data/generate', request);
    return response.data;
  },

  delete: async (fileId: string): Promise<{ message: string }> => {
    const response = await api.delete(`/api/data/${fileId}`);
    return response.data;
  },
};

// 回测相关API
export const backtestApi = {
  list: async (): Promise<{ backtests: BacktestListItem[]; count: number }> => {
    const response = await api.get('/api/backtest/list');
    return response.data;
  },

  get: async (runId: string): Promise<BacktestDetail> => {
    const response = await api.get(`/api/backtest/${runId}`);
    return response.data;
  },

  create: async (request: BacktestCreateRequest): Promise<BacktestResult> => {
    const response = await api.post('/api/backtest/create', request);
    return response.data;
  },

  analyze: async (
    runId: string,
    request: { api_key: string; api_url: string; model_name: string }
  ): Promise<{ message: string; run_id: string }> => {
    const response = await api.post(`/api/backtest/${runId}/analyze`, request);
    return response.data;
  },

  getAnalysisProgress: async (
    runId: string
  ): Promise<{ status: string; progress: number; message: string; total: number; current: number }> => {
    const response = await api.get(`/api/backtest/${runId}/analyze/progress`);
    return response.data;
  },

  stopAnalyze: async (
    runId: string
  ): Promise<{ message: string }> => {
    const response = await api.post(`/api/backtest/${runId}/analyze/stop`);
    return response.data;
  },
};

// 策略相关API
export const strategiesApi = {
  list: async (): Promise<{ strategies: Strategy[]; count: number }> => {
    const response = await api.get('/api/strategies/list');
    return response.data;
  },
};

// 实盘爬取任务 API
export const fetchApi = {
  create: async (request: FetchTaskCreateRequest): Promise<{ task_id: string }> => {
    const response = await api.post('/api/fetch/create', request);
    return response.data;
  },
  list: async (): Promise<{ tasks: FetchTaskSummary[]; count: number }> => {
    const response = await api.get('/api/fetch/list');
    return response.data;
  },
  get: async (taskId: string): Promise<FetchTaskDetailResponse> => {
    const response = await api.get(`/api/fetch/${taskId}`);
    return response.data;
  },
  pause: async (taskId: string): Promise<{ message: string }> => {
    const response = await api.post(`/api/fetch/${taskId}/pause`);
    return response.data;
  },
  resume: async (taskId: string): Promise<{ message: string }> => {
    const response = await api.post(`/api/fetch/${taskId}/resume`);
    return response.data;
  },
  stop: async (taskId: string): Promise<{ message: string }> => {
    const response = await api.post(`/api/fetch/${taskId}/stop`);
    return response.data;
  },
};

export default api;

