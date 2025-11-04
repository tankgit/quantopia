"""
日志模块
"""
import os
import json
from datetime import datetime
from typing import Any, Optional


class BacktestLogger:
    """回测日志记录器"""
    
    def __init__(self, logs_dir: str = "logs"):
        """
        初始化日志记录器
        
        Args:
            logs_dir: 日志目录路径
        """
        self.logs_dir = logs_dir
        os.makedirs(logs_dir, exist_ok=True)
        self.current_run_id: Optional[str] = None
        self.log_entries: list[dict] = []
    
    def start_logging(self, run_id: str, backtest_config: dict):
        """
        开始记录日志
        
        Args:
            run_id: 回测运行ID
            backtest_config: 回测配置信息
        """
        self.current_run_id = run_id
        self.log_entries = []
        
        # 记录回测开始信息
        start_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "backtest_start",
            "run_id": run_id,
            "config": backtest_config
        }
        self.log_entries.append(start_entry)
    
    def log_strategy_info(
        self,
        index: int,
        price: float,
        signal: str,
        strategy_info: dict
    ):
        """
        记录策略信息
        
        Args:
            index: 数据索引位置
            price: 当前价格
            signal: 交易信号 (buy/sell/hold)
            strategy_info: 策略相关信息
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "strategy_signal",
            "data_index": index,
            "price": price,
            "signal": signal,
            "strategy_info": strategy_info
        }
        self.log_entries.append(entry)
    
    def log_trade(
        self,
        index: int,
        trade_type: str,
        price: float,
        quantity: float,
        cash_after: float,
        position_after: float,
        trade_info: dict
    ):
        """
        记录交易行为
        
        Args:
            index: 数据索引位置
            trade_type: 交易类型 (buy/sell)
            price: 交易价格
            quantity: 交易数量
            cash_after: 交易后现金
            position_after: 交易后持仓
            trade_info: 交易相关信息
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "trade",
            "data_index": index,
            "trade_type": trade_type,
            "price": price,
            "quantity": quantity,
            "cash_after": cash_after,
            "position_after": position_after,
            "trade_info": trade_info
        }
        self.log_entries.append(entry)
    
    def log_end(self, final_stats: dict):
        """
        记录回测结束信息
        
        Args:
            final_stats: 最终统计数据
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "backtest_end",
            "final_stats": final_stats
        }
        self.log_entries.append(entry)
        
        # 保存日志到文件
        self.save()
    
    def save(self):
        """保存日志到文件"""
        if self.current_run_id is None:
            raise ValueError("No active logging session. Call start_logging first.")
        
        # 确保日志目录存在
        os.makedirs(self.logs_dir, exist_ok=True)
        
        file_path = os.path.join(self.logs_dir, f"{self.current_run_id}.json")
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.log_entries, f, indent=2, ensure_ascii=False)
    
    def load(self, run_id: str) -> list[dict]:
        """
        加载日志文件
        
        Args:
            run_id: 回测运行ID
            
        Returns:
            日志条目列表
        """
        file_path = os.path.join(self.logs_dir, f"{run_id}.json")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Log file not found: {run_id}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def list_all_logs(self) -> list[str]:
        """
        列出所有日志文件ID
        
        Returns:
            日志文件ID列表
        """
        if not os.path.exists(self.logs_dir):
            return []
        
        log_files = []
        for filename in os.listdir(self.logs_dir):
            if filename.endswith('.json'):
                run_id = filename[:-5]  # 移除.json后缀
                log_files.append(run_id)
        
        return log_files
    
    def update_log(self, run_id: str, log_entries: list[dict]):
        """
        更新日志文件
        
        Args:
            run_id: 回测运行ID
            log_entries: 更新后的日志条目列表
        """
        # 确保日志目录存在
        os.makedirs(self.logs_dir, exist_ok=True)
        
        file_path = os.path.join(self.logs_dir, f"{run_id}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(log_entries, f, indent=2, ensure_ascii=False)

