import type { ReactNode } from 'react';
import { NavLink } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faChartLine, faLightbulb, faHistory, faExchangeAlt, faWallet } from '@fortawesome/free-solid-svg-icons';

interface LayoutProps {
  children: ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const navItems = [
    { path: '/data', label: '数据管理', icon: faChartLine, theme: 'blue' },
    { path: '/strategies', label: '策略库', icon: faLightbulb, theme: 'red' },
    { path: '/backtests', label: '回测管理', icon: faHistory, theme: 'purple' },
    { path: '/trades', label: '实时交易', icon: faExchangeAlt, theme: 'green' },
    { path: '/account', label: '我的资产', icon: faWallet, theme: 'cyan' },
  ];

  const getActiveClasses = (theme: string, isActive: boolean) => {
    if (!isActive) {
      return 'text-slate-300 hover:text-white hover:bg-slate-800/80 hover:backdrop-blur-sm hover:scale-102 hover:border hover:border-slate-600/50';
    }
    
    switch (theme) {
      case 'blue':
        return 'bg-gradient-to-r from-blue-500 to-cyan-600 text-white shadow-sm shadow-blue-500/20 scale-105 border border-blue-400/40';
      case 'red':
        return 'bg-gradient-to-r from-red-500 to-rose-600 text-white shadow-sm shadow-red-500/20 scale-105 border border-red-400/40';
      case 'purple':
        return 'bg-gradient-to-r from-purple-500 to-violet-600 text-white shadow-sm shadow-purple-500/20 scale-105 border border-purple-400/40';
      case 'green':
        return 'bg-gradient-to-r from-orange-500 to-amber-600 text-white shadow-sm shadow-orange-500/20 scale-105 border border-orange-400/40';
      case 'cyan':
        return 'bg-gradient-to-r from-cyan-500 to-teal-600 text-white shadow-sm shadow-cyan-500/20 scale-105 border border-cyan-400/40';
      default:
        return 'bg-gradient-to-r from-blue-500 to-indigo-600 text-white shadow-sm shadow-blue-500/20 scale-105 border border-blue-400/40';
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* 顶部导航栏 */}
      <nav className="bg-slate-900/90 backdrop-blur-xl border-b border-slate-800/50 sticky top-0 z-50 shadow-lg shadow-slate-900/20">
        <div className="max-w-7xl mx-auto px-6 lg:px-8">
          <div className="flex items-center justify-between h-20">
            <div className="flex items-center space-x-4">
              <div className="text-3xl font-bold bg-gradient-to-r from-cyan-400 via-blue-500 to-indigo-500 bg-clip-text text-transparent tracking-tight drop-shadow-lg">
                Quantopia
              </div>
              <span className="text-xs text-slate-500 font-medium tracking-wide">量化交易实验系统</span>
            </div>
            <div className="flex gap-3">
              {navItems.map((item) => (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={({ isActive }) =>
                    `px-6 py-3 rounded-2xl text-sm font-semibold transition-all duration-300 flex items-center gap-3 ${getActiveClasses(item.theme, isActive)}`
                  }
                >
                  <FontAwesomeIcon icon={item.icon} className="w-4 h-4" />
                  {item.label}
                </NavLink>
              ))}
            </div>
          </div>
        </div>
      </nav>

      {/* 主内容区域 */}
      <main className="max-w-7xl mx-auto px-6 lg:px-8 py-10">
        {children}
      </main>
    </div>
  );
}

