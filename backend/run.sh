#!/bin/bash
# 启动脚本

# 检查uv是否安装
if ! command -v uv &> /dev/null
then
    echo "uv 未安装，请先安装 uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# 安装依赖（如果尚未安装）
echo "安装依赖..."
uv pip install -e .

# 启动服务
echo "启动服务..."
python -m quantopia

