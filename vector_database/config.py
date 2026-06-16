"""
向量数据库配置
支持 FAISS 和 Milvus 两种方案
"""

# 通用配置
EMBEDDING_DIM = 192          # 声纹向量维度 (ECAPA-TDNN 输出192维)
INDEX_TYPE = "faiss"         # 可选: "faiss", "milvus"

# FAISS 配置
FAISS = {
    "index_path": "vector_database/faiss_index/celebrity.index",
    "metric": "cosine",                      # 距离度量方式
    "index_factory": "IVF100,Flat",          # IVF 索引参数
    "nprobe": 10,                            # 搜索时探针数
}

# Milvus 配置
MILVUS = {
    "host": "127.0.0.1",
    "port": "19530",
    "collection_name": "celebrity_voices",
    "metric_type": "COSINE",
}
