"""
示例用法：演示如何使用Quantopia后端
"""
from src.quantopia import StockDataGenerator, MAStrategy, Backtest


def example():
    """示例：生成数据并进行回测"""
    
    # 1. 生成模拟数据
    print("=== 生成模拟数据 ===")
    generator = StockDataGenerator()
    file_id = generator.generate(
        length=100,
        base_mean=100.0,
        trend="up",
        volatility_prob=0.3,
        volatility_scale=0.02
    )
    print(f"生成的数据文件ID: {file_id}")
    
    # 2. 创建策略
    print("\n=== 创建策略 ===")
    strategy = MAStrategy(name="MA_Strategy_Demo", short_window=5, long_window=20)
    print(f"策略名称: {strategy.get_name()}")
    print(f"策略参数: {strategy.get_params()}")
    
    # 3. 运行回测
    print("\n=== 运行回测 ===")
    backtest = Backtest()
    result = backtest.run(
        strategy=strategy,
        data_file_id=file_id,
        initial_cash=100000.0,
        commission_rate=0.001
    )
    
    print(f"回测ID: {result['run_id']}")
    print(f"策略名称: {result['strategy_name']}")
    print(f"最终统计:")
    for key, value in result['stats'].items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    example()

