import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faLightbulb, faInfoCircle, faSpinner } from '@fortawesome/free-solid-svg-icons';
import { useStrategies } from '../services/strategies';

export default function Strategies() {
  const { data: strategies, isLoading, error } = useStrategies();

  if (isLoading) {
    return (
      <div className="space-y-8">
        <div>
          <h1 className="text-4xl font-bold text-white mb-2">策略库</h1>
          <p className="text-slate-400 text-sm">查看和管理可用的交易策略</p>
        </div>
        <div className="flex items-center justify-center py-20">
          <FontAwesomeIcon icon={faSpinner} className="w-8 h-8 text-red-500 animate-spin" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-8">
        <div>
          <h1 className="text-4xl font-bold text-white mb-2">策略库</h1>
          <p className="text-slate-400 text-sm">查看和管理可用的交易策略</p>
        </div>
        <div className="bg-red-500/10 border border-red-500/50 rounded-xl p-6 text-red-400">
          加载策略失败，请稍后重试
        </div>
      </div>
    );
  }

  if (!strategies || strategies.length === 0) {
    return (
      <div className="space-y-8">
        <div>
          <h1 className="text-4xl font-bold text-white mb-2">策略库</h1>
          <p className="text-slate-400 text-sm">查看和管理可用的交易策略</p>
        </div>
        <div className="bg-slate-800/40 rounded-xl p-6 text-slate-400">
          暂无可用策略
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-4xl font-bold text-white mb-2">策略库</h1>
        <p className="text-slate-400 text-sm">查看和管理可用的交易策略</p>
      </div>
      
      <div className="grid gap-6">
        {strategies.map((strategy, index) => (
          <div 
            key={strategy.name} 
            className="bg-gradient-to-br from-slate-800/40 via-slate-800/30 to-slate-900/40 backdrop-blur-xl rounded-3xl p-8 border border-slate-700/30 shadow-2xl shadow-slate-900/50 hover:shadow-red-500/10 transition-all duration-300"
            style={{ 
              animationDelay: `${index * 100}ms`,
              animation: 'fadeInUp 0.6s ease-out'
            }}
          >
            <div className="flex items-start justify-between mb-6">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-red-600 to-rose-700 flex items-center justify-center shadow-lg shadow-red-600/30">
                  <FontAwesomeIcon icon={faLightbulb} className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h2 className="text-2xl font-semibold text-white mb-2">{strategy.name}</h2>
                  <p className="text-slate-300 leading-relaxed">{strategy.description}</p>
                </div>
              </div>
            </div>
            
            <div className="mt-8 pt-6 border-t border-slate-800">
              <div className="flex items-center gap-2 mb-6">
                <FontAwesomeIcon icon={faInfoCircle} className="w-5 h-5 text-red-400" />
                <h3 className="text-xl font-semibold text-white">参数说明</h3>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {Object.entries(strategy.params).map(([key, param]: [string, any]) => (
                  <div key={key} className="bg-slate-700/30 backdrop-blur-sm rounded-xl p-6 border border-slate-600/30 hover:border-red-500/50 transition-all duration-300 hover:shadow-lg hover:shadow-red-500/10">
                    <div className="font-medium text-white mb-2">{param.name}</div>
                    <div className="text-sm text-slate-400 mb-3 leading-relaxed">{param.description}</div>
                    <div className="flex items-center gap-4 text-xs text-slate-500">
                      <span>类型: <span className="text-slate-400">{param.type}</span></span>
                      <span>默认: <span className="text-slate-400">{param.default}</span></span>
                      <span>范围: <span className="text-slate-400">{param.min} - {param.max}</span></span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

