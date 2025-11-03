# Quantopia Frontend

量化交易实验系统前端应用

## 技术栈

- React 19
- TypeScript
- Vite
- TailwindCSS
- Recharts (图表库)
- React Query (数据获取)
- React Router (路由)

## 安装和运行

### 安装依赖

```bash
npm install
```

### 开发模式

```bash
npm run dev
```

应用将在 http://localhost:5173 启动

### 构建生产版本

```bash
npm run build
```

### 预览生产版本

```bash
npm run preview
```

## 环境变量

创建 `.env` 文件（已包含在项目中）：

```
VITE_API_URL=http://localhost:8000
```

## 功能模块

### 1. 数据管理
- 查看所有生成的模拟数据列表
- 生成新的模拟数据（可配置参数）
- 数据可视化（折线图/K线图）
- 查看数据详情和元数据

### 2. 策略库
- 查看所有可用策略
- 查看策略详细说明和参数

### 3. 回测管理
- 创建新的回测任务
- 选择数据文件和策略
- 配置回测参数
- 查看所有回测记录

### 4. 回测详情
- 查看详细的回测统计指标
- 可视化价格走势和交易点
- 查看完整的交易日志
- 切换不同的图表类型

## 项目结构

```
frontend/
├── src/
│   ├── components/        # 可复用组件
│   │   ├── Layout.tsx     # 主布局组件
│   │   └── DataChart.tsx  # 数据图表组件
│   ├── pages/            # 页面组件
│   │   ├── DataManagement.tsx
│   │   ├── Strategies.tsx
│   │   ├── BacktestManagement.tsx
│   │   └── BacktestDetail.tsx
│   ├── services/         # API服务
│   │   ├── api.ts
│   │   └── strategies.ts
│   ├── types/            # TypeScript类型定义
│   │   └── index.ts
│   ├── App.tsx           # 主应用组件
│   └── main.tsx          # 入口文件
├── package.json
└── vite.config.ts
```
