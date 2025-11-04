"""
API接口模块
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
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


@app.on_event("startup")
async def load_tasks_from_logs():
    """启动时加载所有任务日志到内存"""
    import os
    from pathlib import Path
    
    # 加载交易任务（使用logs/trade目录）
    trade_log_dir = Path("logs/trade")
    if trade_log_dir.exists():
        for log_file in trade_log_dir.glob("*.txt"):
            try:
                task_id = log_file.stem
                # 读取整个文件内容
                with open(log_file, "r", encoding="utf-8") as f:
                    all_content = f.read()
                
                lines = all_content.split('\n')
                if not lines or not lines[0].strip():
                    continue
                
                # 解析第一行配置JSON
                config = json.loads(lines[0].strip())
                
                # 如果status是running，改为paused
                status = config.get("status", "stopped")
                if status == "running":
                    status = "paused"
                    # 更新配置中的status
                    config["status"] = "paused"
                    # 更新日志文件中的status
                    lines[0] = json.dumps(config, ensure_ascii=False)
                    with open(log_file, "w", encoding="utf-8") as f:
                        f.write('\n'.join(lines))
                
                # 重建meta对象
                duration = config.get("duration", {})
                # 转换duration为timedelta
                duration_obj = TradeDuration(**duration)
                if duration_obj.mode == "permanent":
                    duration_delta = None
                else:
                    duration_delta = timedelta(
                        days=duration_obj.days,
                        hours=duration_obj.hours,
                        minutes=duration_obj.minutes,
                        seconds=duration_obj.seconds
                    )
                
                started_at_str = config.get("start_time", "")
                try:
                    started_at = datetime.fromisoformat(started_at_str.replace("Z", "+00:00"))
                except Exception:
                    started_at = datetime.now(ZoneInfo("UTC"))
                
                # 初始化缓存（从日志文件重建价格缓存）
                price_cache = []
                price_timestamps = []
                trade_records = []
                
                # 解析日志行，重建缓存和交易记录
                if len(lines) > 1:
                    for line in lines[1:]:  # 跳过第一行配置
                        line = line.strip()
                        if not line:
                            continue
                        
                        parts = line.split(",", 2)
                        if len(parts) >= 3:
                            timestamp_str, log_type, data_str = parts[0], parts[1], parts[2]
                            try:
                                data = json.loads(data_str)
                                
                                # 重建价格缓存
                                if log_type == "price_sample" and "price" in data:
                                    price_cache.append(data["price"])
                                    try:
                                        # 尝试解析时间戳
                                        dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                                        price_timestamps.append(dt.isoformat())
                                    except Exception:
                                        price_timestamps.append(timestamp_str)
                                
                                # 重建交易记录（只包含buy/sell）
                                if log_type == "trade" and data.get("trade_type") in ["buy", "sell"]:
                                    trade_records.append({
                                        "timestamp": timestamp_str,
                                        "type": "trade",
                                        "trade_type": data.get("trade_type"),
                                        "price": data.get("price"),
                                        "signal_info": data.get("signal_info", {}),
                                        "session": data.get("session", ""),
                                    })
                            except Exception:
                                continue
                
                # 限制缓存大小
                max_cache_size = config.get("max_cache_size", 1000)
                if len(price_cache) > max_cache_size:
                    price_cache = price_cache[-max_cache_size:]
                    price_timestamps = price_timestamps[-max_cache_size:]
                
                # 读取metrics（如果存在）
                metrics = config.get("metrics", {})
                initial_cash = metrics.get("initial_cash", 100000.0) if metrics else 100000.0
                
                # 加载到_trade_tasks
                _trade_tasks[task_id] = {
                    "symbol": config.get("symbol", ""),
                    "mode": config.get("mode", "paper"),
                    "strategy_name": config.get("strategy_name", ""),
                    "strategy_params": config.get("strategy_params", {}),
                    "sessions": config.get("sessions", []),
                    "duration": duration,
                    "duration_delta": duration_delta,
                    "price_interval": config.get("price_interval", {"value": 5, "unit": "seconds"}),
                    "signal_interval": config.get("signal_interval", {"value": 30, "unit": "seconds"}),
                    "max_cache_size": max_cache_size,
                    "started_at": started_at,
                    "status": status,
                    "file_path": config.get("file_path", os.path.join("logs", "trade", f"{task_id}.txt")),
                    "price_cache": price_cache,
                    "price_timestamps": price_timestamps,
                    "trade_records": trade_records,
                    "current_session": config.get("current_session"),
                    "timezone": config.get("timezone", "America/New_York"),
                    "initial_cash": initial_cash,
                }
                
                # 如果状态是paused，设置暂停标志
                if status == "paused":
                    _trade_task_paused[task_id] = True
                else:
                    _trade_task_paused[task_id] = False
                        
            except Exception as e:
                # 如果某个任务日志加载失败，记录错误但继续加载其他任务
                print(f"Warning: Failed to load trade task {log_file.stem}: {_format_error(e)}")
                continue
    
    # 回测任务不需要加载到内存，因为它们是从日志文件动态读取的
    # list_backtests() 函数会直接从日志文件读取
    print(f"Loaded {len(_trade_tasks)} trade tasks from logs")
    
    # 加载爬取数据任务（使用stock_data/fetch目录）
    fetch_log_dir = Path(FETCH_DIR)
    if fetch_log_dir.exists():
        for fetch_file in fetch_log_dir.glob("*.txt"):
            try:
                task_id = fetch_file.stem
                # 读取第一行配置
                with open(fetch_file, "r", encoding="utf-8") as f:
                    first_line = f.readline().strip()
                
                if not first_line:
                    continue
                
                # 解析第一行配置JSON
                config = json.loads(first_line)
                
                # 如果status是stopped，跳过该任务
                status = config.get("status", "stopped")
                if status == "stopped":
                    continue
                
                # 如果status不是stopped，设置为paused并更新文件
                if status != "paused":
                    status = "paused"
                    config["status"] = "paused"
                    # 更新文件中的status
                    with open(fetch_file, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    if lines:
                        lines[0] = json.dumps(config, ensure_ascii=False) + "\n"
                        with open(fetch_file, "w", encoding="utf-8") as f:
                            f.writelines(lines)
                
                # 解析配置并重建meta对象
                interval = config.get("interval", {"value": 5, "unit": "seconds"})
                interval_obj = FetchInterval(**interval) if isinstance(interval, dict) else interval
                
                duration = config.get("duration", {"mode": "permanent"})
                duration_obj = FetchDuration(**duration) if isinstance(duration, dict) else duration
                duration_delta = _duration_to_timedelta(duration_obj)
                
                started_at_str = config.get("start_time", "")
                try:
                    started_at = datetime.fromisoformat(started_at_str.replace("Z", "+00:00"))
                except Exception:
                    started_at = datetime.now(ZoneInfo("UTC"))
                
                # 加载到_fetch_tasks
                _fetch_tasks[task_id] = {
                    "symbol": config.get("symbol", ""),
                    "mode": config.get("mode", "paper"),
                    "interval": interval_obj,
                    "sessions": config.get("sessions", []),
                    "duration": duration,
                    "duration_delta": duration_delta,
                    "started_at": started_at,
                    "status": status,
                    "file_path": config.get("file_path", _fetch_file_path(task_id)),
                    "current_session": config.get("current_session"),
                    "timezone": config.get("timezone", "America/New_York"),
                }
                
                # 如果状态是paused，设置暂停标志
                if status == "paused":
                    _fetch_task_paused[task_id] = True
                else:
                    _fetch_task_paused[task_id] = False
                        
            except Exception as e:
                # 如果某个任务日志加载失败，记录错误但继续加载其他任务
                print(f"Warning: Failed to load fetch task {fetch_file.stem}: {_format_error(e)}")
                continue
    
    print(f"Loaded {len(_fetch_tasks)} fetch tasks from logs")


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
BACKTEST_LOG_DIR = "logs/test"  # 回测日志目录
backtest_engine = Backtest(logger=BacktestLogger(logs_dir=BACKTEST_LOG_DIR), data_generator=data_generator)
logger = BacktestLogger(logs_dir=BACKTEST_LOG_DIR)
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
        
        # 爬取的实盘数据（只返回status为stopped的数据）
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
                                # 只返回status为stopped的数据
                                status = config.get("status", "stopped")
                                if status != "stopped":
                                    continue
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


@app.delete("/api/backtest/{run_id}")
async def delete_backtest(run_id: str):
    """
    删除回测记录
    
    Args:
        run_id: 回测运行ID
        
    Returns:
        删除成功消息
    """
    try:
        # 检查回测是否存在
        try:
            logger.load(run_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="回测记录不存在")
        
        # 删除日志文件
        log_file_path = os.path.join(BACKTEST_LOG_DIR, f"{run_id}.json")
        if os.path.exists(log_file_path):
            os.remove(log_file_path)
        
        return {"message": "回测记录已删除"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=_format_error(e))


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


# ================== 账户管理API ==================
@app.get("/api/account/list")
async def get_account_list(mode: str = "paper"):
    """获取所有账户列表（US和HK）"""
    try:
        accounts = longport_service.get_account_list(mode=mode)
        return {"accounts": accounts, "count": len(accounts)}
    except RuntimeError as e:
        # RuntimeError 通常是凭证相关的友好错误信息
        error_msg = str(e)
        print(f"[ERROR] 凭证错误: {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        error_str = str(e).lower()
        if "credential" in error_str or "auth" in error_str or "unauthorized" in error_str:
            raise HTTPException(status_code=400, detail=f"{mode}账户凭证验证失败，请检查账户凭证是否正确")
        else:
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/account/{market}/assets")
async def get_account_assets(market: str, mode: str = "paper"):
    """
    获取特定市场的资产信息
    market: "US" 或 "HK"
    """
    try:
        market = market.upper()
        if market not in ["US", "HK"]:
            raise HTTPException(status_code=400, detail="market必须是US或HK")
        assets = longport_service.get_assets_by_market(market, mode=mode)
        # 使用print输出以便调试（比logging更可靠）
        print(f"[DEBUG] 获取{market}市场资产信息: {assets}")
        print(f"[DEBUG] 资产类型: {type(assets)}, 是否为空: {not assets}")
        return assets
    except HTTPException:
        raise
    except RuntimeError as e:
        # RuntimeError 通常是凭证相关的友好错误信息
        error_msg = str(e)
        print(f"[ERROR] 凭证错误: {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        import traceback
        error_detail = f"获取资产信息失败: {str(e)}"
        print(f"[ERROR] {error_detail}")
        print(f"[ERROR] {traceback.format_exc()}")
        # 检查是否是常见的错误类型
        error_str = str(e).lower()
        if "credential" in error_str or "auth" in error_str or "unauthorized" in error_str:
            raise HTTPException(status_code=400, detail=f"{mode}账户凭证验证失败，请检查账户凭证是否正确")
        else:
            raise HTTPException(status_code=500, detail=error_detail)


@app.get("/api/account/{market}/positions")
async def get_account_positions(market: str, mode: str = "paper"):
    """获取特定市场的持仓列表"""
    try:
        market = market.upper()
        if market not in ["US", "HK"]:
            raise HTTPException(status_code=400, detail="market必须是US或HK")
        positions = longport_service.get_positions_by_market(market, mode=mode)
        return {"positions": positions, "count": len(positions)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _is_today_in_market_timezone(dt: datetime, market: str) -> bool:
    """
    判断datetime是否在指定市场的当日（按当地时区）
    """
    if not dt:
        return False
    
    # 转换为市场时区
    if market == "US":
        # 美股时区：America/New_York (EST/EDT)
        market_tz = ZoneInfo("America/New_York")
    elif market == "HK":
        # 港股时区：Asia/Hong_Kong (HKT)
        market_tz = ZoneInfo("Asia/Hong_Kong")
    else:
        return False
    
    # 如果dt是naive，假设是UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    
    # 转换为市场时区
    dt_market = dt.astimezone(market_tz)
    
    # 获取市场时区的今天
    today_market = datetime.now(market_tz).date()
    
    # 判断是否是同一天
    return dt_market.date() == today_market


@app.get("/api/account/{market}/orders/today")
async def get_account_today_orders(market: str, mode: str = "paper"):
    """
    获取特定市场的当日交易记录（按当地股票交易时间）
    market: "US" 或 "HK"
    """
    try:
        market = market.upper()
        if market not in ["US", "HK"]:
            raise HTTPException(status_code=400, detail="market必须是US或HK")
        
        # 获取该市场的所有订单
        orders = longport_service.get_today_orders_by_market(market, mode=mode)
        
        # 过滤出当日订单（按市场时区的当日）
        today_orders = []
        for order in orders:
            # 尝试从不同字段获取时间
            order_time = None
            for time_field in ["submitted_at", "created_at", "updated_at", "timestamp"]:
                if time_field in order and order[time_field]:
                    try:
                        if isinstance(order[time_field], str):
                            # 尝试解析ISO格式时间
                            order_time = datetime.fromisoformat(order[time_field].replace("Z", "+00:00"))
                        elif isinstance(order[time_field], datetime):
                            order_time = order[time_field]
                        if order_time:
                            break
                    except Exception:
                        continue
            
            # 如果找到了时间且是当日，则加入
            if order_time and _is_today_in_market_timezone(order_time, market):
                today_orders.append(order)
            elif not order_time:
                # 如果没有时间字段，默认认为是当日（可能是实时订单）
                today_orders.append(order)
        
        return {"orders": today_orders, "count": len(today_orders), "market": market}
    except HTTPException:
        raise
    except RuntimeError as e:
        # RuntimeError 通常是凭证相关的友好错误信息
        error_msg = str(e)
        print(f"[ERROR] 凭证错误: {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        error_str = str(e).lower()
        if "credential" in error_str or "auth" in error_str or "unauthorized" in error_str:
            raise HTTPException(status_code=400, detail=f"{mode}账户凭证验证失败，请检查账户凭证是否正确")
        else:
            raise HTTPException(status_code=500, detail=str(e))


# ================== 实盘数据爬取任务 ==================
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


def _update_fetch_status(task_id: str, status: str) -> None:
    """更新fetch任务文件中的状态"""
    path = _fetch_file_path(task_id)
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if lines:
            config = json.loads(lines[0].strip())
            config["status"] = status
            lines[0] = json.dumps(config, ensure_ascii=False) + "\n"
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(lines)
    except Exception as e:
        print(f"Warning: Failed to update fetch task status in file {task_id}: {_format_error(e)}")


def _write_fetch_header(task_id: str, info: FetchTaskInfo) -> None:
    # 确保爬取数据目录存在
    os.makedirs(FETCH_DIR, exist_ok=True)
    
    path = _fetch_file_path(task_id)
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(info.model_dump(), ensure_ascii=False) + "\n")


def _append_fetch_point(task_id: str, point: Dict) -> None:
    # 确保爬取数据目录存在
    os.makedirs(FETCH_DIR, exist_ok=True)
    
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


def _get_local_time(symbol: str, now_utc: datetime) -> datetime:
    """
    根据股票代码获取对应的本地时区时间
    
    Args:
        symbol: 股票代码
        now_utc: UTC时间
    
    Returns:
        本地时区时间
    """
    if _is_us_stock(symbol):
        # 美股：使用ET时区
        return now_utc.astimezone(ZoneInfo("America/New_York"))
    elif _is_hk_stock(symbol):
        # 港股：使用HK时区
        return now_utc.astimezone(ZoneInfo("Asia/Hong_Kong"))
    else:
        # 未知类型，默认使用UTC
        return now_utc


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
                if meta["status"] != "paused":
                    meta["status"] = "paused"
                    _update_fetch_status(task_id, "paused")
                await asyncio.sleep(1)
                continue
            
            now = datetime.now(ZoneInfo("UTC"))
            current_session = _get_session_name_cn(symbol, now)
            meta["current_session"] = current_session
            if stop_at and now >= stop_at:
                meta["status"] = "completed"
                _update_fetch_status(task_id, "completed")
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
        _update_fetch_status(task_id, "stopped")
        raise
    except Exception as e:
        error_status = f"error: {_format_error(e)}"
        meta["status"] = error_status
        _update_fetch_status(task_id, error_status)
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
    meta["status"] = "paused"
    _update_fetch_status(task_id, "paused")
    return {"message": "任务已暂停"}


@app.post("/api/fetch/{task_id}/resume")
async def resume_fetch_task(task_id: str):
    meta = _fetch_tasks.get(task_id)
    if not meta:
        raise HTTPException(status_code=404, detail="任务不存在")
    if meta["status"] in ["stopped", "completed"]:
        raise HTTPException(status_code=400, detail="任务已停止或已完成，无法恢复")
    _fetch_task_paused[task_id] = False
    meta["status"] = "running"
    _update_fetch_status(task_id, "running")
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
        _update_fetch_status(task_id, "stopped")
        return {"message": "任务已停止"}
    try:
        handle.cancel()
        _fetch_task_paused.pop(task_id, None)
        meta["status"] = "stopped"
        _update_fetch_status(task_id, "stopped")
        return {"message": "已发送停止指令"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=_format_error(e))


@app.delete("/api/fetch/{task_id}")
async def delete_fetch_task(task_id: str):
    """删除爬取任务及其数据文件"""
    try:
        # 检查任务是否存在
        meta = _fetch_tasks.get(task_id)
        if not meta:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 停止任务（如果正在运行）
        if meta.get("status") == "running":
            meta["status"] = "stopped"
            task_handle = _fetch_task_handles.get(task_id)
            if task_handle:
                task_handle.cancel()
        
        # 从内存中删除
        _fetch_tasks.pop(task_id, None)
        _fetch_task_handles.pop(task_id, None)
        _fetch_task_paused.pop(task_id, None)
        
        # 删除数据文件
        file_path = _fetch_file_path(task_id)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        return {"message": "任务已删除"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=_format_error(e))


# ================== 实时交易任务 ==================
TRADE_DIR = os.path.join("logs", "trade")
os.makedirs(TRADE_DIR, exist_ok=True)

class TradeInterval(BaseModel):
    value: int
    unit: str  # 'seconds' | 'minutes' | 'hours'

class TradeDuration(BaseModel):
    mode: str  # 'permanent' | 'finite'
    days: int = 0
    hours: int = 0
    minutes: int = 0
    seconds: int = 0

class TradeTaskCreateRequest(BaseModel):
    symbol: str
    mode: str = Field("paper", description="paper 或 live")
    strategy_name: str
    strategy_params: Dict = Field(default_factory=dict)
    sessions: List[str] = Field(default_factory=list, description="盘前/盘中/盘后/夜盘 等")
    duration: TradeDuration
    price_interval: TradeInterval  # 采样股票价格的时间间隔
    signal_interval: TradeInterval  # 产生信号的时间间隔
    max_cache_size: int = Field(1000, description="最大缓存的股票数据数目")

class TradeTaskInfo(BaseModel):
    task_id: str
    symbol: str
    mode: str
    strategy_name: str
    strategy_params: Dict
    sessions: List[str]
    duration: TradeDuration
    price_interval: TradeInterval
    signal_interval: TradeInterval
    max_cache_size: int
    start_time: str
    status: str  # running|stopped|completed|paused
    file_path: str
    timezone: str = "America/New_York"
    current_session: str | None = None

# 内存中的交易任务管理
_trade_tasks: Dict[str, Dict] = {}
_trade_task_handles: Dict[str, asyncio.Task] = {}
_trade_task_paused: Dict[str, bool] = {}

def _trade_file_path(task_id: str) -> str:
    return os.path.join(TRADE_DIR, f"{task_id}.txt")

def _write_trade_header(task_id: str, info: TradeTaskInfo) -> None:
    """写入交易任务配置头部"""
    os.makedirs(TRADE_DIR, exist_ok=True)
    path = _trade_file_path(task_id)
    config_dict = info.model_dump()
    # 初始化metrics字段
    config_dict["metrics"] = {
        "total_trades": 0,
        "buy_count": 0,
        "sell_count": 0,
        "win_rate": 0.0,
        "total_profit": 0.0,
        "total_return_rate": 0.0,
        "profit_loss_ratio": 0.0,
        "sharpe_ratio": 0.0,
        "initial_cash": 100000.0,  # 默认初始资金
        "current_cash": 100000.0,
        "current_position": 0.0,
        "current_asset_value": 100000.0,
    }
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(config_dict, ensure_ascii=False) + "\n")

def _calculate_trade_metrics(trade_records: List[Dict], initial_cash: float = 100000.0) -> Dict:
    """
    计算交易指标
    
    Args:
        trade_records: 交易记录列表
        initial_cash: 初始资金
    
    Returns:
        指标字典
    """
    if not trade_records:
        return {
            "total_trades": 0,
            "buy_count": 0,
            "sell_count": 0,
            "win_rate": 0.0,
            "total_profit": 0.0,
            "total_return_rate": 0.0,
            "profit_loss_ratio": 0.0,
            "sharpe_ratio": 0.0,
            "initial_cash": initial_cash,
            "current_cash": initial_cash,
            "current_position": 0.0,
            "current_asset_value": initial_cash,
        }
    
    # 统计买卖次数
    buy_count = sum(1 for r in trade_records if r.get("trade_type") == "buy")
    sell_count = sum(1 for r in trade_records if r.get("trade_type") == "sell")
    total_trades = len(trade_records)
    
    # 计算持仓和现金（模拟交易）
    cash = initial_cash
    position = 0.0  # 持仓数量
    position_cost = 0.0  # 持仓成本
    completed_trades = []  # 已完成的交易（买入-卖出配对）
    
    # 记录买入订单
    buy_orders = []
    
    for record in trade_records:
        trade_type = record.get("trade_type")
        price = record.get("price", 0.0)
        
        if trade_type == "buy" and price > 0:
            # 假设使用30%的资金买入（可以根据策略调整）
            buy_amount = cash * 0.3
            commission = buy_amount * 0.001  # 0.1%手续费
            actual_amount = buy_amount - commission
            quantity = actual_amount / price
            
            cash -= buy_amount
            position += quantity
            position_cost += buy_amount
            
            buy_orders.append({
                "price": price,
                "quantity": quantity,
                "amount": buy_amount,
            })
        
        elif trade_type == "sell" and price > 0 and len(buy_orders) > 0:
            # 卖出最近的买入订单
            buy_order = buy_orders.pop(0)
            sell_quantity = min(buy_order["quantity"], position)
            sell_amount = sell_quantity * price
            commission = sell_amount * 0.001
            actual_sell_amount = sell_amount - commission
            
            cash += actual_sell_amount
            position -= sell_quantity
            
            # 计算盈亏
            buy_cost = buy_order["amount"]
            profit = actual_sell_amount - buy_cost
            completed_trades.append(profit)
            
            position_cost -= buy_cost * (sell_quantity / buy_order["quantity"])
    
    # 计算当前资产价值
    current_price = trade_records[-1].get("price", 0.0) if trade_records else 0.0
    current_asset_value = cash + (position * current_price if current_price > 0 else 0)
    total_profit = current_asset_value - initial_cash
    total_return_rate = (total_profit / initial_cash * 100) if initial_cash > 0 else 0.0
    
    # 计算胜率
    winning_trades = sum(1 for p in completed_trades if p > 0)
    win_rate = (winning_trades / len(completed_trades) * 100) if completed_trades else 0.0
    
    # 计算盈亏比
    profits = [p for p in completed_trades if p > 0]
    losses = [p for p in completed_trades if p < 0]
    avg_profit = sum(profits) / len(profits) if profits else 0.0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 0.0
    profit_loss_ratio = (avg_profit / avg_loss) if avg_loss > 0 else 0.0
    
    # 计算夏普比率（简化版，使用日收益率）
    if len(completed_trades) > 1:
        returns = [p / initial_cash for p in completed_trades]
        avg_return = sum(returns) / len(returns)
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
        std_dev = variance ** 0.5
        sharpe_ratio = (avg_return / std_dev) if std_dev > 0 else 0.0
        # 年化（假设252个交易日）
        sharpe_ratio = sharpe_ratio * (252 ** 0.5) if len(returns) > 1 else 0.0
    else:
        sharpe_ratio = 0.0
    
    return {
        "total_trades": total_trades,
        "buy_count": buy_count,
        "sell_count": sell_count,
        "win_rate": round(win_rate, 2),
        "total_profit": round(total_profit, 2),
        "total_return_rate": round(total_return_rate, 2),
        "profit_loss_ratio": round(profit_loss_ratio, 2),
        "sharpe_ratio": round(sharpe_ratio, 4),
        "initial_cash": initial_cash,
        "current_cash": round(cash, 2),
        "current_position": round(position, 4),
        "current_asset_value": round(current_asset_value, 2),
    }

def _update_trade_metrics(task_id: str, trade_records: List[Dict], initial_cash: float = 100000.0) -> None:
    """
    更新日志文件第一行的metrics字段
    
    Args:
        task_id: 任务ID
        trade_records: 交易记录列表
        initial_cash: 初始资金
    """
    try:
        path = _trade_file_path(task_id)
        if not os.path.exists(path):
            return
        
        # 读取文件
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        if not lines:
            return
        
        # 解析第一行配置
        config = json.loads(lines[0].strip())
        
        # 计算指标
        metrics = _calculate_trade_metrics(trade_records, initial_cash)
        
        # 更新配置中的metrics
        config["metrics"] = metrics
        
        # 写回第一行
        lines[0] = json.dumps(config, ensure_ascii=False) + "\n"
        
        # 写回文件
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(lines)
    except Exception as e:
        # 静默失败，不影响主流程
        import logging
        logging.getLogger(__name__).warning(f"更新指标失败: {_format_error(e)}")

def _append_trade_log(task_id: str, log_entry: Dict) -> None:
    """追加交易日志"""
    os.makedirs(TRADE_DIR, exist_ok=True)
    path = _trade_file_path(task_id)
    timestamp_str = log_entry.get("timestamp", "")
    try:
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        time_str = timestamp_str[:19] if len(timestamp_str) >= 19 else timestamp_str
    
    # 写入日志：时间,类型,详情（JSON格式）
    log_type = log_entry.get("type", "log")
    log_data = {k: v for k, v in log_entry.items() if k != "timestamp" and k != "type"}
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{time_str},{log_type},{json.dumps(log_data, ensure_ascii=False)}\n")

async def _run_trade_task(task_id: str) -> None:
    """运行实时交易任务"""
    meta = _trade_tasks.get(task_id)
    if not meta:
        return
    
    symbol = meta["symbol"]
    mode = meta["mode"]
    strategy_name = meta["strategy_name"]
    strategy_params = meta["strategy_params"]
    sessions = meta["sessions"]
    duration_delta = meta["duration_delta"]
    price_interval = meta["price_interval"]
    signal_interval = meta["signal_interval"]
    max_cache_size = meta["max_cache_size"]
    started_at: datetime = meta["started_at"]
    stop_at: Optional[datetime] = started_at + duration_delta if duration_delta else None
    
    # 创建策略实例
    strategy_class = AVAILABLE_STRATEGIES.get(strategy_name)
    if not strategy_class:
        meta["status"] = f"error: 策略 {strategy_name} 不存在"
        return
    
    # 确保策略参数类型正确（前端可能发送字符串类型的数值）
    cleaned_params = {}
    try:
        # 获取策略的参数schema以确定参数类型
        params_schema = strategy_class.get_params_schema()
        for key, value in strategy_params.items():
            if key in params_schema:
                param_info = params_schema[key]
                if param_info.get("type") == "number":
                    # 转换为数字类型
                    if isinstance(value, str):
                        # 尝试转换为浮点数或整数
                        if '.' in value or 'e' in value.lower():
                            cleaned_params[key] = float(value)
                        else:
                            cleaned_params[key] = int(value)
                    else:
                        cleaned_params[key] = value
                else:
                    cleaned_params[key] = value
            else:
                # 未知参数，保持原值
                cleaned_params[key] = value
    except Exception as e:
        # 如果参数清理失败，使用原始参数
        cleaned_params = strategy_params
        _append_trade_log(task_id, {
            "timestamp": datetime.now(ZoneInfo("UTC")).isoformat(),
            "type": "error",
            "error": f"参数清理警告: {_format_error(e)}"
        })
    
    try:
        strategy = strategy_class(name=strategy_name, **cleaned_params)
    except Exception as e:
        meta["status"] = f"error: 策略初始化失败: {_format_error(e)}"
        _append_trade_log(task_id, {
            "timestamp": datetime.now(ZoneInfo("UTC")).isoformat(),
            "type": "error",
            "error": f"策略初始化失败: {_format_error(e)}"
        })
        return
    
    # 价格缓存和历史记录（存储在meta中以便实时访问）
    if "price_cache" not in meta:
        meta["price_cache"] = []
        meta["price_timestamps"] = []
    if "trade_records" not in meta:
        meta["trade_records"] = []  # 专门的买卖交易记录列表
    price_cache: List[float] = meta["price_cache"]
    price_timestamps: List[str] = meta["price_timestamps"]
    trade_records: List[dict] = meta["trade_records"]  # 实时维护的交易记录
    trade_history: List[dict] = []  # 临时历史记录（用于策略计算）
    last_signal_time: Optional[datetime] = None
    
    try:
        while True:
            # 检查是否暂停
            if _trade_task_paused.get(task_id, False):
                meta["status"] = "paused"
                await asyncio.sleep(1)
                continue
            
            now = datetime.now(ZoneInfo("UTC"))
            current_session = _get_session_name_cn(symbol, now)
            meta["current_session"] = current_session
            
            # 检查是否超时
            if stop_at and now >= stop_at:
                meta["status"] = "completed"
                break
            
            # 检查交易时段
            if sessions and current_session not in sessions:
                meta["status"] = "waiting"
                await asyncio.sleep(1)
                continue
            
            meta["status"] = "running"
            
            # 按价格采样间隔获取价格
            price_interval_seconds = _interval_to_seconds(price_interval)
            current_time_seconds = now.timestamp()
            
            # 获取最新价格
            try:
                q = longport_service.get_last_done_for_session(symbol, current_session, mode=mode)
                last_done = q.get("last_done")
                
                if last_done is not None:
                    # 根据股票代码选择对应的时区时间进行记录
                    now_local = _get_local_time(symbol, now)
                    
                    # 添加到缓存（限制大小）
                    price_cache.append(float(last_done))
                    price_timestamps.append(now_local.isoformat())
                    
                    # 确保缓存大小不超过max_cache_size
                    while len(price_cache) > max_cache_size:
                        price_cache.pop(0)
                    while len(price_timestamps) > max_cache_size:
                        price_timestamps.pop(0)
                    
                    # 确保两个列表长度一致
                    if len(price_cache) != len(price_timestamps):
                        min_len = min(len(price_cache), len(price_timestamps))
                        price_cache = price_cache[:min_len]
                        price_timestamps = price_timestamps[:min_len]
                        meta["price_cache"] = price_cache
                        meta["price_timestamps"] = price_timestamps
                    
                    # 记录价格采样（使用本地时区时间）
                    _append_trade_log(task_id, {
                        "timestamp": now_local.isoformat(),
                        "type": "price_sample",
                        "price": last_done,
                        "session": current_session,
                        "cache_size": len(price_cache)
                    })
            except Exception as e:
                # 使用本地时区时间记录错误
                now_local = _get_local_time(symbol, now)
                _append_trade_log(task_id, {
                    "timestamp": now_local.isoformat(),
                    "type": "error",
                    "error": f"获取价格失败: {_format_error(e)}"
                })
            
            # 按信号间隔运行策略产生信号
            signal_interval_seconds = _interval_to_seconds(signal_interval)
            should_generate_signal = False
            
            if last_signal_time is None:
                should_generate_signal = True
            else:
                elapsed = (now - last_signal_time).total_seconds()
                if elapsed >= signal_interval_seconds:
                    should_generate_signal = True
            
            if should_generate_signal and len(price_cache) >= 2:
                try:
                    # 使用本地时区时间用于信号和交易记录
                    now_local = _get_local_time(symbol, now)
                    
                    # 运行策略生成信号
                    current_index = len(price_cache) - 1
                    signal, strategy_info = strategy.generate_signal(price_cache, current_index, trade_history)
                    
                    # 记录信号
                    _append_trade_log(task_id, {
                        "timestamp": now_local.isoformat(),
                        "type": "strategy_signal",
                        "signal": signal.value,
                        "price": price_cache[current_index],
                        "strategy_info": strategy_info,
                        "cache_size": len(price_cache)
                    })
                    
                    # 如果是买卖信号，执行交易（这里可以扩展为实际下单）
                    if signal.value in ["buy", "sell"]:
                        trade_entry = {
                            "timestamp": now_local.isoformat(),
                            "type": "trade",
                            "trade_type": signal.value,
                            "price": price_cache[current_index],
                            "signal_info": strategy_info,
                            "session": current_session
                        }
                        trade_history.append(trade_entry)  # 用于策略计算
                        trade_records.append(trade_entry)  # 添加到专门的交易记录列表
                        _append_trade_log(task_id, trade_entry)  # 写入日志文件（用于持久化）
                        
                        # 更新实时指标
                        initial_cash = meta.get("initial_cash", 100000.0)
                        _update_trade_metrics(task_id, trade_records, initial_cash)
                    
                    last_signal_time = now
                except Exception as e:
                    # 使用本地时区时间记录错误
                    now_local = _get_local_time(symbol, now)
                    _append_trade_log(task_id, {
                        "timestamp": now_local.isoformat(),
                        "type": "error",
                        "error": f"策略执行失败: {_format_error(e)}"
                    })
            
            # 等待价格采样间隔
            await asyncio.sleep(price_interval_seconds)
            
    except asyncio.CancelledError:
        meta["status"] = "stopped"
        raise
    except Exception as e:
        meta["status"] = f"error: {_format_error(e)}"
        # 使用本地时区时间记录错误
        now_utc = datetime.now(ZoneInfo("UTC"))
        now_local = _get_local_time(symbol, now_utc)
        _append_trade_log(task_id, {
            "timestamp": now_local.isoformat(),
            "type": "error",
            "error": f"任务异常: {_format_error(e)}"
        })
    finally:
        _trade_task_handles.pop(task_id, None)

@app.post("/api/trade/create")
async def create_trade_task(req: TradeTaskCreateRequest):
    """创建实时交易任务"""
    try:
        # 基本校验
        if req.price_interval.value <= 0:
            raise HTTPException(status_code=400, detail="price_interval.value 必须为正整数")
        if req.signal_interval.value <= 0:
            raise HTTPException(status_code=400, detail="signal_interval.value 必须为正整数")
        if req.max_cache_size <= 0:
            raise HTTPException(status_code=400, detail="max_cache_size 必须为正整数")
        
        # 验证策略
        if req.strategy_name not in AVAILABLE_STRATEGIES:
            raise HTTPException(status_code=400, detail=f"策略 {req.strategy_name} 不存在")
        
        duration_delta = _duration_to_timedelta(req.duration)
        
        # 生成8位任务ID
        task_id = str(uuid.uuid4())[:8]
        started_at = datetime.now(ZoneInfo("UTC"))
        
        # 根据股票代码确定时区
        if _is_us_stock(req.symbol):
            timezone = "America/New_York"
        elif _is_hk_stock(req.symbol):
            timezone = "Asia/Hong_Kong"
        else:
            timezone = "America/New_York"
        
        info = TradeTaskInfo(
            task_id=task_id,
            symbol=req.symbol,
            mode=req.mode,
            strategy_name=req.strategy_name,
            strategy_params=req.strategy_params,
            sessions=req.sessions,
            duration=req.duration,
            price_interval=req.price_interval,
            signal_interval=req.signal_interval,
            max_cache_size=req.max_cache_size,
            start_time=started_at.isoformat(),
            status="running",
            file_path=_trade_file_path(task_id),
            timezone=timezone,
            current_session=None,
        )
        
        _trade_tasks[task_id] = {
            "symbol": req.symbol,
            "mode": req.mode,
            "strategy_name": req.strategy_name,
            "strategy_params": req.strategy_params,
            "sessions": req.sessions,
            "duration": req.duration,
            "duration_delta": duration_delta,
            "price_interval": req.price_interval,
            "signal_interval": req.signal_interval,
            "max_cache_size": req.max_cache_size,
            "started_at": started_at,
            "status": "running",
            "file_path": info.file_path,
            "price_cache": [],  # 初始化价格缓存
            "price_timestamps": [],  # 初始化时间戳缓存
            "trade_records": [],  # 初始化交易记录列表（只包含买卖交易）
            "initial_cash": 100000.0,  # 默认初始资金
        }
        _trade_task_paused[task_id] = False
        
        _write_trade_header(task_id, info)
        
        # 启动后台任务
        task = asyncio.create_task(_run_trade_task(task_id))
        _trade_task_handles[task_id] = task
        
        return {"task_id": task_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=_format_error(e))

@app.get("/api/trade/list")
async def list_trade_tasks():
    """获取所有交易任务列表"""
    summaries = []
    for task_id, meta in _trade_tasks.items():
        summaries.append({
            "task_id": task_id,
            "symbol": meta["symbol"],
            "mode": meta["mode"],
            "strategy_name": meta["strategy_name"],
            "sessions": meta["sessions"],
            "status": meta["status"],
            "started_at": meta["started_at"].isoformat(),
            "current_session": meta.get("current_session"),
        })
    return {"tasks": summaries, "count": len(summaries)}

@app.get("/api/trade/{task_id}")
async def get_trade_task(task_id: str):
    """获取交易任务详情 - 完全从内存缓存获取实时数据"""
    meta = _trade_tasks.get(task_id)
    if not meta:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    try:
        # 从meta构建配置信息（不从文件读取）
        config = {
            "task_id": task_id,
            "symbol": meta.get("symbol"),
            "mode": meta.get("mode"),
            "strategy_name": meta.get("strategy_name"),
            "strategy_params": meta.get("strategy_params", {}),
            "sessions": meta.get("sessions", []),
            "duration": meta.get("duration"),
            "price_interval": meta.get("price_interval"),
            "signal_interval": meta.get("signal_interval"),
            "max_cache_size": meta.get("max_cache_size", 1000),
            "start_time": meta.get("started_at").isoformat() if meta.get("started_at") else None,
            "status": meta.get("status", "unknown"),
        }
        
        # 只从内存缓存获取价格数据
        price_cache = meta.get("price_cache", [])
        price_timestamps = meta.get("price_timestamps", [])
        
        # 调试信息
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Task {task_id}: price_cache length={len(price_cache) if price_cache else 0}, price_timestamps length={len(price_timestamps) if price_timestamps else 0}")
        
        # 从内存缓存构建价格点
        latest_prices = []
        if price_cache and price_timestamps and len(price_cache) == len(price_timestamps):
            max_cache_size = meta.get("max_cache_size", 1000)
            # 取最近的数据（最多max_cache_size条）
            start_idx = max(0, len(price_cache) - max_cache_size)
            for i in range(start_idx, len(price_cache)):
                # 转换时间戳格式为字符串（从ISO格式转换为显示格式）
                timestamp_str = price_timestamps[i]
                try:
                    # 如果是ISO格式，转换为显示格式
                    if isinstance(timestamp_str, str):
                        if 'T' in timestamp_str or '+' in timestamp_str:
                            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                            timestamp_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception as e:
                    # 如果转换失败，保持原格式
                    pass
                
                price_value = price_cache[i]
                if price_value is not None:
                    latest_prices.append({
                        "timestamp": str(timestamp_str),
                        "price": float(price_value),
                        "session": meta.get("current_session", ""),
                    })
        
        # 直接从内存中的交易记录列表获取（只包含买卖交易，不包括持有信号）
        trade_records = meta.get("trade_records", [])
        
        # 转换为前端需要的格式，按时间降序
        trade_logs = []
        for record in reversed(trade_records):  # 反转列表使其按时间降序
            trade_logs.append({
                "timestamp": record.get("timestamp", ""),
                "type": record.get("type", "trade"),
                "trade_type": record.get("trade_type"),
                "price": record.get("price"),
                "signal_info": record.get("signal_info", {}),
                "session": record.get("session", ""),
            })
        
        # 如果current_session为None，尝试计算当前时段
        current_session = meta.get("current_session")
        if current_session is None and meta:
            symbol = meta.get("symbol")
            if symbol:
                try:
                    now = datetime.now(ZoneInfo("UTC"))
                    current_session = _get_session_name_cn(symbol, now)
                except Exception:
                    pass
        
        # 读取metrics（从日志文件第一行或实时计算）
        metrics = None
        try:
            path = _trade_file_path(task_id)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    first_line = f.readline().strip()
                    if first_line:
                        file_config = json.loads(first_line)
                        metrics = file_config.get("metrics")
        except Exception:
            pass
        
        # 如果文件中的metrics不存在或过期，实时计算
        if not metrics:
            trade_records = meta.get("trade_records", [])
            initial_cash = meta.get("initial_cash", 100000.0)
            metrics = _calculate_trade_metrics(trade_records, initial_cash)
        
        return {
            "config": config,
            "latest_points": latest_prices,
            "trade_logs": trade_logs,
            "count": len(latest_prices),
            "current_session": current_session,
            "metrics": metrics,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=_format_error(e))

@app.post("/api/trade/{task_id}/pause")
async def pause_trade_task(task_id: str):
    """暂停交易任务"""
    meta = _trade_tasks.get(task_id)
    if not meta:
        raise HTTPException(status_code=404, detail="任务不存在")
    if meta["status"] in ["stopped", "completed"]:
        raise HTTPException(status_code=400, detail="任务已停止或已完成，无法暂停")
    _trade_task_paused[task_id] = True
    meta["status"] = "paused"
    return {"message": "任务已暂停"}

@app.post("/api/trade/{task_id}/resume")
async def resume_trade_task(task_id: str):
    """恢复交易任务"""
    meta = _trade_tasks.get(task_id)
    if not meta:
        raise HTTPException(status_code=404, detail="任务不存在")
    if meta["status"] in ["stopped", "completed"]:
        raise HTTPException(status_code=400, detail="任务已停止或已完成，无法恢复")
    _trade_task_paused[task_id] = False
    # 状态会在_run_trade_task中自动更新为running
    return {"message": "任务已恢复"}

@app.post("/api/trade/{task_id}/stop")
async def stop_trade_task(task_id: str):
    """停止交易任务"""
    meta = _trade_tasks.get(task_id)
    if not meta:
        raise HTTPException(status_code=404, detail="任务不存在")
    handle = _trade_task_handles.get(task_id)
    if not handle:
        meta["status"] = "stopped"
        _trade_task_paused.pop(task_id, None)
        return {"message": "任务已停止"}
    try:
        handle.cancel()
        meta["status"] = "stopped"
        _trade_task_paused.pop(task_id, None)
        return {"message": "已发送停止指令"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=_format_error(e))

@app.delete("/api/trade/{task_id}")
async def delete_trade_task(task_id: str):
    """删除交易任务及其日志文件"""
    try:
        # 检查任务是否存在
        meta = _trade_tasks.get(task_id)
        if not meta:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 停止任务（如果正在运行）
        if meta.get("status") == "running":
            meta["status"] = "stopped"
            task_handle = _trade_task_handles.get(task_id)
            if task_handle:
                task_handle.cancel()
        
        # 从内存中删除
        _trade_tasks.pop(task_id, None)
        _trade_task_handles.pop(task_id, None)
        _trade_task_paused.pop(task_id, None)
        
        # 删除日志文件
        log_file_path = _trade_file_path(task_id)
        if os.path.exists(log_file_path):
            os.remove(log_file_path)
        
        return {"message": "任务已删除"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=_format_error(e))

