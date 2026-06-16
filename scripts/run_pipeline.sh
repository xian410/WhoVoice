#!/bin/bash
# WhoVoice 全流程一键运行脚本
# 按顺序执行: 爬取 -> 预处理 -> 向量库构建

set -e

echo "========================================"
echo "  WhoVoice 全流程处理"
echo "========================================"

# 1. 爬取数据
echo ""
echo "[1/3] 开始爬取语音数据..."
python scripts/run_crawler.py --max 5

# 2. 预处理
echo ""
echo "[2/3] 开始预处理..."
python scripts/run_preprocessing.py

# 3. 构建向量索引
echo ""
echo "[3/3] 构建向量索引..."
python -c "
from vector_database.build_index import VectorIndexBuilder
print('向量索引构建准备就绪')
# TODO: 加载 embedding 并构建索引
"

echo ""
echo "========================================"
echo "  全流程处理完成!"
echo "========================================"
