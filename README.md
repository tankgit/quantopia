# Quantopia

量化交易实验系统

## 作者
Tank

## 项目简介

Quantopia是一个量化交易实验系统，提供完整的股票数据生成、策略回测和可视化功能。系统分为前后端两部分，采用现代化的技术栈构建。

## 项目结构

```
Quantopia/
├── backend/          # 后端目录（Python + FastAPI）
├── frontend/         # 前端目录（React + TypeScript + Vite）
└── README.md
```

## 技术栈

### 后端
- Python 3.10+
- FastAPI
- uv (包管理)
- NumPy

### 前端
- React 19
- TypeScript
- Vite
- TailwindCSS
- Recharts (图表)
- React Query (数据管理)
- React Router (路由)

## 快速开始

### 后端启动

1. 安装uv（如果尚未安装）
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. 安装后端依赖
```bash
cd backend
uv pip install -e .
```

3. 启动后端服务
```bash
python -m quantopia
# 或使用脚本
./run.sh
```

后端服务将在 http://localhost:8000 启动  
API文档：http://localhost:8000/docs

### 前端启动

1. 安装依赖
```bash
cd frontend
npm install
```

2. 启动开发服务器
```bash
npm run dev
```

前端应用将在 http://localhost:5173 启动

## 功能特性

### 数据管理
- ✅ 生成模拟股票数据（丰富的参数配置）
- ✅ 查看所有数据列表
- ✅ 数据可视化（折线图/K线图）
- ✅ 查看数据详情和元数据

### 策略库
- ✅ MA策略（移动平均策略）
- ✅ 策略参数配置和说明

### 回测系统
- ✅ 创建回测任务
- ✅ 详细的回测统计指标
- ✅ 完整的交易日志
- ✅ 可视化回测结果（图表上标记买卖点）

### 界面设计
- ✅ 现代化的深色主题
- ✅ 响应式布局
- ✅ 流畅的交互体验
- ✅ 清晰的数据可视化

## 详细文档

- [后端文档](backend/README.md)
- [前端文档](frontend/README.md)

## License

待定

