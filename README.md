# Quantopia

Quantopia是我个人launch的一个量化工具平台，希望可以集成数据、策略、实验、交易为一体，同时完全拥抱AI范式，希望将AI的能力enroll进所有的数据、交易、策略的环节，探索下一代量化交易的工程范式。

## 特别说明

本项目为我个人开发+AI辅助，其中可能存在不可靠的代码片段，通常用于实验作用，用于实际交易请慎重。

实盘数据以及交易接口目前均使用长桥证券API，暂未支持其他平台。

## 项目结构

```
Quantopia/
├── backend/          # 后端目录（Python + FastAPI）
├── frontend/         # 前端目录（React + TypeScript + Vite）
└── README.md
```


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
python -m src.quantopia
# 或使用脚本
./run.sh
```

后端服务将在 http://localhost:15000 启动  
API文档：http://localhost:15000/docs

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

## 功能路标

### 数据管理
- [x] 支持爬取实盘数据
- [x] 生成模拟股票数据（丰富的参数配置）
- [x] 数据可视化
- [x] 查看数据详情和元数据

### 策略库
- [x] MA策略（移动平均策略）
- [x] 策略参数配置和说明

### 回测系统
- [x] 创建回测任务
- [x] 详细的回测统计指标
- [x] 完整的交易日志
- [x] 可视化回测结果（图表上标记买卖点）
- [x] AI结果分析

### 量化交易
- [ ] 待设计

## 详细文档

- [后端文档](backend/README.md)
- [前端文档](frontend/README.md)

## License

本项目采用 **GNU Affero General Public License v3.0 (AGPL-3.0)** 授权。

您可以自由复制、分发、研究和修改本软件，但**必须**：
- **开源**：任何衍生项目都必须采用相同的 AGPLv3 许可证，并公开源代码。
- **网络服务条款**：如果您对外提供本软件的服务（如SaaS），也需开放完整源代码。
- **保留原始版权声明及许可证文件**。

完整协议内容请参阅：[https://www.gnu.org/licenses/agpl-3.0.html](https://www.gnu.org/licenses/agpl-3.0.html)

如需商业授权或有其他需求，请联系作者协商。



