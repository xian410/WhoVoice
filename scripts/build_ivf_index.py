"""
构建 IVF_FLAT 索引用于 Feder 可视化
读取现有的 FlatIP 索引和向量，创建一个 IVF_FLAT 索引
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import faiss
import json

# 路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDEX_DIR = PROJECT_ROOT / "vector_database" / "faiss_index"
META_PATH = INDEX_DIR / "celebrity_metadata.json"
FLAT_INDEX_PATH = INDEX_DIR / "celebrity.index"
IVF_INDEX_PATH = INDEX_DIR / "celebrity_ivf.index"

# 加载元数据
with open(META_PATH, "r", encoding="utf-8") as f:
    meta = json.load(f)
celeb_names = meta["celebrities"]
dim = meta["embedding_dim"]
print(f"Celebrities: {len(celeb_names)}, dim: {dim}")

# 加载 FlatIP 索引
flat_index = faiss.read_index(str(FLAT_INDEX_PATH))
print(f"Flat index type: {type(flat_index).__name__}, ntotal: {flat_index.ntotal}")

# 如果 Flat 索引有 vectors 属性，可以直接提取
# 否则需要从 embeddings_npy 文件重建
vectors_dir = INDEX_DIR / "embeddings_npy"

all_vectors = []
all_ids = []

# 方法1：尝试从 Flat 索引提取向量
# IndexFlatIP has `xb` attribute with raw vectors
try:
    if hasattr(flat_index, 'xb'):
        vectors = faiss.vector_float_to_array(flat_index.xb)
        vectors = vectors.reshape(-1, dim)
        print(f"Extracted {len(vectors)} vectors from flat index (xb)")
        all_vectors = vectors
    elif hasattr(flat_index, 'reconstruct'):
        vectors = np.zeros((flat_index.ntotal, dim), dtype=np.float32)
        for i in range(flat_index.ntotal):
            flat_index.reconstruct(i, vectors[i])
        print(f"Reconstructed {len(vectors)} vectors from flat index")
        all_vectors = vectors
    else:
        raise AttributeError("Cannot extract vectors")
except Exception as e:
    print(f"Cannot extract vectors from flat index: {e}")
    print("Falling back to embeddings_npy files...")
    # 从 embeddings_npy 文件加载
    for name in celeb_names:
        npy_path = vectors_dir / f"{name}.npy"
        if npy_path.exists():
            vec = np.load(str(npy_path))
            # Average all embeddings for this celebrity
            if vec.ndim > 1:
                vec = vec.mean(axis=0)
            all_vectors.append(vec)
        else:
            print(f"Warning: {name}.npy not found")
    all_vectors = np.array(all_vectors, dtype=np.float32)
    print(f"Loaded {len(all_vectors)} vectors from npy files")

assert len(all_vectors) == len(celeb_names), f"Vector count mismatch: {len(all_vectors)} vs {len(celeb_names)}"

# 归一化
faiss.normalize_L2(all_vectors)

# 构建 IVF_FLAT 索引
nlist = min(128, len(all_vectors) // 5)  # ~5 vectors per cluster
if nlist < 2:
    nlist = 2
print(f"Building IVF_FLAT with nlist={nlist}")

quantizer = faiss.IndexFlatIP(dim)  # 使用内积作为距离度量
ivf_index = faiss.IndexIVFFlat(quantizer, dim, nlist, faiss.METRIC_INNER_PRODUCT)

# 训练
print("Training...")
ivf_index.train(all_vectors)

# 添加向量
print("Adding vectors...")
ivf_index.add(all_vectors)
print(f"IVF index ntotal: {ivf_index.ntotal}")

# 保存
faiss.write_index(ivf_index, str(IVF_INDEX_PATH))
print(f"IVF index saved to {IVF_INDEX_PATH}")

# 验证
verify = faiss.read_index(str(IVF_INDEX_PATH))
print(f"Verified: {verify.ntotal} vectors, nlist={verify.nlist}, type={type(verify).__name__}")
print("Done!")
