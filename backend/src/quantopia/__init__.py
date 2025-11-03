"""
Quantopia - 量化交易实验系统后端
"""

__version__ = "0.1.0"
__author__ = "Tank"

from .data_generator import StockDataGenerator
from .strategy import BaseStrategy, MAStrategy, Signal
from .logger import BacktestLogger
from .backtest import Backtest

__all__ = [
    "StockDataGenerator",
    "BaseStrategy",
    "MAStrategy",
    "Signal",
    "BacktestLogger",
    "Backtest",
]

