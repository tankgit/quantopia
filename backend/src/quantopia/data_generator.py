"""
股票数据生成模块
"""
import uuid
import os
from typing import Optional, Literal
from datetime import datetime
import json


class StockDataGenerator:
    """股票数据生成器"""
    
    def __init__(
        self,
        output_dir: str = "stock_data/generate"
    ):
        """
        初始化数据生成器
        
        Args:
            output_dir: 输出目录路径
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def generate(
        self,
        length: int = 100,
        base_mean: float = 100.0,
        trend: Literal["up", "stable", "down"] = "stable",
        start_price: Optional[float] = None,
        end_price: Optional[float] = None,
        volatility_prob: float = 0.3,
        volatility_scale: float = 0.02,
        seed: Optional[int] = None
    ) -> str:
        """
        生成模拟股票数据
        
        Args:
            length: 数据长度（天数）
            base_mean: 整体围绕的均值
            trend: 整体趋势 ("up"上升, "stable"平稳, "down"下降)
            start_price: 起始股价（可选）
            end_price: 最终股价（可选）
            volatility_prob: 不稳定波动的概率（0-1）
            volatility_scale: 波动幅度大小（概率参数，控制波动标准差）
            seed: 随机种子（可选）
            
        Returns:
            生成的文件ID（8位uuid）
        """
        import numpy as np
        
        if seed is not None:
            np.random.seed(seed)
        
        # 生成8位uuid作为文件标识符
        file_id = str(uuid.uuid4())[:8]
        
        # 确定起始和结束价格
        if start_price is None:
            start_price = base_mean * (1 + np.random.normal(0, 0.1))
        if end_price is None:
            if trend == "up":
                end_price = start_price * (1 + np.random.uniform(0.05, 0.3))
            elif trend == "down":
                end_price = start_price * (1 - np.random.uniform(0.05, 0.3))
            else:  # stable
                end_price = start_price * (1 + np.random.uniform(-0.05, 0.05))
        
        # 生成基础趋势线（线性插值）
        trend_line = np.linspace(start_price, end_price, length)
        
        # 生成随机波动
        prices = []
        current_price = start_price
        
        for i in range(length):
            # 基础趋势点
            trend_target = trend_line[i]
            
            # 决定是否出现不稳定波动
            is_volatile = np.random.random() < volatility_prob
            
            if is_volatile:
                # 不稳定波动：较大的随机变化
                volatility = np.random.normal(0, volatility_scale * base_mean * (1 + np.random.random()))
                change_pct = volatility / current_price
            else:
                # 正常波动：较小的随机变化
                normal_volatility = volatility_scale * 0.3 * base_mean
                volatility = np.random.normal(0, normal_volatility)
                change_pct = volatility / current_price
            
            # 向趋势目标调整，加上波动
            drift = (trend_target - current_price) / (length - i) if i < length - 1 else 0
            current_price = current_price + drift + volatility
            
            # 确保价格为正
            current_price = max(0.01, current_price)
            prices.append(round(current_price, 3))
        
        # 构建metadata
        metadata = {
            "file_id": file_id,
            "length": length,
            "base_mean": round(base_mean, 3),
            "trend": trend,
            "start_price": round(start_price, 3),
            "end_price": round(end_price, 3),
            "volatility_prob": round(volatility_prob, 3),
            "volatility_scale": round(volatility_scale, 3),
            "generated_at": datetime.now().isoformat(),
            "seed": seed
        }
        
        # 保存数据
        file_path = os.path.join(self.output_dir, f"{file_id}.txt")
        with open(file_path, 'w', encoding='utf-8') as f:
            # 第一行：metadata（JSON格式）
            f.write(json.dumps(metadata, ensure_ascii=False) + "\n")
            # 后续行：每行一个数据点，格式：,,价格（时间栏和交易时段为空）
            for price in prices:
                f.write(f",,{price}\n")
        
        return file_id
    
    def load_data(self, file_id: str):
        """
        加载数据文件（生成的数据或爬取的实盘数据）
        
        Args:
            file_id: 文件ID
            
        Returns:
            (metadata, prices): 元数据字典和价格列表
        """
        # 先尝试从生成数据目录加载
        file_path = os.path.join(self.output_dir, f"{file_id}.txt")
        if not os.path.exists(file_path):
            # 如果生成数据目录不存在，尝试从爬取数据目录加载
            fetch_dir = os.path.join("stock_data", "fetch")
            fetch_path = os.path.join(fetch_dir, f"{file_id}.txt")
            if os.path.exists(fetch_path):
                file_path = fetch_path
            else:
                raise FileNotFoundError(f"Data file not found: {file_id}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 第一行是metadata
        metadata = json.loads(lines[0].strip())
        
        # 解析数据点
        prices = []
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split(",", 2)
            if len(parts) < 3:
                # 兼容旧格式：如果只有一行逗号分隔的数据
                if len(parts) == 1 and parts[0]:
                    # 可能是旧格式：一行包含多个价格
                    prices.extend([float(x) for x in parts[0].split(",") if x.strip()])
                    break
                continue
            # 新格式：,,价格 或 时间,交易时段,价格
            price_str = parts[2].strip()
            if price_str:
                try:
                    prices.append(float(price_str))
                except ValueError:
                    continue
        
        return metadata, prices
    
    def list_all_data_files(self) -> list[dict]:
        """
        列出所有生成的数据文件
        
        Returns:
            数据文件信息列表
        """
        files = []
        if not os.path.exists(self.output_dir):
            return files
        
        for filename in os.listdir(self.output_dir):
            if filename.endswith('.txt'):
                file_id = filename[:-4]  # 移除.txt后缀
                try:
                    metadata, _ = self.load_data(file_id)
                    files.append(metadata)
                except Exception:
                    continue
        
        return files

