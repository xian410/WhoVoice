"""
向量索引构建工具
将明星声纹向量导入 FAISS 或 Milvus 向量库
"""

import numpy as np
from pathlib import Path
from typing import List, Optional, Tuple

import json
from vector_database.config import EMBEDDING_DIM, INDEX_TYPE, FAISS

METADATA_PATH = Path(FAISS["index_path"]).parent / "celebrity_metadata.json"

# 从哈希到名字的反向映射缓存
_NAME_BY_HASH = {}


def _hash_name(name: str) -> int:
    """使用确定性哈希（MD5），确保跨进程一致"""
    import hashlib
    h = hashlib.md5(name.encode("utf-8")).hexdigest()
    return abs(int(h, 16)) % (2 ** 63)


def _load_metadata() -> dict:
    """加载现有元数据"""
    if METADATA_PATH.exists():
        with open(METADATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"celebrities": [], "name_to_id": {}}


def _save_metadata(celeb_names: list, dim: int):
    """保存元数据"""
    METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "celebrities": celeb_names,
        "embedding_dim": int(dim),
        "num_celebrities": len(celeb_names),
        "model_type": "cam++",
        "index_path": str(FAISS["index_path"]),
        "name_to_id": {name: _hash_name(name) for name in celeb_names},
    }
    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"  元数据已保存: {METADATA_PATH}")


def get_existing_ids() -> set:
    """获取已在 FAISS 索引中的明星名集合"""
    meta = _load_metadata()
    return set(meta.get("celebrities", []))


class VectorIndexBuilder:
    """向量索引构建器"""

    def __init__(self, index_type: str = INDEX_TYPE, dimension: int = EMBEDDING_DIM):
        self.index_type = index_type
        self.dimension = dimension
        self.index = None

    def build_faiss(self, embeddings: np.ndarray, ids: Optional[List[str]] = None) -> object:
        """
        构建 FAISS 索引
        Args:
            embeddings: 声纹向量矩阵 (N, D)
            ids: 说话人ID列表
        Returns:
            FAISS 索引对象
        """
        import faiss

        dim = embeddings.shape[1]
        n_vectors = embeddings.shape[0]

        # 归一化后内积 = 余弦相似度
        faiss.normalize_L2(embeddings)

        # 小数据集用 Flat（暴力搜索），大数据集用 IVF
        if n_vectors < 10000:
            index = faiss.index_factory(dim, "Flat", faiss.METRIC_INNER_PRODUCT)
        else:
            n_centroids = min(int(n_vectors ** 0.5), 100)
            index = faiss.index_factory(dim, f"IVF{n_centroids},Flat", faiss.METRIC_INNER_PRODUCT)
            index.train(embeddings)

        if ids is not None:
            id_array = np.array([_hash_name(i) for i in ids], dtype=np.int64)
            index = faiss.IndexIDMap(index)
            index.add_with_ids(embeddings, id_array)
        else:
            index.add(embeddings)

        self.index = index
        return index

    def add_to_faiss(self, embeddings: np.ndarray, celeb_names: List[str],
                     index_path: str = FAISS["index_path"]) -> object:
        """
        增量添加明星到现有 FAISS 索引（无需重新处理已有数据）
        Args:
            embeddings: 新明星的声纹向量矩阵 (M, D)
            celeb_names: 新明星名字列表
            index_path: 现有索引路径
        Returns:
            FAISS 索引对象
        """
        import faiss

        # 加载现有索引
        index_path = Path(index_path)
        if index_path.exists():
            self.index = faiss.read_index(str(index_path))
            print(f"  已加载现有索引: {index_path} ({self.index.ntotal} 个向量)")
        else:
            print(f"  未找到现有索引，创建新索引")
            self.index = faiss.index_factory(self.dimension, "Flat", faiss.METRIC_INNER_PRODUCT)
            self.index = faiss.IndexIDMap(self.index)

        # 归一化新向量
        faiss.normalize_L2(embeddings)

        # 生成哈希ID
        id_array = np.array([_hash_name(n) for n in celeb_names], dtype=np.int64)

        # 添加到索引
        self.index.add_with_ids(embeddings, id_array)
        print(f"  新增 {len(celeb_names)} 个向量，索引总数: {self.index.ntotal}")

        # 保存
        faiss.write_index(self.index, str(index_path))
        print(f"  索引已保存: {index_path}")

        # 更新元数据
        meta = _load_metadata()
        existing = set(meta.get("celebrities", []))
        existing.update(celeb_names)
        _save_metadata(list(existing), self.dimension)

        return self.index

    def save_faiss(self, save_path: str = FAISS["index_path"]):
        """保存 FAISS 索引到磁盘"""
        if self.index is None:
            raise RuntimeError("索引为空，请先构建索引")

        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)

        import faiss
        faiss.write_index(self.index, str(save_path))
        print(f"FAISS 索引已保存到: {save_path}")

    def load_faiss(self, load_path: str = FAISS["index_path"]):
        """从磁盘加载 FAISS 索引"""
        import faiss
        self.index = faiss.read_index(load_path)
        print(f"FAISS 索引已从 {load_path} 加载")
        return self.index

    def search(self, query: np.ndarray, top_k: int = 5) -> Tuple[np.ndarray, np.ndarray]:
        """
        搜索最相似的向量
        Args:
            query: 查询向量 (D,)
            top_k: 返回 Top-K 结果
        Returns:
            (distances, indices)
        """
        if self.index is None:
            raise RuntimeError("索引未加载，请先构建或加载索引")

        import faiss
        query = query.reshape(1, -1).astype(np.float32)
        faiss.normalize_L2(query)

        distances, indices = self.index.search(query, top_k)
        return distances[0], indices[0]
