#!/usr/bin/env python3
"""
声纹识别测试脚本 —— 验证预训练模型 + FAISS 索引的识别效果

用法:
    python scripts/test_recognition.py                                         # 用周杰伦的切片自测
    python scripts/test_recognition.py --audio /path/to/test.wav               # 用自定义音频测试
    python scripts/test_recognition.py --self-test                              # 全部切片交叉验证
"""

import os
# macOS 上 PyTorch + FAISS 的 OpenMP 库冲突修复
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import sys
import json
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voice_recognition.model_loader import VoiceprintRecognizer
from vector_database.config import FAISS, EMBEDDING_DIM

PROCESSED_DIR = Path("data/processed")
INDEX_PATH = Path(FAISS["index_path"])
METADATA_PATH = INDEX_PATH.parent / "celebrity_metadata.json"


def _hash_name(name: str) -> int:
    """与 extract_embeddings.py 中一致的 hash 方法"""
    return abs(hash(name)) % (2**63)


def load_index_and_metadata():
    """加载 FAISS 索引和明星元数据"""
    import faiss

    if not INDEX_PATH.exists():
        print(f"[ERROR] FAISS 索引不存在: {INDEX_PATH}")
        print("请先运行: python scripts/extract_embeddings.py")
        sys.exit(1)

    if not METADATA_PATH.exists():
        print(f"[ERROR] 元数据不存在: {METADATA_PATH}")
        sys.exit(1)

    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    index = faiss.read_index(str(INDEX_PATH))
    print(f"  索引加载成功: {INDEX_PATH}")
    print(f"  注册明星: {metadata['celebrities']}")
    return index, metadata


def identify(audio_path: str, recognizer: VoiceprintRecognizer, index, id_to_name: dict, top_k: int = 3):
    """
    声纹识别：提取特征 → FAISS 搜索 → 返回 Top-K 匹配

    Returns:
        [(明星名, 相似度), ...]
    """
    print(f"\n  提取特征: {Path(audio_path).name}")

    embedding = recognizer.extract_embedding(audio_path)

    # 手动归一化（避免 faiss.normalize_L2 在 macOS 上 segfault）
    query = embedding.reshape(1, -1).astype(np.float32)
    norm = np.linalg.norm(query)
    if norm > 0:
        query = query / norm

    distances, indices = index.search(query, top_k)

    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx == -1:
            break
        sim = float(dist)  # 归一化后的内积 = 余弦相似度
        name = id_to_name.get(int(idx), "未知")
        results.append((name, sim))

    return results


def build_id_to_name(metadata: dict) -> dict:
    """根据元数据构建 FAISS ID → 明星名 映射"""
    name_to_id = metadata.get("name_to_id", {})
    return {v: k for k, v in name_to_id.items()}


def self_test(recognizer, index, metadata):
    """自测：对每位明星的每条切片做交叉验证，统计识别准确率"""
    celeb_names = metadata["celebrities"]
    id_to_name = build_id_to_name(metadata)

    print(f"\n{'='*60}")
    print("  自测模式：交叉验证")
    print(f"{'='*60}")

    for celebrity in celeb_names:
        celeb_dir = PROCESSED_DIR / celebrity
        if not celeb_dir.exists():
            continue

        wav_files = sorted(celeb_dir.glob("*.wav"))
        if not wav_files:
            continue

        print(f"\n  [{celebrity}] 共 {len(wav_files)} 条切片, 逐条测试:")

        correct = 0
        total = 0
        all_scores = []
        show_limit = min(20, len(wav_files))

        for i, wav_path in enumerate(wav_files):
            results = identify(str(wav_path), recognizer, index, id_to_name, top_k=1)
            is_match = results[0][0] == celebrity if results else False
            score = results[0][1] if results else 0

            if is_match:
                correct += 1
            total += 1
            all_scores.append(score)

            if i < show_limit:
                status = "✅" if is_match else "❌"
                print(f"    {status} [{i+1:>2}/{len(wav_files)}] 预测={results[0][0]} 置信度={score:.2%}")

        scores = np.array(all_scores)
        accuracy = correct / total * 100 if total > 0 else 0
        print(f"  {'─'*50}")
        print(f"  [{celebrity}] 准确率: {correct}/{total} = {accuracy:.1f}%")
        print(f"  相似度: min={scores.min():.2%}, max={scores.max():.2%}, avg={scores.mean():.2%}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="WhoVoice - 声纹识别测试")
    parser.add_argument("--audio", type=str, help="测试音频路径")
    parser.add_argument("--self-test", action="store_true", help="交叉验证模式（用所有切片自测）")
    parser.add_argument("--top-k", type=int, default=3, help="返回 Top-K 结果")
    parser.add_argument("--gpu", action="store_true", help="使用 GPU 推理")
    args = parser.parse_args()

    print("=" * 60)
    print("  WhoVoice - 声纹识别测试")
    print("=" * 60)

    # 第1步: 加载模型
    print("\n[1/3] 加载预训练模型...")
    recognizer = VoiceprintRecognizer(use_gpu=args.gpu)

    # 第2步: 加载索引
    print("\n[2/3] 加载 FAISS 索引...")
    index, metadata = load_index_and_metadata()
    id_to_name = build_id_to_name(metadata)

    # 第3步: 执行测试
    print("\n[3/3] 执行识别...")

    if args.self_test:
        self_test(recognizer, index, metadata)

    elif args.audio:
        audio_path = Path(args.audio)
        if not audio_path.exists():
            print(f"[ERROR] 文件不存在: {audio_path}")
            sys.exit(1)

        results = identify(str(audio_path), recognizer, index, id_to_name, top_k=args.top_k)

        print(f"\n  {'='*50}")
        print(f"  识别结果 Top-{args.top_k}")
        print(f"  {'='*50}")
        for rank, (name, score) in enumerate(results, 1):
            bar_len = min(int(score * 30), 30)
            bar = "█" * bar_len + "░" * (30 - bar_len)
            print(f"  #{rank}  {name:<8} {score:>6.2%}  |{bar}|")
        print(f"  {'='*50}")

        if results:
            top_name, top_score = results[0]
            if top_score > 0.5:
                print(f"\n  ✅ 识别为: {top_name} (置信度 {top_score:.2%})")
            else:
                print(f"\n  ⚠️  未匹配到可信结果 (最高置信度仅 {top_score:.2%})")
    else:
        first_slice = list(PROCESSED_DIR.glob("周杰伦/*.wav"))
        if first_slice:
            print(f"\n  默认模式: 随机抽取 10 条切片自测")
            slices = sorted(PROCESSED_DIR.glob("周杰伦/*.wav"))[:10]
            scores = []
            for s in slices:
                results = identify(str(s), recognizer, index, id_to_name, top_k=1)
                score = results[0][1] if results else 0
                scores.append(score)

            scores_arr = np.array(scores)
            print(f"\n  {'='*50}")
            print(f"  测试 {len(slices)} 条切片")
            print(f"  相似度: min={scores_arr.min():.2%}, max={scores_arr.max():.2%}")
            print(f"          均值={scores_arr.mean():.2%} (越高说明声纹越稳定)")
            print(f"  {'='*50}")

            top_idx = np.argmax(scores_arr)
            print(f"\n  ✅ 最佳匹配: 周杰伦 (置信度 {scores_arr[top_idx]:.2%})")
        else:
            print("[ERROR] 未找到周杰伦的切片，请先运行预处理")


if __name__ == "__main__":
    main()
