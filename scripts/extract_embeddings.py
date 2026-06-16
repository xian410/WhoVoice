#!/usr/bin/env python3
"""
批量提取声纹特征 + 构建 FAISS 向量索引

流程:
    预处理后的切片音频 → 预训练模型提取 embedding → 每个明星平均 → FAISS 索引

用法:
    python scripts/extract_embeddings.py                        # 提取所有明星
    python scripts/extract_embeddings.py --celebrity 周杰伦     # 提取单个
"""

import sys
import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice_recognition.model_loader import VoiceprintRecognizer
from vector_database.build_index import VectorIndexBuilder, get_existing_ids
from vector_database.config import FAISS, EMBEDDING_DIM

PROCESSED_DIR = Path("data/processed")
INDEX_DIR = Path(FAISS["index_path"]).parent
METADATA_PATH = INDEX_DIR / "celebrity_metadata.json"


def collect_slices(celebrity: str = None) -> Dict[str, List[str]]:
    """
    收集已预处理好的音频切片
    Returns:
        { "周杰伦": ["/path/to/slice1.wav", ...], ... }
    """
    celeb_data = {}

    if not PROCESSED_DIR.exists():
        print(f"[ERROR] 预处理目录不存在: {PROCESSED_DIR}")
        print("请先运行: python scripts/run_preprocessing.py")
        return celeb_data

    celeb_dirs = [PROCESSED_DIR / celebrity] if celebrity else sorted(PROCESSED_DIR.iterdir())

    for celeb_dir in celeb_dirs:
        if not celeb_dir.is_dir():
            continue
        wav_files = sorted(celeb_dir.glob("*.wav"))
        if wav_files:
            celeb_data[celeb_dir.name] = [str(f.absolute()) for f in wav_files]
            print(f"  {celeb_dir.name}: {len(wav_files)} 个切片")

    return celeb_data


def extract_embeddings(
    recognizer: VoiceprintRecognizer,
    celeb_data: Dict[str, List[str]],
) -> Tuple[Dict[str, np.ndarray], np.ndarray, List[str]]:
    """
    提取每个明星所有切片的声纹 embedding，并计算平均向量

    Returns:
        avg_embeddings: { "周杰伦": np.array(192,), ... }
        embedding_matrix: np.array(N, 192)  # N个明星
        celeb_names: ["周杰伦", ...]
    """
    avg_embeddings = {}
    all_embeddings = []
    all_names = []

    for celebrity, audio_paths in celeb_data.items():
        print(f"\n  提取 [{celebrity}] 声纹特征 ({len(audio_paths)} 条切片)...")
        slice_embeddings = []

        for i, path in enumerate(audio_paths):
            try:
                emb = recognizer.extract_embedding(path)
                slice_embeddings.append(emb)
            except Exception as e:
                print(f"    [{i+1}/{len(audio_paths)}] 失败: {Path(path).name} - {e}")
                continue

            if (i + 1) % 50 == 0:
                print(f"    [{i+1}/{len(audio_paths)}] 已完成")

        if slice_embeddings:
            # 取所有切片 embedding 的平均值作为该明星的声纹中心
            avg_emb = np.mean(slice_embeddings, axis=0)
            avg_emb = avg_emb / np.linalg.norm(avg_emb)  # 归一化
            avg_embeddings[celebrity] = avg_emb
            all_embeddings.append(avg_emb)
            all_names.append(celebrity)
            print(f"    ✅ 完成! 平均向量维度: {avg_emb.shape}")
        else:
            print(f"    ❌ 未提取到有效特征")

    if not all_embeddings:
        print("[ERROR] 没有提取到任何声纹特征")
        return {}, np.array([]), []

    embedding_matrix = np.array(all_embeddings, dtype=np.float32)
    return avg_embeddings, embedding_matrix, all_names


def build_faiss_index(embedding_matrix: np.ndarray, celeb_names: List[str], append: bool = False):
    """构建或增量更新 FAISS 索引"""
    print(f"\n{'='*50}")
    if append:
        print("增量更新 FAISS 索引（保留已有明星，仅添加新明星）...")
    else:
        print("构建 FAISS 向量索引...")
    print(f"  明星数量: {len(celeb_names)}")
    print(f"  向量维度: {embedding_matrix.shape[1]}")

    builder = VectorIndexBuilder(dimension=EMBEDDING_DIM)

    if append:
        # 增量添加（加载已有索引，添加新向量，自动保存）
        builder.add_to_faiss(embeddings=embedding_matrix, celeb_names=celeb_names)
    else:
        # 全新构建
        builder.build_faiss(embeddings=embedding_matrix, ids=celeb_names)
        builder.save_faiss()

        # 保存元数据
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        metadata = {
            "celebrities": celeb_names,
            "embedding_dim": int(EMBEDDING_DIM),
            "num_celebrities": len(celeb_names),
            "model_type": "cam++",
            "index_path": str(FAISS["index_path"]),
            "name_to_id": {name: abs(hash(name)) % (2**63) for name in celeb_names},
        }
        with open(METADATA_PATH, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        print(f"  索引保存: {FAISS['index_path']}")
        print(f"  元数据:   {METADATA_PATH}")

    print(f"{'='*50}")

    # 小规模时打印相似度矩阵（调试用）
    if not append and len(celeb_names) <= 30:
        print("\n明星声纹余弦相似度矩阵:")
        print(f"{'':>12}", end="")
        for name in celeb_names:
            print(f"{name:>10}", end="")
        print()
        for i, name_i in enumerate(celeb_names):
            print(f"{name_i:>10}", end="")
            for j in range(len(celeb_names)):
                sim = float(np.dot(embedding_matrix[i], embedding_matrix[j]))
                print(f"{sim:>10.4f}", end="")
            print()
    else:
        print(f"\n(明星数 > 30 或增量模式, 跳过相似度矩阵打印)")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="WhoVoice - 批量提取声纹特征 + FAISS 索引")
    parser.add_argument("--celebrity", type=str, help="指定单个明星（处理所有则不指定）")
    parser.add_argument("--model", type=str, default="cam++", choices=["cam++", "ecapa_tdnn", "eres2net"])
    parser.add_argument("--gpu", action="store_true", help="使用 GPU 推理")
    parser.add_argument("--append", action="store_true",
                        help="增量模式：只处理新明星，添加到已有FAISS索引（无需重新处理已有数据）")
    args = parser.parse_args()

    print("=" * 60)
    print("  WhoVoice - 声纹特征提取 + 向量索引构建")
    print("=" * 60)

    # 第1步: 加载预训练模型
    print("\n[1/4] 加载预训练模型...")
    recognizer = VoiceprintRecognizer(model_type=args.model, use_gpu=args.gpu)

    # 第2步: 收集切片
    print("\n[2/4] 收集预处理切片...")
    celeb_data = collect_slices(args.celebrity)
    if not celeb_data:
        sys.exit(1)

    # 增量模式：过滤掉已在FAISS索引中的明星
    if args.append:
        existing = get_existing_ids()
        new_celebrities = {k: v for k, v in celeb_data.items() if k not in existing}
        skipped = len(celeb_data) - len(new_celebrities)
        if skipped > 0:
            print(f"  跳过 {skipped} 位已存在的明星（FAISS索引中已有）")
        if not new_celebrities:
            print("  没有新明星需要处理 ✅")
            return
        celeb_data = new_celebrities

    total_slices = sum(len(v) for v in celeb_data.values())
    print(f"  共 {len(celeb_data)} 位明星, {total_slices} 条切片")

    # 第3步: 提取声纹特征
    print("\n[3/4] 提取声纹特征...")
    avg_embeddings, embedding_matrix, celeb_names = extract_embeddings(recognizer, celeb_data)
    if embedding_matrix.size == 0:
        sys.exit(1)

    # 第4步: 构建/更新 FAISS 索引
    print("\n[4/4] 构建向量索引...")
    build_faiss_index(embedding_matrix, celeb_names, append=args.append)

    print(f"\n{'='*60}")
    print(f"  ✅ 全部完成! 已注册 {len(celeb_names)} 位明星的声纹")
    print(f"  {'='*60}")
    print(f"  使用以下命令启动识别:")
    print(f"    python backend/manage.py runserver")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
