"""
API接口模块
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import httpx
import json
import asyncio
import traceback
import sys
from .data_generator import StockDataGenerator
from .strategy import BaseStrategy, MAStrategy, MultiFactorStrategy

# 注册所有可用的策略类
AVAILABLE_STRATEGIES = {
    "MA_Strategy": MAStrategy,
    "MultiFactor_Strategy": MultiFactorStrategy
}
from .backtest import Backtest
from .logger import BacktestLogger
from .longport_client import LongPortService


app = FastAPI(title="Quantopia Backend API", version="0.1.0")

# 添加CORS支持
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite默认端口5173
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic模型定义
class DataGenerateRequest(BaseModel):
    """数据生成请求"""
    length: int = 100
    base_mean: float = 100.0
    trend: str = "stable"  # "up", "stable", "down"
    start_price: Optional[float] = None
    end_price: Optional[float] = None
    volatility_prob: float = 0.3
    volatility_scale: float = 0.02
    seed: Optional[int] = None


class BacktestCreateRequest(BaseModel):
    """创建回测请求"""
    data_file_id: str
    strategy_name: str = "MA_Strategy"
    strategy_params: dict = {}  # MA策略参数：short_window, long_window
    initial_cash: float = 100000.0
    commission_rate: float = 0.001


class BacktestResult(BaseModel):
    """回测结果"""
    run_id: str
    strategy_name: str
    data_file_id: str
    stats: dict
    history_length: int


class AIAnalysisRequest(BaseModel):
    """AI分析请求"""
    api_key: str
    api_url: str
    model_name: str


# 长桥下单请求模型
class LongPortOrderRequest(BaseModel):
    symbol: str = Field(..., description="如 AAPL.US 或 700.HK")
    side: str = Field(..., description="Buy 或 Sell，区分大小写按SDK要求")
    quantity: float = Field(..., gt=0)
    mode: str = Field("paper", description="paper 或 live")
    order_type: str = Field("Limit", description="Limit/Market/... 依SDK支持")
    price: Optional[float] = None
    time_in_force: Optional[str] = None
    remark: Optional[str] = None
    # 允许透传其他字段给SDK
    extra: Dict[str, object] = Field(default_factory=dict)


# 初始化全局组件
data_generator = StockDataGenerator()
backtest_engine = Backtest(logger=BacktestLogger(), data_generator=data_generator)
logger = BacktestLogger()
longport_service = LongPortService()

# 存储AI分析任务进度 {run_id: {"status": "running"/"completed"/"error"/"cancelled", "progress": 0-100, "message": "", "total": 0, "current": 0}}
analysis_progress: Dict[str, Dict] = {}
# 存储异步任务句柄，支持取消
analysis_tasks: Dict[str, asyncio.Task] = {}
# 统一错误格式化，包含文件和行号
def _format_error(err: Exception) -> str:
    try:
        exc_type, exc_value, exc_tb = sys.exc_info()
        if exc_tb is None:
            return f"{type(err).__name__}: {err}"
        tb_list = traceback.extract_tb(exc_tb)
        if not tb_list:
            return f"{type(err).__name__}: {err}"
        last = tb_list[-1]
        return f"{type(err).__name__}: {err} @ {last.filename}:{last.lineno} in {last.name}"
    except Exception:
        return str(err)



# API端点
@app.get("/")
async def root():
    """根端点"""
    return {"message": "Quantopia Backend API", "version": "0.1.0"}


@app.post("/api/data/generate")
async def generate_data(request: DataGenerateRequest):
    """
    生成模拟股票数据
    
    Returns:
        生成的文件ID和元数据
    """
    try:
        file_id = data_generator.generate(
            length=request.length,
            base_mean=request.base_mean,
            trend=request.trend,
            start_price=request.start_price,
            end_price=request.end_price,
            volatility_prob=request.volatility_prob,
            volatility_scale=request.volatility_scale,
            seed=request.seed
        )
        
        metadata, _ = data_generator.load_data(file_id)
        return {"file_id": file_id, "metadata": metadata}
    except Exception as e:
        raise HTTPException(status_code=500, detail=_format_error(e))


@app.get("/api/strategies/list")
async def list_strategies():
    """
    获取所有可用策略列表
    
    Returns:
        策略列表，包含每个策略的详细信息（名称、描述、参数schema）
    """
    try:
        strategies = []
        for strategy_name, strategy_class in AVAILABLE_STRATEGIES.items():
            info = strategy_class.get_strategy_info()
            params_schema = strategy_class.get_params_schema()
            
            strategies.append({
                "name": info["name"],
                "description": info["description"],
                "params": params_schema
            })
        
        return {"strategies": strategies, "count": len(strategies)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=_format_error(e))


@app.get("/api/data/list")
async def list_data_files():
    """
    获取所有数据列表（包括生成的数据和爬取的实盘数据）
    
    Returns:
        数据文件信息列表，每个文件包含 type 字段标识数据类型
    """
    try:
        files = []
        # 生成的数据
        generated_files = data_generator.list_all_data_files()
        for file_info in generated_files:
            file_info["type"] = "generated"
            files.append(file_info)
        
        # 爬取的实盘数据
        if os.path.exists(FETCH_DIR):
            for filename in os.listdir(FETCH_DIR):
                if filename.endswith('.txt'):
                    task_id = filename[:-4]
                    fetch_path = os.path.join(FETCH_DIR, filename)
                    try:
                        with open(fetch_path, "r", encoding="utf-8") as f:
                            first_line = f.readline().strip()
                            if first_line:
                                config = json.loads(first_line)
                                # 统计数据点数量
                                lines = f.readlines()
                                data_count = len([l for l in lines if l.strip()])
                                files.append({
                                    "file_id": task_id,
                                    "type": "fetched",
                                    "symbol": config.get("symbol", ""),
                                    "mode": config.get("mode", ""),
                                    "start_time": config.get("start_time", ""),
                                    "length": data_count,
                                    "generated_at": config.get("start_time", ""),
                                })
                    except Exception:
                        continue
        
        return {"files": files, "count": len(files)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=_format_error(e))


@app.get("/api/data/{file_id}")
async def get_data_file(file_id: str):
    """
    获取某个数据文件（生成的数据或爬取的实盘数据）
    
    Args:
        file_id: 数据文件ID
        
    Returns:
        数据文件信息（元数据和价格数据）
    """
    try:
        # 使用统一的 load_data 方法加载数据
        metadata, prices = data_generator.load_data(file_id)
        
        # 根据 metadata 判断数据类型
        data_type = "fetched" if "symbol" in metadata else "generated"
        
        # 如果是爬取数据，需要解析完整的数据点（包含时间戳和交易时段）
        if data_type == "fetched":
            # 确定文件路径
            gen_path = os.path.join("stock_data", "generate", f"{file_id}.txt")
            fetch_path = os.path.join(FETCH_DIR, f"{file_id}.txt")
            file_path = fetch_path if os.path.exists(fetch_path) else gen_path
            
            points = []
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(",", 2)
                if len(parts) < 3:
                    continue
                timestamp_str = parts[0].strip()
                quote_session = parts[1].strip()
                price_str = parts[2].strip()
                try:
                    price = float(price_str) if price_str else None
                except ValueError:
                    price = None
                points.append({
                    "timestamp": timestamp_str,
                    "quote_session": quote_session,
                    "price": price,
                })
            
            return {
                "file_id": file_id,
                "type": "fetched",
                "metadata": metadata,
                "prices": prices,
                "points": points,
                "data_length": len(points)
            }
        else:
            return {
                "file_id": file_id,
                "type": "generated",
                "metadata": metadata,
                "prices": prices,
                "data_length": len(prices)
            }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Data file not found: {file_id}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=_format_error(e))


@app.delete("/api/data/{file_id}")
async def delete_data_file(file_id: str):
    """
    删除数据文件（生成的数据或爬取的实盘数据）
    
    Args:
        file_id: 数据文件ID
        
    Returns:
        删除成功消息
    """
    try:
        # 尝试加载数据以确定文件类型和路径
        try:
            metadata, _ = data_generator.load_data(file_id)
            data_type = "fetched" if "symbol" in metadata else "generated"
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Data file not found: {file_id}")
        
        # 确定文件路径
        gen_path = os.path.join("stock_data", "generate", f"{file_id}.txt")
        fetch_path = os.path.join(FETCH_DIR, f"{file_id}.txt")
        
        # 删除文件（可能在任一目录）
        deleted = False
        if os.path.exists(fetch_path):
            os.remove(fetch_path)
            deleted = True
        if os.path.exists(gen_path):
            os.remove(gen_path)
            deleted = True
        
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Data file not found: {file_id}")
        
        return {"message": f"Data file {file_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=_format_error(e))


@app.post("/api/backtest/create")
async def create_backtest(request: BacktestCreateRequest):
    """
    提供数据和策略创建一个新的回测
    
    Args:
        request: 回测创建请求
        
    Returns:
        回测结果
    """
    try:
        # 验证数据文件存在
        try:
            data_generator.load_data(request.data_file_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Data file not found: {request.data_file_id}")
        
        # 创建策略
        strategy_class = AVAILABLE_STRATEGIES.get(request.strategy_name)
        if strategy_class is None:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown strategy: {request.strategy_name}"
            )
        
        # 使用策略参数创建策略实例
        strategy = strategy_class(name=request.strategy_name, **request.strategy_params)
        
        # 运行回测
        result = backtest_engine.run(
            strategy=strategy,
            data_file_id=request.data_file_id,
            initial_cash=request.initial_cash,
            commission_rate=request.commission_rate
        )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=_format_error(e))


@app.get("/api/backtest/list")
async def list_backtests():
    """
    获取所有回测列表（包含每个回测的基本信息和统计指标）
    
    Returns:
        回测列表，每个回测包含run_id、stats、data_file_id等关键信息
    """
    try:
        run_ids = logger.list_all_logs()
        backtests = []
        
        for run_id in run_ids:
            try:
                log_entries = logger.load(run_id)
                
                # 提取回测配置和结果
                start_entry = next((e for e in log_entries if e.get("type") == "backtest_start"), None)
                end_entry = next((e for e in log_entries if e.get("type") == "backtest_end"), None)
                
                if start_entry and end_entry:
                    config = start_entry.get("config", {})
                    final_stats = end_entry.get("final_stats", {})
                    
                    # 提取关键信息
                    backtest_info = {
                        "run_id": run_id,
                        "data_file_id": config.get("data_file_id", ""),
                        "strategy_name": config.get("strategy_name", ""),
                        "start_time": start_entry.get("timestamp"),
                        "stats": {
                            "total_return_pct": final_stats.get("total_return_pct", 0.0),
                            "win_rate": final_stats.get("win_rate", 0.0),
                            "total_trades": final_stats.get("total_trades", 0),
                            "total_return": final_stats.get("total_return", 0.0),
                            "final_value": final_stats.get("final_value", 0.0),
                            "max_drawdown_pct": final_stats.get("max_drawdown_pct", 0.0),
                            "buy_count": final_stats.get("buy_count", 0),
                            "sell_count": final_stats.get("sell_count", 0),
                        }
                    }
                    backtests.append(backtest_info)
            except Exception as e:
                # 如果某个回测日志加载失败，跳过它
                continue
        
        return {"backtests": backtests, "count": len(backtests)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/backtest/{run_id}")
async def get_backtest_detail(run_id: str):
    """
    获取某个回测详情
    
    Args:
        run_id: 回测运行ID
        
    Returns:
        回测详情（包括日志）
    """
    try:
        log_entries = logger.load(run_id)
        
        # 解析日志，提取关键信息
        start_entry = next((e for e in log_entries if e.get("type") == "backtest_start"), None)
        end_entry = next((e for e in log_entries if e.get("type") == "backtest_end"), None)
        
        strategy_signals = [e for e in log_entries if e.get("type") == "strategy_signal"]
        trades = [e for e in log_entries if e.get("type") == "trade"]
        
        return {
            "run_id": run_id,
            "config": start_entry.get("config", {}) if start_entry else {},
            "start_time": start_entry.get("timestamp") if start_entry else None,
            "end_time": end_entry.get("timestamp") if end_entry else None,
            "final_stats": end_entry.get("final_stats", {}) if end_entry else {},
            "total_signals": len(strategy_signals),
            "total_trades": len(trades),
            "logs": log_entries,
            "signals": strategy_signals,
            "trades": trades
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Backtest not found: {run_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def call_ai_model(api_url: str, api_key: str, model_name: str, messages: list[dict]) -> str:
    """
    调用AI模型
    
    Args:
        api_url: API地址
        api_key: API密钥
        model_name: 模型名称
        messages: 消息列表
        
    Returns:
        模型返回的文本
    """
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                api_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model_name,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 800
                }
            )
            response.raise_for_status()
            result = response.json()
            
            # 兼容不同的响应格式
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0].get("message", {}).get("content", "")
                if content:
                    return content
            
            # 如果格式不同，尝试其他可能的格式
            if "content" in result:
                return result["content"]
            
            raise ValueError("无法解析AI模型响应")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"AI模型HTTP请求失败: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI模型调用失败: {str(e)}")


async def analyze_backtest_task(run_id: str, request: AIAnalysisRequest):
    """后台任务：执行AI分析"""
    try:
        analysis_progress[run_id] = {
            "status": "running",
            "progress": 0,
            "message": "正在加载回测数据...",
            "total": 0,
            "current": 0
        }
        
        # 加载回测日志
        log_entries = logger.load(run_id)
        
        # 获取回测配置和结果
        start_entry = next((e for e in log_entries if e.get("type") == "backtest_start"), None)
        end_entry = next((e for e in log_entries if e.get("type") == "backtest_end"), None)
        
        if not start_entry or not end_entry:
            analysis_progress[run_id] = {
                "status": "error",
                "progress": 0,
                "message": "回测记录不存在",
                "total": 0,
                "current": 0
            }
            return
        
        config = start_entry.get("config", {})
        final_stats = end_entry.get("final_stats", {})
        data_file_id = config.get("data_file_id")
        
        analysis_progress[run_id]["message"] = "正在加载价格数据..."
        analysis_progress[run_id]["progress"] = 5
        
        # 加载股票价格数据
        _, prices = data_generator.load_data(data_file_id)
        
        analysis_progress[run_id]["message"] = "正在识别失败交易..."
        analysis_progress[run_id]["progress"] = 10
        
        # 获取所有交易
        trades = [e for e in log_entries if e.get("type") == "trade"]
        
        # 配对买入和卖出交易，找出失败的交易
        losing_trades = []
        buy_stack = []  # 使用FIFO来匹配买入卖出，每个元素是 (entry, remaining_quantity)
        
        for trade in trades:
            if trade["trade_type"] == "buy":
                buy_stack.append({
                    "entry": trade,
                    "remaining_quantity": trade["quantity"],
                    "price": trade["price"],
                    "total_commission": trade.get("trade_info", {}).get("commission", 0)
                })
            elif trade["trade_type"] == "sell":
                sell_quantity = trade["quantity"]
                sell_price = trade["price"]
                sell_commission = trade.get("trade_info", {}).get("commission", 0)
                
                # 匹配买入交易，使用FIFO原则
                while sell_quantity > 0 and buy_stack:
                    buy_info = buy_stack[0]
                    matched_quantity = min(sell_quantity, buy_info["remaining_quantity"])
                    
                    # 计算成本（按比例分摊手续费）
                    buy_cost = buy_info["price"] * matched_quantity
                    buy_commission_ratio = matched_quantity / buy_info["entry"]["quantity"]
                    buy_commission = buy_info["total_commission"] * buy_commission_ratio
                    
                    sell_value = sell_price * matched_quantity
                    
                    # 计算盈亏（考虑手续费）
                    profit = sell_value - buy_cost - buy_commission - (sell_commission * (matched_quantity / trade["quantity"]))
                    
                    if profit < 0:  # 亏损交易
                        losing_trades.append({
                            "buy_entry": buy_info["entry"],
                            "sell_entry": trade,
                            "matched_quantity": matched_quantity,
                            "profit": profit,
                            "profit_pct": (profit / (buy_cost + buy_commission)) * 100 if (buy_cost + buy_commission) > 0 else 0
                        })
                    
                    # 更新买入栈
                    buy_info["remaining_quantity"] -= matched_quantity
                    sell_quantity -= matched_quantity
                    
                    # 如果买入全部匹配完，移除
                    if buy_info["remaining_quantity"] <= 0.001:  # 浮点数精度处理
                        buy_stack.pop(0)
        
        if not losing_trades:
            analysis_progress[run_id] = {
                "status": "completed",
                "progress": 100,
                "message": "没有发现失败的交易",
                "total": 0,
                "current": 0
            }
            return
        
        # 构建基础context
        strategy_config = {
            "strategy_name": config.get("strategy_name", ""),
            "strategy_params": config.get("strategy_params", {}),
            "initial_cash": config.get("initial_cash", 0),
            "commission_rate": config.get("commission_rate", 0)
        }
        
        stats_summary = {
            "total_return_pct": final_stats.get("total_return_pct", 0),
            "win_rate": final_stats.get("win_rate", 0),
            "total_trades": final_stats.get("total_trades", 0),
            "max_drawdown_pct": final_stats.get("max_drawdown_pct", 0),
            "winning_trades": final_stats.get("winning_trades", 0),
            "losing_trades": final_stats.get("losing_trades", 0),
            "profit_loss_ratio": final_stats.get("profit_loss_ratio", 0),
            "sharpe_ratio": final_stats.get("sharpe_ratio", 0)
        }
        
        total_tasks = len(losing_trades) + 1  # 失败交易分析 + 整体总结
        analysis_progress[run_id]["total"] = total_tasks
        analysis_progress[run_id]["message"] = f"开始分析 {len(losing_trades)} 笔失败交易..."
        analysis_progress[run_id]["progress"] = 15
        
        previous_summary = None
        
        # 分析每一笔失败交易
        for idx, losing_trade in enumerate(losing_trades):
            analysis_progress[run_id]["current"] = idx + 1
            analysis_progress[run_id]["message"] = f"正在分析第 {idx + 1}/{len(losing_trades)} 笔失败交易..."
            analysis_progress[run_id]["progress"] = 15 + int((idx + 1) / len(losing_trades) * 70)
            
            sell_entry = losing_trade["sell_entry"]
            buy_entry = losing_trade["buy_entry"]
            sell_index = sell_entry["data_index"]
            buy_index = buy_entry["data_index"]
            
            # 提取前后100条数据（注意边界），以卖出点为中心
            start_idx = max(0, sell_index - 100)
            end_idx = min(len(prices), sell_index + 101)
            context_prices = prices[start_idx:end_idx]
            
            # 构建交易上下文
            trade_context = {
                "buy_index": buy_index,
                "buy_price": buy_entry["price"],
                "buy_quantity": buy_entry["quantity"],
                "sell_index": sell_index,
                "sell_price": sell_entry["price"],
                "sell_quantity": sell_entry["quantity"],
                "matched_quantity": losing_trade.get("matched_quantity", sell_entry["quantity"]),
                "profit": losing_trades[idx]["profit"],
                "profit_pct": losing_trades[idx]["profit_pct"],
                "holding_period": sell_index - buy_index,
                "price_data": context_prices,
                "buy_signal_reason": buy_entry.get("trade_info", {}).get("signal_reason", ""),
                "sell_signal_reason": sell_entry.get("trade_info", {}).get("signal_reason", "")
            }
            
            # 构建prompt
            prompt_parts = [
                "你是一个专业的量化交易分析师。请分析以下失败的交易：\n",
                f"策略配置：{json.dumps(strategy_config, ensure_ascii=False, indent=2)}\n",
                f"回测总体指标：{json.dumps(stats_summary, ensure_ascii=False, indent=2)}\n",
                f"交易详情：\n",
                f"- 买入时间点：{trade_context['buy_index']}, 价格：{trade_context['buy_price']:.3f}, 数量：{trade_context['buy_quantity']:.3f}\n",
                f"- 买入信号原因：{trade_context['buy_signal_reason']}\n",
                f"- 卖出时间点：{trade_context['sell_index']}, 价格：{trade_context['sell_price']:.3f}, 数量：{trade_context['sell_quantity']:.3f}\n",
                f"- 卖出信号原因：{trade_context['sell_signal_reason']}\n",
                f"- 持仓周期：{trade_context['holding_period']}个数据点\n",
                f"- 亏损金额：{trade_context['profit']:.3f}, 亏损比例：{trade_context['profit_pct']:.2f}%\n",
                f"- 交易前后100个数据点的价格序列：{json.dumps([round(p, 3) for p in context_prices], ensure_ascii=False)}\n",
            ]
            
            if previous_summary:
                prompt_parts.append(f"\n上一笔失败交易的总结：\n{previous_summary}\n")
            
            prompt_parts.append(
                "\n请简要分析这笔交易失败的原因（几句话即可）：\n"
                "1. 为什么会失败？\n"
                "2. 这是正常的止损还是应该避免的错误？\n"
                "3. 应该如何调整策略？\n"
            )
            
            prompt = "".join(prompt_parts)
            
            # 调用AI模型
            messages = [
                {"role": "system", "content": "你是一个专业的量化交易分析师，擅长分析交易失败原因并提供改进建议。"},
                {"role": "user", "content": prompt}
            ]
            
            summary = await call_ai_model(request.api_url, request.api_key, request.model_name, messages)
            
            # 保存到日志文件（通过timestamp和data_index匹配，确保精确）
            for log_entry in log_entries:
                if (log_entry.get("type") == "trade" 
                    and log_entry.get("timestamp") == sell_entry["timestamp"]
                    and log_entry.get("data_index") == sell_entry["data_index"]
                    and log_entry.get("trade_type") == "sell"):
                    log_entry["summary"] = summary
                    break
            
            previous_summary = summary
        
        # 生成整体总结
        analysis_progress[run_id]["current"] = total_tasks
        analysis_progress[run_id]["message"] = "正在生成整体总结..."
        analysis_progress[run_id]["progress"] = 90
        
        overall_prompt = f"""你是一个专业的量化交易分析师。请对整个回测实验进行总结：

策略配置：
{json.dumps(strategy_config, ensure_ascii=False, indent=2)}

回测总体指标：
{json.dumps(stats_summary, ensure_ascii=False, indent=2)}

失败交易数量：{len(losing_trades)}

最后一笔失败交易的总结：
{previous_summary if previous_summary else "无"}

请提供整体回测实验的总结（几句话即可）：包括整体表现评价、主要问题、改进方向等。
"""
        
        overall_messages = [
            {"role": "system", "content": "你是一个专业的量化交易分析师，擅长总结回测实验结果并提供改进建议。"},
            {"role": "user", "content": overall_prompt}
        ]
        
        overall_summary = await call_ai_model(request.api_url, request.api_key, request.model_name, overall_messages)
        
        # 保存整体总结到backtest_end条目
        for log_entry in log_entries:
            if log_entry.get("type") == "backtest_end":
                log_entry["overall_summary"] = overall_summary
                break
        
        # 保存更新后的日志
        logger.update_log(run_id, log_entries)
        
        analysis_progress[run_id] = {
            "status": "completed",
            "progress": 100,
            "message": f"AI分析完成，共分析了 {len(losing_trades)} 笔失败交易",
            "total": total_tasks,
            "current": total_tasks
        }
        
    except asyncio.CancelledError:
        analysis_progress[run_id] = {
            "status": "cancelled",
            "progress": analysis_progress.get(run_id, {}).get("progress", 0),
            "message": "分析任务已被手动停止",
            "total": analysis_progress.get(run_id, {}).get("total", 0),
            "current": analysis_progress.get(run_id, {}).get("current", 0)
        }
        raise
    except FileNotFoundError:
        analysis_progress[run_id] = {
            "status": "error",
            "progress": 0,
            "message": f"回测记录不存在: {run_id}",
            "total": 0,
            "current": 0
        }
    except Exception as e:
        analysis_progress[run_id] = {
            "status": "error",
            "progress": 0,
            "message": f"分析失败: {str(e)}",
            "total": 0,
            "current": 0
        }
    finally:
        # 任务结束后从任务表中移除
        try:
            if run_id in analysis_tasks:
                del analysis_tasks[run_id]
        except Exception:
            pass


@app.post("/api/backtest/{run_id}/analyze")
async def analyze_backtest(run_id: str, request: AIAnalysisRequest):
    """
    启动AI分析任务（异步）
    
    Args:
        run_id: 回测运行ID
        request: AI分析请求参数
        
    Returns:
        任务启动响应
    """
    # 检查是否已有任务在运行
    if run_id in analysis_progress:
        current_status = analysis_progress[run_id].get("status")
        if current_status == "running":
            raise HTTPException(status_code=400, detail="分析任务已在运行中")
    
    # 启动后台任务
    task = asyncio.create_task(analyze_backtest_task(run_id, request))
    analysis_tasks[run_id] = task
    
    return {
        "message": "AI分析任务已启动",
        "run_id": run_id
    }


@app.get("/api/backtest/{run_id}/analyze/progress")
async def get_analysis_progress(run_id: str):
    """
    获取AI分析任务进度
    
    Args:
        run_id: 回测运行ID
        
    Returns:
        进度信息
    """
    if run_id not in analysis_progress:
        raise HTTPException(status_code=404, detail="分析任务不存在")
    
    return analysis_progress[run_id]


@app.post("/api/backtest/{run_id}/analyze/stop")
async def stop_analyze(run_id: str):
    """
    停止AI分析任务
    """
    task = analysis_tasks.get(run_id)
    if task is None:
        raise HTTPException(status_code=404, detail="未找到进行中的分析任务")
    if task.done():
        # 已结束
        del analysis_tasks[run_id]
        return {"message": "任务已结束"}
    task.cancel()
    return {"message": "已发送停止指令"}


# ============== LongPort OpenAPI 接口 ==============
@app.get("/api/longport/quote")
async def lp_quote(symbols: str, mode: str = "paper"):
    """获取实时行情，symbols以逗号分隔，如 AAPL.US,700.HK"""
    try:
        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
        if not symbol_list:
            raise HTTPException(status_code=400, detail="symbols 不能为空")
        data = longport_service.get_realtime_quotes(symbol_list, mode=mode)
        return {"quotes": data, "count": len(data)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/longport/assets")
async def lp_assets(mode: str = "paper"):
    """获取账户资产信息"""
    try:
        data = longport_service.get_assets(mode=mode)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/longport/positions")
async def lp_positions(mode: str = "paper"):
    """获取持仓列表"""
    try:
        data = longport_service.get_positions(mode=mode)
        return {"positions": data, "count": len(data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/longport/orders/today")
async def lp_today_orders(mode: str = "paper"):
    """获取当日订单"""
    try:
        data = longport_service.list_today_orders(mode=mode)
        return {"orders": data, "count": len(data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/longport/order")
async def lp_place_order(req: LongPortOrderRequest):
    """下单接口"""
    try:
        if req.order_type.lower() == "limit" and (req.price is None or req.price <= 0):
            raise HTTPException(status_code=400, detail="限价单需要提供正的 price")
        resp = longport_service.place_order(
            symbol=req.symbol,
            side=req.side,
            quantity=req.quantity,
            mode=req.mode,
            order_type=req.order_type,
            price=req.price,
            time_in_force=req.time_in_force,
            remark=req.remark,
            **(req.extra or {}),
        )
        return resp
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/longport/order/{order_id}/cancel")
async def lp_cancel_order(order_id: str, mode: str = "paper"):
    """撤单接口"""
    try:
        resp = longport_service.cancel_order(order_id=order_id, mode=mode)
        return resp
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ================== 实盘数据爬取任务 ==================
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
import os
import uuid

FETCH_DIR = os.path.join("stock_data", "fetch")
os.makedirs(FETCH_DIR, exist_ok=True)

class FetchInterval(BaseModel):
    value: int
    unit: str  # 'seconds' | 'minutes' | 'hours'

class FetchDuration(BaseModel):
    mode: str  # 'permanent' | 'finite'
    days: int = 0
    hours: int = 0
    minutes: int = 0
    seconds: int = 0

class FetchTaskCreateRequest(BaseModel):
    symbol: str
    mode: str = Field("paper", description="paper 或 live")
    interval: FetchInterval
    sessions: List[str] = Field(default_factory=list, description="盘前/盘中/盘后/夜盘 等")
    duration: FetchDuration

class FetchTaskInfo(BaseModel):
    task_id: str
    symbol: str
    mode: str
    interval: FetchInterval
    sessions: List[str]
    duration: FetchDuration
    start_time: str
    status: str  # running|stopped|completed
    file_path: str
    timezone: str = "America/New_York"
    current_session: str | None = None  # 盘前/盘中/盘后/夜盘/休市

# 内存中的任务管理
_fetch_tasks: Dict[str, Dict] = {}
_fetch_task_handles: Dict[str, asyncio.Task] = {}
# 暂停标志
_fetch_task_paused: Dict[str, bool] = {}


def _interval_to_seconds(interval: FetchInterval) -> float:
    unit = interval.unit.lower()
    if unit.startswith("sec"):
        return max(1, interval.value)
    if unit.startswith("min"):
        return max(1, interval.value) * 60
    if unit.startswith("hour"):
        return max(1, interval.value) * 3600
    raise HTTPException(status_code=400, detail="interval.unit 必须为 seconds/minutes/hours")


def _duration_to_timedelta(duration: FetchDuration) -> Optional[timedelta]:
    if duration.mode == "permanent":
        return None
    total = timedelta(days=duration.days, hours=duration.hours, minutes=duration.minutes, seconds=duration.seconds)
    if total.total_seconds() <= 0:
        raise HTTPException(status_code=400, detail="有限时长必须大于0")
    return total


def _fetch_file_path(task_id: str) -> str:
    return os.path.join(FETCH_DIR, f"{task_id}.txt")


def _write_fetch_header(task_id: str, info: FetchTaskInfo) -> None:
    path = _fetch_file_path(task_id)
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(info.model_dump(), ensure_ascii=False) + "\n")


def _append_fetch_point(task_id: str, point: Dict) -> None:
    path = _fetch_file_path(task_id)
    # 格式：时间,交易时段,价格（逗号分隔）
    # 时间只精确到秒，去掉毫秒
    timestamp_str = point.get("timestamp", "")
    try:
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        # 格式化为 YYYY-MM-DD HH:MM:SS，去掉毫秒
        time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        time_str = timestamp_str[:19] if len(timestamp_str) >= 19 else timestamp_str
    
    quote_session = point.get("quote_session", "")
    price = point.get("price", "")
    # CSV格式：时间,交易时段,价格（逗号分隔）
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{time_str},{quote_session},{price}\n")


def _is_us_stock(symbol: str) -> bool:
    """判断是否为美股"""
    return symbol.upper().endswith('.US')


def _is_hk_stock(symbol: str) -> bool:
    """判断是否为港股"""
    return symbol.upper().endswith('.HK')


def _is_dst(now_et: datetime) -> bool:
    """
    判断当前是否为夏令时（Daylight Saving Time）
    美国夏令时：3月第二个周日 02:00 - 11月第一个周日 02:00
    """
    year = now_et.year
    # 3月第二个周日
    march = datetime(year, 3, 1, tzinfo=now_et.tzinfo)
    march_first_sunday = march + timedelta(days=(6 - march.weekday()) % 7)
    march_second_sunday = march_first_sunday + timedelta(days=7)
    dst_start = march_second_sunday.replace(hour=2, minute=0, second=0, microsecond=0)
    
    # 11月第一个周日
    november = datetime(year, 11, 1, tzinfo=now_et.tzinfo)
    november_first_sunday = november + timedelta(days=(6 - november.weekday()) % 7)
    dst_end = november_first_sunday.replace(hour=2, minute=0, second=0, microsecond=0)
    
    return dst_start <= now_et < dst_end


def _get_us_session_name_cn(now_et: datetime) -> str:
    """
    获取美股交易时段（中文）
    考虑冬令时和夏令时，但交易时段在ET时区下是固定的
    """
    # Weekend
    if now_et.weekday() >= 5:
        return "休市"
    t = now_et.time()
    # Define ranges in ET (交易时段在ET时区下是固定的)
    pre_start, pre_end = time(4, 0), time(9, 30)
    regular_start, regular_end = time(9, 30), time(16, 0)
    post_start, post_end = time(16, 0), time(20, 0)
    # Overnight spans 20:00 - 04:00 next day
    if pre_start <= t < pre_end:
        return "盘前"
    if regular_start <= t < regular_end:
        return "盘中"
    if post_start <= t < post_end:
        return "盘后"
    # Overnight or closed outside ranges on weekdays
    return "夜盘"


def _get_hk_session_name_cn(now_hk: datetime) -> str:
    """
    获取港股交易时段（中文）
    港股交易时段（HK时间，UTC+8）：
    - 早盘：09:30 - 12:00
    - 午休：12:00 - 13:00
    - 下午盘：13:00 - 16:00
    - 夜盘（延时交易）：17:15 - 23:45（当日）
    """
    # Weekend
    if now_hk.weekday() >= 5:
        return "休市"
    t = now_hk.time()
    # 早盘
    if time(9, 30) <= t < time(12, 0):
        return "盘中"
    # 午休
    if time(12, 0) <= t < time(13, 0):
        return "休市"
    # 下午盘
    if time(13, 0) <= t < time(16, 0):
        return "盘中"
    # 夜盘（延时交易）
    if time(17, 15) <= t < time(23, 45):
        return "夜盘"
    # 其他时间为休市（包括 03:00 - 09:30 和 23:45 - 24:00）
    return "休市"


def _get_session_name_cn(symbol: str, now_utc: datetime) -> str:
    """
    根据股票代码和UTC时间获取交易时段（中文）
    
    Args:
        symbol: 股票代码
        now_utc: UTC时间
    
    Returns:
        交易时段名称（盘前/盘中/盘后/夜盘/休市）
    """
    if _is_us_stock(symbol):
        # 美股：转换为ET时区
        now_et = now_utc.astimezone(ZoneInfo("America/New_York"))
        return _get_us_session_name_cn(now_et)
    elif _is_hk_stock(symbol):
        # 港股：转换为HK时区
        now_hk = now_utc.astimezone(ZoneInfo("Asia/Hong_Kong"))
        return _get_hk_session_name_cn(now_hk)
    else:
        # 未知类型，默认使用美股逻辑
        now_et = now_utc.astimezone(ZoneInfo("America/New_York"))
        return _get_us_session_name_cn(now_et)


async def _run_fetch_task(task_id: str) -> None:
    meta = _fetch_tasks.get(task_id)
    if not meta:
        return
    symbol = meta["symbol"]
    mode = meta["mode"]
    interval = meta["interval"]
    duration_delta = meta["duration_delta"]  # Optional[timedelta]
    started_at: datetime = meta["started_at"]
    stop_at: Optional[datetime] = started_at + duration_delta if duration_delta else None

    try:
        while True:
            # 检查是否暂停
            if _fetch_task_paused.get(task_id, False):
                meta["status"] = "paused"
                await asyncio.sleep(1)
                continue
            
            now = datetime.now(ZoneInfo("UTC"))
            current_session = _get_session_name_cn(symbol, now)
            meta["current_session"] = current_session
            if stop_at and now >= stop_at:
                meta["status"] = "completed"
                break
            # Gate by configured sessions; if not selected, wait 1s
            selected_sessions = meta.get("sessions") or []
            if selected_sessions and current_session not in selected_sessions:
                meta["status"] = "waiting"
                await asyncio.sleep(1)
                continue
            else:
                meta["status"] = "running"
            # 获取当前时段的最新价格
            q = longport_service.get_last_done_for_session(symbol, current_session, mode=mode)
            last_done = q.get("last_done")
            quote_session = q.get("quote_session", current_session)
            point = {
                "timestamp": now.isoformat(),
                "price": last_done,
                "quote_session": quote_session,
            }
            _append_fetch_point(task_id, point)
            await asyncio.sleep(_interval_to_seconds(interval))
    except asyncio.CancelledError:
        meta["status"] = "stopped"
        raise
    except Exception as e:
        meta["status"] = f"error: {_format_error(e)}"
    finally:
        _fetch_task_handles.pop(task_id, None)


@app.post("/api/fetch/create")
async def create_fetch_task(req: FetchTaskCreateRequest):
    try:
        # 基本校验
        if req.interval.value <= 0:
            raise HTTPException(status_code=400, detail="interval.value 必须为正整数")
        duration_delta = _duration_to_timedelta(req.duration)
        # 生成任务ID
        task_id = str(uuid.uuid4())[:8]
        started_at = datetime.now(ZoneInfo("UTC"))
        # 根据股票代码确定时区
        if _is_us_stock(req.symbol):
            timezone = "America/New_York"
        elif _is_hk_stock(req.symbol):
            timezone = "Asia/Hong_Kong"
        else:
            timezone = "America/New_York"  # 默认使用美股时区
        info = FetchTaskInfo(
            task_id=task_id,
            symbol=req.symbol,
            mode=req.mode,
            interval=req.interval,
            sessions=req.sessions,
            duration=req.duration,
            start_time=started_at.isoformat(),
            status="running",
        file_path=_fetch_file_path(task_id),
        timezone=timezone,
        current_session=None,
        )
        _fetch_tasks[task_id] = {
            "symbol": req.symbol,
            "mode": req.mode,
            "interval": req.interval,
            "sessions": req.sessions,
            "duration": req.duration,
            "duration_delta": duration_delta,
            "started_at": started_at,
            "status": "running",
            "file_path": info.file_path,
        }
        _fetch_task_paused[task_id] = False
        _write_fetch_header(task_id, info)
        # 启动后台任务
        task = asyncio.create_task(_run_fetch_task(task_id))
        _fetch_task_handles[task_id] = task
        return {"task_id": task_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=_format_error(e))


@app.get("/api/fetch/list")
async def list_fetch_tasks():
    summaries = []
    for task_id, meta in _fetch_tasks.items():
        summaries.append({
            "task_id": task_id,
            "symbol": meta["symbol"],
            "mode": meta["mode"],
            "interval": meta["interval"].model_dump() if hasattr(meta["interval"], "model_dump") else meta["interval"].__dict__,
            "sessions": meta["sessions"],
            "status": meta["status"],
            "started_at": meta["started_at"].isoformat(),
            "current_session": meta.get("current_session"),
        })
    return {"tasks": summaries, "count": len(summaries)}


@app.get("/api/fetch/{task_id}")
async def get_fetch_task(task_id: str):
    meta = _fetch_tasks.get(task_id)
    if not meta:
        raise HTTPException(status_code=404, detail="任务不存在")
    path = _fetch_file_path(task_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="任务文件不存在")
    try:
        # 读取文件，第一行是配置，后面是CSV格式数据点（逗号分隔：时间,交易时段,价格）
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        config = json.loads(lines[0]) if lines else {}
        # 更新配置中的状态为内存中的最新状态
        if meta:
            config["status"] = meta["status"]
        # 只返回最近100条数据
        points_raw = lines[1:][-100:]
        points = []
        for line in points_raw:
            line = line.strip()
            if not line:
                continue
            # 格式：YYYY-MM-DD HH:MM:SS,交易时段,价格（逗号分隔）
            # 时间包含空格，所以需要按第一个逗号分割
            parts = line.split(",", 2)  # 最多分割2次，得到3个部分
            if len(parts) < 3:
                continue
            timestamp_str = parts[0].strip()
            quote_session = parts[1].strip()
            price_str = parts[2].strip()
            try:
                price = float(price_str) if price_str else None
            except ValueError:
                price = None
            points.append({
                "timestamp": timestamp_str,
                "quote_session": quote_session,
                "price": price,
            })
        return {"config": config, "latest_points": points, "count": len(points), "current_session": _fetch_tasks.get(task_id, {}).get("current_session")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=_format_error(e))


@app.post("/api/fetch/{task_id}/pause")
async def pause_fetch_task(task_id: str):
    meta = _fetch_tasks.get(task_id)
    if not meta:
        raise HTTPException(status_code=404, detail="任务不存在")
    if meta["status"] in ["stopped", "completed"]:
        raise HTTPException(status_code=400, detail="任务已停止或已完成，无法暂停")
    _fetch_task_paused[task_id] = True
    return {"message": "任务已暂停"}


@app.post("/api/fetch/{task_id}/resume")
async def resume_fetch_task(task_id: str):
    meta = _fetch_tasks.get(task_id)
    if not meta:
        raise HTTPException(status_code=404, detail="任务不存在")
    if meta["status"] in ["stopped", "completed"]:
        raise HTTPException(status_code=400, detail="任务已停止或已完成，无法恢复")
    _fetch_task_paused[task_id] = False
    return {"message": "任务已恢复"}


@app.post("/api/fetch/{task_id}/stop")
async def stop_fetch_task(task_id: str):
    meta = _fetch_tasks.get(task_id)
    if not meta:
        raise HTTPException(status_code=404, detail="任务不存在")
    handle = _fetch_task_handles.get(task_id)
    if not handle:
        meta["status"] = "stopped"
        _fetch_task_paused.pop(task_id, None)
        return {"message": "任务已停止"}
    try:
        handle.cancel()
        _fetch_task_paused.pop(task_id, None)
        return {"message": "已发送停止指令"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=_format_error(e))

