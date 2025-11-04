import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from './components/Layout';
import DataManagement from './pages/DataManagement';
import Strategies from './pages/Strategies';
import BacktestManagement from './pages/BacktestManagement';
import BacktestDetail from './pages/BacktestDetail';
import FetchTaskDetail from './pages/FetchTaskDetail';
import TradeManagement from './pages/TradeManagement';
import TradeTaskDetail from './pages/TradeTaskDetail';
import AccountManagement from './pages/AccountManagement';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Navigate to="/data" replace />} />
            <Route path="/data" element={<DataManagement />} />
            <Route path="/data/fetch/:taskId" element={<FetchTaskDetail />} />
            <Route path="/strategies" element={<Strategies />} />
            <Route path="/backtests" element={<BacktestManagement />} />
            <Route path="/backtests/:runId" element={<BacktestDetail />} />
            <Route path="/trades" element={<TradeManagement />} />
            <Route path="/trades/:taskId" element={<TradeTaskDetail />} />
            <Route path="/account" element={<AccountManagement />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
