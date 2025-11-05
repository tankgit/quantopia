"""
回测模块
"""
import uuid
from typing import Optional
from .data_generator import StockDataGenerator
from .strategy import BaseStrategy, Signal
from .logger import BacktestLogger


class Backtest:
    """回测引擎"""
    
    def __init__(
        self,
        logger: Optional[BacktestLogger] = None,
        data_generator: Optional[StockDataGenerator] = None
    ):
        """
        初始化回测引擎
        
        Args:
            logger: 日志记录器
            data_generator: 数据生成器（用于加载数据）
        """
        self.logger = logger or BacktestLogger()
        self.data_generator = data_generator or StockDataGenerator()
    
    def run(
        self,
        strategy: BaseStrategy,
        data_file_id: str,
        initial_cash: float = 100000.0,
        commission: float = 5.0,
        lot_size: float = 1.0,
        max_pos_ratio: float = 1.0
    ) -> dict:
        """
        运行回测
        
        Args:
            strategy: 交易策略
            data_file_id: 数据文件ID
            initial_cash: 初始资金
            commission: 每笔交易手续费（绝对数值，单位：元）
            lot_size: 最小交易单位（股数）
            max_pos_ratio: 最大持仓比率（0-1之间）
            
        Returns:
            回测结果字典
        """
        # 生成run_id
        run_id = str(uuid.uuid4())[:8]
        
        # 加载数据
        metadata, prices = self.data_generator.load_data(data_file_id)
        
        # 初始化回测状态
        cash = initial_cash
        position = 0.0  # 持仓数量
        history = []  # 历史记录
        
        # 记录回测开始
        backtest_config = {
            "strategy_name": strategy.get_name(),
            "strategy_params": strategy.get_params(),
            "data_file_id": data_file_id,
            "data_metadata": metadata,
            "initial_cash": initial_cash,
            "commission": commission,
            "lot_size": lot_size,
            "max_pos_ratio": max_pos_ratio
        }
        self.logger.start_logging(run_id, backtest_config)
        
        # 回测循环
        for i in range(len(prices)):
            current_price = prices[i]
            
            # 生成信号
            signal, strategy_info = strategy.generate_signal(prices, i, history)
            
            # 记录策略信息
            self.logger.log_strategy_info(
                index=i,
                price=current_price,
                signal=signal.value,
                strategy_info=strategy_info
            )
            
            # 执行交易
            trade_executed = False
            trade_info = {}
            
            # 获取策略信号强度（用于计算交易数量）
            signal_strength = strategy_info.get("signal_strength", 1.0)  # 默认1.0
            signal_strength = max(0.0, min(1.0, signal_strength))  # 限制在0-1之间
            
            # 计算最大可买入数量（基于可用资金和最大持仓比率）
            max_buy_value = cash * max_pos_ratio
            max_buy_quantity_raw = max_buy_value / current_price if current_price > 0 else 0
            
            # 根据信号强度和lot_size计算实际买入数量
            # 信号强度越高，买入数量越多（线性关系）
            desired_quantity = max_buy_quantity_raw * signal_strength
            
            # 向下取整到lot_size的倍数
            if lot_size > 0:
                desired_quantity = (desired_quantity // lot_size) * lot_size
            else:
                desired_quantity = 0
            
            if signal == Signal.BUY and cash > 0 and desired_quantity >= lot_size:
                # 计算实际买入数量（考虑资金限制）
                trade_value = desired_quantity * current_price
                commission_cost = commission  # 固定手续费
                total_cost = trade_value + commission_cost
                
                # 如果资金不足，减少买入数量
                if cash < total_cost:
                    # 反向计算：可用资金能买多少（考虑手续费）
                    available_cash = cash - commission_cost  # 扣除手续费后的可用资金
                    if available_cash > 0 and current_price > 0:
                        max_affordable_quantity = available_cash / current_price
                    else:
                        max_affordable_quantity = 0
                    
                    # 向下取整到lot_size的倍数
                    if lot_size > 0:
                        max_affordable_quantity = (max_affordable_quantity // lot_size) * lot_size
                    else:
                        max_affordable_quantity = 0
                    
                    desired_quantity = min(desired_quantity, max_affordable_quantity)
                    trade_value = desired_quantity * current_price
                    total_cost = trade_value + commission_cost
                
                # 执行买入
                if desired_quantity >= lot_size and cash >= total_cost:
                    cash -= total_cost
                    position += desired_quantity
                    trade_executed = True
                    trade_info = {
                        "signal_reason": strategy_info.get("reason", ""),
                        "quantity": round(desired_quantity, 3),
                        "commission": round(commission_cost, 3),
                        "signal_strength": round(signal_strength, 3),
                        "lot_size": lot_size,
                        "max_pos_ratio": max_pos_ratio
                    }
                    
                    self.logger.log_trade(
                        index=i,
                        trade_type="buy",
                        price=current_price,
                        quantity=round(desired_quantity, 3),
                        cash_after=round(cash, 3),
                        position_after=round(position, 3),
                        trade_info=trade_info
                    )
            
            elif signal == Signal.SELL and position > 0:
                # 卖出逻辑：根据信号强度决定卖出比例
                # 信号强度越高，卖出比例越大
                sell_ratio = signal_strength
                sell_ratio = max(0.0, min(1.0, sell_ratio))  # 限制在0-1之间
                
                desired_sell_quantity = position * sell_ratio
                
                # 向下取整到lot_size的倍数
                if lot_size > 0:
                    desired_sell_quantity = (desired_sell_quantity // lot_size) * lot_size
                else:
                    desired_sell_quantity = 0
                
                # 不能超过持仓
                desired_sell_quantity = min(desired_sell_quantity, position)
                
                if desired_sell_quantity >= lot_size:
                    trade_value = desired_sell_quantity * current_price
                    commission_cost = commission  # 固定手续费
                    cash += trade_value - commission_cost
                    
                    position -= desired_sell_quantity
                    trade_executed = True
                    trade_info = {
                        "signal_reason": strategy_info.get("reason", ""),
                        "quantity": round(desired_sell_quantity, 3),
                        "commission": round(commission_cost, 3),
                        "signal_strength": round(signal_strength, 3),
                        "sell_ratio": round(sell_ratio, 3),
                        "lot_size": lot_size
                    }
                    
                    self.logger.log_trade(
                        index=i,
                        trade_type="sell",
                        price=current_price,
                        quantity=round(desired_sell_quantity, 3),
                        cash_after=round(cash, 3),
                        position_after=round(position, 3),
                        trade_info=trade_info
                    )
            
            # 更新历史记录
            history_entry = {
                "index": i,
                "price": current_price,
                "signal": signal.value,
                "strategy_info": strategy_info,
                "cash": round(cash, 3),
                "position": round(position, 3),
                "trade_executed": trade_executed
            }
            history.append(history_entry)
        
        # 计算最终收益（平仓）
        final_price = prices[-1]
        final_value = cash + position * final_price
        total_return = final_value - initial_cash
        total_return_pct = (total_return / initial_cash) * 100 if initial_cash > 0 else 0
        
        # 计算统计数据
        stats = self._calculate_statistics(prices, history, initial_cash, final_value, total_return)
        
        # 记录回测结束
        final_stats = {
            "run_id": run_id,
            "final_cash": round(cash, 3),
            "final_position": round(position, 3),
            "final_value": round(final_value, 3),
            "initial_cash": initial_cash,
            "total_return": round(total_return, 3),
            "total_return_pct": round(total_return_pct, 3),
            "final_price": round(final_price, 3),
            **stats
        }
        self.logger.log_end(final_stats)
        
        # 返回结果
        return {
            "run_id": run_id,
            "strategy_name": strategy.get_name(),
            "data_file_id": data_file_id,
            "stats": final_stats,
            "history_length": len(history)
        }
    
    def _calculate_statistics(
        self,
        prices: list[float],
        history: list[dict],
        initial_cash: float,
        final_value: float,
        total_return: float
    ) -> dict:
        """
        计算回测统计数据
        
        Args:
            prices: 价格列表
            history: 历史记录
            initial_cash: 初始资金
            final_value: 最终价值
            total_return: 总收益
            
        Returns:
            统计数据字典
        """
        # 计算买卖次数
        buy_count = sum(1 for h in history if h.get("signal") == "buy" and h.get("trade_executed"))
        sell_count = sum(1 for h in history if h.get("signal") == "sell" and h.get("trade_executed"))
        
        # 计算最大回撤
        portfolio_values = []
        returns = []  # 每期收益率
        for h in history:
            current_value = h["cash"] + h["position"] * h["price"]
            portfolio_values.append(current_value)
        
        # 计算每期收益率
        for i in range(1, len(portfolio_values)):
            if portfolio_values[i-1] > 0:
                period_return = (portfolio_values[i] - portfolio_values[i-1]) / portfolio_values[i-1]
                returns.append(period_return)
        
        if portfolio_values:
            peak = portfolio_values[0]
            max_drawdown = 0.0
            max_drawdown_pct = 0.0
            
            for value in portfolio_values:
                if value > peak:
                    peak = value
                drawdown = peak - value
                drawdown_pct = (drawdown / peak) * 100 if peak > 0 else 0
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
                if drawdown_pct > max_drawdown_pct:
                    max_drawdown_pct = drawdown_pct
        else:
            max_drawdown = 0.0
            max_drawdown_pct = 0.0
        
        # 计算价格统计
        if prices:
            price_change = prices[-1] - prices[0]
            price_change_pct = (price_change / prices[0]) * 100 if prices[0] > 0 else 0
            max_price = max(prices)
            min_price = min(prices)
        else:
            price_change = 0.0
            price_change_pct = 0.0
            max_price = 0.0
            min_price = 0.0
        
        # 计算交易胜率（盈利交易数 / 总交易对数）
        trade_pairs = []
        buy_price = None
        for h in history:
            if h.get("signal") == "buy" and h.get("trade_executed"):
                buy_price = h["price"]
            elif h.get("signal") == "sell" and h.get("trade_executed") and buy_price is not None:
                trade_pairs.append({
                    "buy_price": buy_price,
                    "sell_price": h["price"],
                    "profit": h["price"] - buy_price,
                    "profit_pct": ((h["price"] - buy_price) / buy_price * 100) if buy_price > 0 else 0
                })
                buy_price = None
        
        winning_trades = sum(1 for tp in trade_pairs if tp["profit"] > 0)
        losing_trades = sum(1 for tp in trade_pairs if tp["profit"] < 0)
        win_rate = (winning_trades / len(trade_pairs) * 100) if len(trade_pairs) > 0 else 0.0
        
        # 计算盈亏比（平均盈利 / 平均亏损）
        if losing_trades > 0:
            avg_win = sum(tp["profit"] for tp in trade_pairs if tp["profit"] > 0) / winning_trades if winning_trades > 0 else 0.0
            avg_loss = abs(sum(tp["profit"] for tp in trade_pairs if tp["profit"] < 0) / losing_trades)
            profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0.0
        else:
            avg_win = sum(tp["profit"] for tp in trade_pairs if tp["profit"] > 0) / winning_trades if winning_trades > 0 else 0.0
            avg_loss = 0.0
            profit_loss_ratio = float('inf') if avg_win > 0 else 0.0
        
        # 计算夏普比率（假设无风险利率为0）
        if returns:
            mean_return = sum(returns) / len(returns)
            variance = sum((r - mean_return) ** 2 for r in returns) / len(returns) if len(returns) > 1 else 0
            std_dev = variance ** 0.5
            sharpe_ratio = (mean_return / std_dev) * (252 ** 0.5) if std_dev > 0 else 0.0  # 年化
        else:
            sharpe_ratio = 0.0
        
        # 计算平均持仓时间（数据点数）
        avg_holding_period = len(prices) / len(trade_pairs) if len(trade_pairs) > 0 else 0.0
        
        return {
            "buy_count": buy_count,
            "sell_count": sell_count,
            "total_trades": buy_count + sell_count,
            "max_drawdown": round(max_drawdown, 3),
            "max_drawdown_pct": round(max_drawdown_pct, 3),
            "price_change": round(price_change, 3),
            "price_change_pct": round(price_change_pct, 3),
            "max_price": round(max_price, 3),
            "min_price": round(min_price, 3),
            "initial_price": round(prices[0], 3) if prices else 0.0,
            "final_price": round(prices[-1], 3) if prices else 0.0,
            # 新增指标
            "win_rate": round(win_rate, 2),  # 胜率 (%)
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "profit_loss_ratio": round(profit_loss_ratio, 3) if profit_loss_ratio != float('inf') else 999.999,  # 盈亏比
            "sharpe_ratio": round(sharpe_ratio, 3),  # 夏普比率
            "avg_holding_period": round(avg_holding_period, 1),  # 平均持仓周期（数据点）
            "total_trade_pairs": len(trade_pairs),  # 交易对数量
        }

