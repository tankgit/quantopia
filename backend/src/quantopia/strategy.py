"""
策略模块
"""
from abc import ABC, abstractmethod
from typing import Literal, Optional
from enum import Enum


class Signal(Enum):
    """交易信号"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class BaseStrategy(ABC):
    """策略基类"""
    
    def __init__(self, name: str, **kwargs):
        """
        初始化策略
        
        Args:
            name: 策略唯一标识名称
            **kwargs: 策略特定参数
        """
        self.name = name
        self.params = kwargs
        self.state = {}  # 策略状态，用于存储中间计算结果
    
    @abstractmethod
    def generate_signal(
        self,
        prices: list[float],
        current_index: int,
        history: list[dict]
    ) -> tuple[Signal, dict]:
        """
        生成交易信号
        
        Args:
            prices: 历史价格列表
            current_index: 当前价格索引
            history: 历史交易记录和状态列表
            
        Returns:
            (signal, info): 信号和相关信息字典
        """
        pass
    
    def get_name(self) -> str:
        """获取策略名称"""
        return self.name
    
    def get_params(self) -> dict:
        """获取策略参数"""
        return self.params
    
    @classmethod
    @abstractmethod
    def get_strategy_info(cls) -> dict:
        """
        获取策略信息（描述、名称等）
        
        Returns:
            包含策略信息的字典，至少包含：
            - name: 策略名称
            - description: 策略描述
        """
        pass
    
    @classmethod
    @abstractmethod
    def get_params_schema(cls) -> dict:
        """
        获取参数schema
        
        Returns:
            参数字典，格式：
            {
                "param_name": {
                    "name": "参数显示名称",
                    "description": "参数描述",
                    "type": "number" | "string" | "boolean",
                    "default": 默认值,
                    "min": 最小值（可选）,
                    "max": 最大值（可选）,
                    "options": [可选值列表]（可选）
                }
            }
        """
        pass


class MAStrategy(BaseStrategy):
    """移动平均策略（MA Strategy）"""
    
    def __init__(
        self,
        name: str = "MA_Strategy",
        short_window: int = 5,
        long_window: int = 20
    ):
        """
        初始化MA策略
        
        Args:
            name: 策略名称
            short_window: 短期移动平均窗口
            long_window: 长期移动平均窗口
        """
        super().__init__(name, short_window=short_window, long_window=long_window)
        self.short_window = short_window
        self.long_window = long_window
    
    def _calculate_ma(self, prices: list[float], window: int, end_index: int) -> float:
        """计算移动平均"""
        if end_index < window - 1:
            return None
        
        start_index = max(0, end_index - window + 1)
        window_prices = prices[start_index:end_index + 1]
        return sum(window_prices) / len(window_prices)
    
    def generate_signal(
        self,
        prices: list[float],
        current_index: int,
        history: list[dict]
    ) -> tuple[Signal, dict]:
        """
        生成交易信号
        
        MA策略逻辑：
        - 当短期MA向上穿越长期MA时，买入
        - 当短期MA向下穿越长期MA时，卖出
        - 其他情况，持有
        """
        # 确保有足够的数据计算MA
        if current_index < self.long_window - 1:
            return Signal.HOLD, {
                "reason": "insufficient_data",
                "short_ma": None,
                "long_ma": None
            }
        
        # 计算短期和长期MA
        short_ma = self._calculate_ma(prices, self.short_window, current_index)
        long_ma = self._calculate_ma(prices, self.long_window, current_index)
        
        if short_ma is None or long_ma is None:
            return Signal.HOLD, {
                "reason": "ma_calculation_failed",
                "short_ma": short_ma,
                "long_ma": long_ma
            }
        
        # 获取上一次的MA值（如果有）
        prev_short_ma = None
        prev_long_ma = None
        
        if current_index > 0 and len(history) > 0:
            last_info = history[-1].get("strategy_info", {})
            prev_short_ma = last_info.get("short_ma")
            prev_long_ma = last_info.get("long_ma")
        
        # 判断信号
        signal = Signal.HOLD
        reason = "no_cross"
        
        if prev_short_ma is not None and prev_long_ma is not None:
            # 检查是否发生穿越
            if prev_short_ma <= prev_long_ma and short_ma > long_ma:
                # 金叉：短期MA向上穿越长期MA
                signal = Signal.BUY
                reason = "golden_cross"
            elif prev_short_ma >= prev_long_ma and short_ma < long_ma:
                # 死叉：短期MA向下穿越长期MA
                signal = Signal.SELL
                reason = "death_cross"
        
        info = {
            "reason": reason,
            "short_ma": round(short_ma, 3),
            "long_ma": round(long_ma, 3),
            "current_price": round(prices[current_index], 3),
            "prev_short_ma": round(prev_short_ma, 3) if prev_short_ma is not None else None,
            "prev_long_ma": round(prev_long_ma, 3) if prev_long_ma is not None else None
        }
        
        return signal, info
    
    @classmethod
    def get_strategy_info(cls) -> dict:
        """获取策略信息"""
        return {
            "name": "MA_Strategy",
            "description": "移动平均策略（Moving Average Strategy）基于短期和长期移动平均线的交叉来产生交易信号。当短期MA向上穿越长期MA时产生买入信号（金叉），当短期MA向下穿越长期MA时产生卖出信号（死叉）。该策略采用全仓交易方式。"
        }
    
    @classmethod
    def get_params_schema(cls) -> dict:
        """获取参数schema"""
        return {
            "short_window": {
                "name": "短期窗口",
                "description": "短期移动平均线的窗口大小（天数）",
                "type": "number",
                "default": 5,
                "min": 2,
                "max": 50
            },
            "long_window": {
                "name": "长期窗口",
                "description": "长期移动平均线的窗口大小（天数）",
                "type": "number",
                "default": 20,
                "min": 5,
                "max": 200
            }
        }


class MultiFactorStrategy(BaseStrategy):
    """
    多因子量化策略
    
    结合多个技术指标：
    - MA（移动平均）：趋势确认
    - RSI（相对强弱指标）：超买超卖判断
    - MACD：动量确认
    - 仓位管理：根据信号强度动态调整仓位
    - 止损止盈：风险控制
    """
    
    def __init__(
        self,
        name: str = "MultiFactor_Strategy",
        short_ma: int = 5,
        long_ma: int = 20,
        rsi_period: int = 14,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0,
        stop_loss_pct: float = 5.0,  # 止损百分比
        take_profit_pct: float = 10.0,  # 止盈百分比
        min_position_ratio: float = 0.3,  # 最小仓位比例
        max_position_ratio: float = 0.8,  # 最大仓位比例
    ):
        """
        初始化多因子策略
        
        Args:
            name: 策略名称
            short_ma: 短期移动平均窗口
            long_ma: 长期移动平均窗口
            rsi_period: RSI计算周期
            macd_fast: MACD快线周期
            macd_slow: MACD慢线周期
            macd_signal: MACD信号线周期
            rsi_oversold: RSI超卖阈值
            rsi_overbought: RSI超买阈值
            stop_loss_pct: 止损百分比
            take_profit_pct: 止盈百分比
            min_position_ratio: 最小仓位比例（0-1）
            max_position_ratio: 最大仓位比例（0-1）
        """
        super().__init__(
            name,
            short_ma=short_ma,
            long_ma=long_ma,
            rsi_period=rsi_period,
            macd_fast=macd_fast,
            macd_slow=macd_slow,
            macd_signal=macd_signal,
            rsi_oversold=rsi_oversold,
            rsi_overbought=rsi_overbought,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            min_position_ratio=min_position_ratio,
            max_position_ratio=max_position_ratio
        )
        self.short_ma = short_ma
        self.long_ma = long_ma
        self.rsi_period = rsi_period
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.min_position_ratio = min_position_ratio
        self.max_position_ratio = max_position_ratio
        
        # 记录持仓成本价（用于止损止盈）
        if "entry_price" not in self.state:
            self.state["entry_price"] = None
    
    def _calculate_ma(self, prices: list[float], window: int, end_index: int) -> Optional[float]:
        """计算移动平均"""
        if end_index < window - 1:
            return None
        
        start_index = max(0, end_index - window + 1)
        window_prices = prices[start_index:end_index + 1]
        return sum(window_prices) / len(window_prices)
    
    def _calculate_ema(self, prices: list[float], period: int, end_index: int) -> Optional[float]:
        """计算指数移动平均（EMA）"""
        if end_index < period - 1:
            return None
        
        start_index = max(0, end_index - period + 1)
        multiplier = 2.0 / (period + 1)
        
        # 从SMA开始
        ema = self._calculate_ma(prices, period, end_index)
        if ema is None:
            return None
        
        # 向前迭代计算EMA
        for i in range(end_index - 1, start_index - 1, -1):
            if i < 0:
                break
            ema = (prices[i] - ema) * multiplier + ema
        
        return ema
    
    def _calculate_rsi(self, prices: list[float], period: int, end_index: int) -> Optional[float]:
        """计算RSI（相对强弱指标）"""
        if end_index < period:
            return None
        
        start_index = max(0, end_index - period)
        price_changes = []
        
        for i in range(start_index + 1, end_index + 1):
            change = prices[i] - prices[i - 1]
            price_changes.append(change)
        
        if len(price_changes) == 0:
            return None
        
        # 计算平均收益和平均亏损
        gains = [max(0, chg) for chg in price_changes]
        losses = [max(0, -chg) for chg in price_changes]
        
        avg_gain = sum(gains) / len(gains)
        avg_loss = sum(losses) / len(losses)
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_macd(self, prices: list[float], current_index: int) -> Optional[dict]:
        """计算MACD指标"""
        if current_index < self.macd_slow - 1:
            return None
        
        # 计算快线和慢线EMA
        fast_ema = self._calculate_ema(prices, self.macd_fast, current_index)
        slow_ema = self._calculate_ema(prices, self.macd_slow, current_index)
        
        if fast_ema is None or slow_ema is None:
            return None
        
        # MACD线 = 快线 - 慢线
        macd_line = fast_ema - slow_ema
        
        # 计算信号线（需要历史MACD值序列）
        signal_line = None
        histogram = None
        
        min_for_signal = self.macd_slow + self.macd_signal - 2
        if current_index >= min_for_signal:
            # 计算历史MACD值序列
            macd_values = []
            for i in range(max(0, current_index - self.macd_signal + 1), current_index + 1):
                fast = self._calculate_ema(prices, self.macd_fast, i)
                slow = self._calculate_ema(prices, self.macd_slow, i)
                if fast is not None and slow is not None:
                    macd_values.append(fast - slow)
            
            # 对MACD值序列计算EMA得到信号线
            if len(macd_values) >= self.macd_signal:
                # 使用MACD值序列计算信号线EMA
                signal_multiplier = 2.0 / (self.macd_signal + 1)
                signal_line = sum(macd_values[:self.macd_signal]) / self.macd_signal  # 从SMA开始
                
                # 向前迭代
                for i in range(self.macd_signal, len(macd_values)):
                    signal_line = (macd_values[i] - signal_line) * signal_multiplier + signal_line
                
                histogram = macd_line - signal_line
        
        return {
            "macd_line": macd_line,
            "signal_line": signal_line,
            "histogram": histogram,
            "fast_ema": fast_ema,
            "slow_ema": slow_ema
        }
    
    def _calculate_signal_strength(
        self,
        ma_signal: int,  # -1, 0, 1 for bearish, neutral, bullish
        rsi: Optional[float],
        macd: Optional[dict],
        current_price: float
    ) -> float:
        """
        计算综合信号强度（0-1之间）
        
        Returns:
            信号强度，用于确定仓位大小
        """
        strength = 0.0
        factor_count = 0
        
        # MA信号强度（权重40%）
        if ma_signal != 0:
            ma_weight = 0.4
            ma_strength = abs(ma_signal)  # 1 for bullish/bearish
            strength += ma_weight * ma_strength
            factor_count += 1
        
        # RSI信号强度（权重30%）
        if rsi is not None:
            rsi_weight = 0.3
            if ma_signal == 1:  # 买入信号时，RSI越低越好（超卖）
                rsi_strength = max(0, (self.rsi_oversold - rsi) / self.rsi_oversold)
            elif ma_signal == -1:  # 卖出信号时，RSI越高越好（超买）
                rsi_strength = max(0, (rsi - self.rsi_overbought) / (100 - self.rsi_overbought))
            else:
                rsi_strength = 0.5  # 中性
            
            strength += rsi_weight * rsi_strength
            factor_count += 1
        
        # MACD信号强度（权重30%）
        if macd is not None and macd.get("histogram") is not None:
            macd_weight = 0.3
            histogram = macd["histogram"]
            
            if ma_signal == 1 and histogram > 0:  # 买入且MACD为正
                macd_strength = min(1.0, abs(histogram) / (current_price * 0.01))  # 归一化
            elif ma_signal == -1 and histogram < 0:  # 卖出且MACD为负
                macd_strength = min(1.0, abs(histogram) / (current_price * 0.01))
            else:
                macd_strength = 0.3
            
            strength += macd_weight * macd_strength
            factor_count += 1
        
        # 归一化到0-1
        if factor_count > 0:
            strength = strength / (0.4 + 0.3 + 0.3)  # 归一化
        else:
            strength = 0.0
        
        return max(0.0, min(1.0, strength))
    
    def _check_stop_loss_take_profit(
        self,
        current_price: float,
        position: float,
        entry_price: Optional[float]
    ) -> Optional[tuple[Signal, str]]:
        """
        检查止损止盈条件
        
        Returns:
            (signal, reason) 如果需要止损止盈，否则None
        """
        if entry_price is None or position == 0:
            return None
        
        price_change_pct = ((current_price - entry_price) / entry_price) * 100
        
        # 止损
        if price_change_pct <= -self.stop_loss_pct:
            return Signal.SELL, f"stop_loss_{abs(price_change_pct):.2f}%"
        
        # 止盈
        if price_change_pct >= self.take_profit_pct:
            return Signal.SELL, f"take_profit_{price_change_pct:.2f}%"
        
        return None
    
    def generate_signal(
        self,
        prices: list[float],
        current_index: int,
        history: list[dict]
    ) -> tuple[Signal, dict]:
        """
        生成交易信号
        
        策略逻辑：
        1. 计算MA、RSI、MACD指标
        2. 综合判断买卖信号
        3. 根据信号强度确定仓位比例
        4. 检查止损止盈条件
        """
        # 最小数据要求
        min_required = max(self.long_ma, self.macd_slow + self.macd_signal, self.rsi_period)
        if current_index < min_required:
            return Signal.HOLD, {
                "reason": "insufficient_data",
                "required": min_required,
                "current": current_index
            }
        
        current_price = prices[current_index]
        
        # 获取当前持仓状态
        current_position = 0.0
        if len(history) > 0:
            last_entry = history[-1]
            current_position = last_entry.get("position", 0.0)
            # 如果当前持仓为0但entry_price还存在，清除它
            if current_position == 0 and self.state.get("entry_price") is not None:
                self.state["entry_price"] = None
        
        # 获取上一次的状态
        prev_short_ma = None
        prev_long_ma = None
        if current_index > 0 and len(history) > 0:
            last_info = history[-1].get("strategy_info", {})
            prev_short_ma = last_info.get("short_ma")
            prev_long_ma = last_info.get("long_ma")
            # 从历史记录中恢复entry_price（如果存在）
            saved_entry_price = last_info.get("entry_price")
            if saved_entry_price is not None:
                self.state["entry_price"] = saved_entry_price
        
        # 计算技术指标
        short_ma = self._calculate_ma(prices, self.short_ma, current_index)
        long_ma = self._calculate_ma(prices, self.long_ma, current_index)
        rsi = self._calculate_rsi(prices, self.rsi_period, current_index)
        macd = self._calculate_macd(prices, current_index)
        
        if short_ma is None or long_ma is None:
            return Signal.HOLD, {
                "reason": "indicator_calculation_failed",
                "short_ma": short_ma,
                "long_ma": long_ma
            }
        
        # 检查止损止盈（优先级最高）
        if current_position > 0 and self.state.get("entry_price") is not None:
            stop_signal = self._check_stop_loss_take_profit(
                current_price,
                current_position,
                self.state["entry_price"]
            )
            if stop_signal:
                signal, reason = stop_signal
                # 止损止盈时全仓卖出，清除entry_price
                entry_price_to_return = self.state["entry_price"]
                self.state["entry_price"] = None
                return signal, {
                    "reason": reason,
                    "short_ma": round(short_ma, 3),
                    "long_ma": round(long_ma, 3),
                    "rsi": round(rsi, 3) if rsi else None,
                    "macd": {
                        "macd_line": round(macd["macd_line"], 3) if macd else None,
                        "histogram": round(macd.get("histogram", 0), 3) if macd and macd.get("histogram") else None
                    } if macd else None,
                    "current_price": round(current_price, 3),
                    "entry_price": round(entry_price_to_return, 3) if entry_price_to_return else None,
                    "position_ratio": 1.0,  # 止损止盈全仓卖出
                    "signal_strength": 1.0
                }
        
        # 判断MA信号
        ma_signal = 0  # -1: 卖出, 0: 中性, 1: 买入
        ma_reason = "no_cross"
        
        if prev_short_ma is not None and prev_long_ma is not None:
            # 检查穿越
            if prev_short_ma <= prev_long_ma and short_ma > long_ma:
                ma_signal = 1
                ma_reason = "golden_cross"
            elif prev_short_ma >= prev_long_ma and short_ma < long_ma:
                ma_signal = -1
                ma_reason = "death_cross"
        
        # 综合判断
        signal = Signal.HOLD
        reason = ma_reason
        position_ratio = 0.0
        
        # 买入逻辑：MA金叉 + RSI不超买 + MACD支持
        if ma_signal == 1 and current_position == 0:
            # RSI检查：不能太超买
            rsi_ok = rsi is None or rsi < self.rsi_overbought
            
            # MACD检查：最好是正值或正在转正
            macd_ok = macd is None or (macd.get("histogram", 0) > -current_price * 0.001)
            
            if rsi_ok and macd_ok:
                signal = Signal.BUY
                reason = f"multi_factor_buy_{ma_reason}"
                
                # 计算信号强度并确定仓位
                signal_strength = self._calculate_signal_strength(1, rsi, macd, current_price)
                position_ratio = self.min_position_ratio + (
                    signal_strength * (self.max_position_ratio - self.min_position_ratio)
                )
                
                # 记录入场价格
                self.state["entry_price"] = current_price
        
        # 卖出逻辑：MA死叉 或 RSI超买 或 MACD转负
        elif ma_signal == -1 and current_position > 0:
            signal = Signal.SELL
            reason = f"multi_factor_sell_{ma_reason}"
            position_ratio = 1.0  # 卖出信号时全仓卖出
            # 如果全仓卖出，清除entry_price
            if position_ratio >= 1.0:
                self.state["entry_price"] = None
        
        # 部分减仓逻辑：持仓中但RSI严重超买
        elif current_position > 0 and rsi is not None and rsi > 80:
            signal = Signal.SELL
            reason = "rsi_extreme_overbought"
            position_ratio = 0.5  # 减仓50%
            # 部分减仓，如果剩余仓位为0，清除entry_price（这里不处理，因为部分卖出后仍有仓位）
        
        # 部分加仓逻辑：已持仓且趋势强化
        elif current_position > 0 and ma_signal == 1:
            # 已有持仓，但信号继续加强，可以考虑加仓
            signal_strength = self._calculate_signal_strength(1, rsi, macd, current_price)
            if signal_strength > 0.7:  # 信号很强
                signal = Signal.BUY
                reason = "add_position_strengthen"
                # 加仓比例较小
                position_ratio = 0.2 * signal_strength
        
        info = {
            "reason": reason,
            "short_ma": round(short_ma, 3),
            "long_ma": round(long_ma, 3),
            "rsi": round(rsi, 3) if rsi else None,
            "macd": {
                "macd_line": round(macd["macd_line"], 3) if macd else None,
                "signal_line": round(macd.get("signal_line", 0), 3) if macd and macd.get("signal_line") else None,
                "histogram": round(macd.get("histogram", 0), 3) if macd and macd.get("histogram") else None
            } if macd else None,
            "current_price": round(current_price, 3),
            "ma_signal": ma_signal,
            "position_ratio": round(position_ratio, 3),
            "signal_strength": round(self._calculate_signal_strength(ma_signal, rsi, macd, current_price), 3),
            "entry_price": round(self.state["entry_price"], 3) if self.state.get("entry_price") else None
        }
        
        return signal, info
    
    @classmethod
    def get_strategy_info(cls) -> dict:
        """获取策略信息"""
        return {
            "name": "MultiFactor_Strategy",
            "description": "多因子量化策略结合了多个技术指标进行综合判断，包括移动平均线（MA）、相对强弱指标（RSI）和MACD指标。策略特点：1）根据信号强度动态调整仓位（30%-80%），而非全仓交易；2）具备止损止盈风险控制机制；3）支持部分加仓和减仓操作；4）综合多个指标提高交易信号的准确性。适用于追求稳健收益和风险控制的量化交易场景。"
        }
    
    @classmethod
    def get_params_schema(cls) -> dict:
        """获取参数schema"""
        return {
            "short_ma": {
                "name": "短期移动平均",
                "description": "短期移动平均线的窗口大小（天数）",
                "type": "number",
                "default": 5,
                "min": 2,
                "max": 50
            },
            "long_ma": {
                "name": "长期移动平均",
                "description": "长期移动平均线的窗口大小（天数）",
                "type": "number",
                "default": 20,
                "min": 5,
                "max": 200
            },
            "rsi_period": {
                "name": "RSI周期",
                "description": "RSI（相对强弱指标）的计算周期（天数）",
                "type": "number",
                "default": 14,
                "min": 5,
                "max": 50
            },
            "macd_fast": {
                "name": "MACD快线周期",
                "description": "MACD快线（EMA）的计算周期",
                "type": "number",
                "default": 12,
                "min": 5,
                "max": 50
            },
            "macd_slow": {
                "name": "MACD慢线周期",
                "description": "MACD慢线（EMA）的计算周期",
                "type": "number",
                "default": 26,
                "min": 10,
                "max": 100
            },
            "macd_signal": {
                "name": "MACD信号线周期",
                "description": "MACD信号线（EMA）的计算周期",
                "type": "number",
                "default": 9,
                "min": 3,
                "max": 20
            },
            "rsi_oversold": {
                "name": "RSI超卖阈值",
                "description": "RSI低于此值视为超卖（买入机会）",
                "type": "number",
                "default": 30.0,
                "min": 10,
                "max": 40
            },
            "rsi_overbought": {
                "name": "RSI超买阈值",
                "description": "RSI高于此值视为超买（卖出机会）",
                "type": "number",
                "default": 70.0,
                "min": 60,
                "max": 90
            },
            "stop_loss_pct": {
                "name": "止损百分比",
                "description": "止损百分比，当亏损达到此比例时自动卖出",
                "type": "number",
                "default": 5.0,
                "min": 1.0,
                "max": 20.0
            },
            "take_profit_pct": {
                "name": "止盈百分比",
                "description": "止盈百分比，当盈利达到此比例时自动卖出",
                "type": "number",
                "default": 10.0,
                "min": 5.0,
                "max": 50.0
            },
            "min_position_ratio": {
                "name": "最小仓位比例",
                "description": "最小仓位比例（0-1之间），信号弱时使用",
                "type": "number",
                "default": 0.3,
                "min": 0.1,
                "max": 0.9
            },
            "max_position_ratio": {
                "name": "最大仓位比例",
                "description": "最大仓位比例（0-1之间），信号强时使用",
                "type": "number",
                "default": 0.8,
                "min": 0.3,
                "max": 1.0
            }
        }

