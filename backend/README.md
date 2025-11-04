# Quantopia Backend

## 项目结构

```
backend/
├── src/
│   └── quantopia/
│       ├── __init__.py
│       ├── data_generator.py    # 数据生成模块
│       ├── strategy.py           # 策略模块
│       ├── logger.py             # 日志模块
│       ├── backtest.py           # 回测模块
│       ├── api.py                # API接口模块
│       └── __main__.py           # 主入口
├── stock_data/
│   └── generate/                 # 生成的数据文件存储目录
├── logs/                         # 日志文件存储目录
├── pyproject.toml                # 项目配置和依赖
└── README.md
```

## 安装和运行

### 使用 uv 安装依赖

```bash
cd backend
uv pip install -e .
```

### 运行API服务

```bash
python -m quantopia
```

或者使用uvicorn直接运行：

```bash
uvicorn quantopia.api:app --host 0.0.0.0 --port 8000 --reload
```

API文档会自动生成在：http://localhost:8000/docs

## API接口说明

### 数据相关接口

1. **POST /api/data/generate** - 生成模拟股票数据
2. **GET /api/data/list** - 获取所有模拟生成数据列表
3. **GET /api/data/{file_id}** - 获取某个生成的模拟数据

### 回测相关接口

1. **POST /api/backtest/create** - 创建新的回测
2. **GET /api/backtest/list** - 获取所有回测列表
3. **GET /api/backtest/{run_id}** - 获取某个回测详情

## 模块说明

### 数据生成模块 (data_generator.py)
- 生成模拟股票价格数据
- 支持丰富的参数控制（趋势、波动性等）
- 数据以文本文件格式存储，包含元数据

### 策略模块 (strategy.py)
- 提供策略基类 `BaseStrategy`
- 实现MA策略 `MAStrategy`（移动平均策略）
- 支持买卖信号生成

### 回测模块 (backtest.py)
- 回测引擎，执行策略回测
- 计算详细的回测统计指标
- 与日志模块集成

### 日志模块 (logger.py)
- 记录回测运行的所有细节
- 包括策略信号、交易行为等
- 以JSON格式存储日志

### API接口模块 (api.py)
- 基于FastAPI构建RESTful API
- 提供完整的CRUD操作接口

