#!/usr/bin/env python3
"""GPU提取 (限制70%显存) + 存npy + CPU建索引"""
import sys, os, json, time, gc
from pathlib import Path
os.environ["INFERENCE_DEVICE"] = "gpu"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if os.name == "nt":
    sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import torch

RAW_DIR = Path("data/raw")
INDEX_FILE = Path("vector_database/faiss_index/celebrity.index")
META_FILE = Path("vector_database/faiss_index/celebrity_metadata.json")
NPY_DIR = Path("vector_database/faiss_index/embeddings_npy")

def main():
    print("=" * 60)
    print("  WhoVoice - GPU(70%显存限制)→存npy→CPU建索引")
    print("=" * 60)
    NPY_DIR.mkdir(parents=True, exist_ok=True)

    all_singers = []
    for d in sorted(RAW_DIR.iterdir()):
        if not d.is_dir(): continue
        files = sorted([str(f.absolute()) for f in d.rglob("*")
            if f.suffix.lower() in (".wav", ".mp3", ".m4a")
            and "demucs_output" not in f.parts and "tmp" not in f.parts])
        if files:
            all_singers.append((d.name, files[:3]))

    done = set(f.stem for f in NPY_DIR.glob("*.npy"))
    remaining = [(n, p) for n, p in all_singers if n not in done]
    print(f"\n总数: {len(all_singers)} | 已完成: {len(done)} | 待处理: {len(remaining)}")
    if not remaining:
        build_faiss(all_singers); return

    from voice_recognition.model_loader import VoiceprintRecognizer
    rec = VoiceprintRecognizer(use_gpu=True)
    t_start = time.time()

    for idx, (name, paths) in enumerate(remaining):
        embs = []
        for p in paths:
            try:
                embs.append(rec.extract_embedding(p))
            except Exception:
                continue
        if embs:
            avg = np.mean(embs, axis=0).astype(np.float32)
            nrm = np.linalg.norm(avg)
            if nrm > 0: avg /= nrm
            np.save(str(NPY_DIR / f"{name}.npy"), avg)

        # 每20位清理
        if (idx + 1) % 20 == 0:
            gc.collect(); torch.cuda.empty_cache()
            elapsed = time.time() - t_start
            total_done = len(done) + idx + 1
            rate = total_done / (elapsed / 3600)
            print(f"  进度: {idx+1}/{len(remaining)} | 累计{total_done}/{len(all_singers)} | {elapsed:.0f}s | {rate:.0f}人/h")

    del rec; gc.collect(); torch.cuda.empty_cache()
    print(f"\n提取完成: {time.time()-t_start:.0f}s")
    build_faiss(all_singers)
    print(f"\n✅ 完成! 注册 {len(all_singers)} 位歌手")

def build_faiss(singers):
    import faiss
    all_embs, all_names, missing = [], [], []
    for name, _ in singers:
        npy = NPY_DIR / f"{name}.npy"
        if not npy.exists():
            missing.append(name); continue
        all_embs.append(np.load(str(npy)))
        all_names.append(name)
    print(f"\n[FAISS] {len(all_names)} 向量 (缺失{len(missing)})")
    if not all_embs: return
    matrix = np.array(all_embs, dtype=np.float32)
    faiss.normalize_L2(matrix)
    index = faiss.index_factory(matrix.shape[1], "Flat", faiss.METRIC_INNER_PRODUCT)
    index.add(matrix)
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(INDEX_FILE))
    meta = {"celebrities": all_names, "embedding_dim": int(matrix.shape[1]),
            "num_celebrities": len(all_names), "model_type": "cam++",
            "index_path": str(INDEX_FILE)}
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"  索引: {INDEX_FILE} | 元数据: {META_FILE} ({len(all_names)} 位)")

if __name__ == "__main__":
    main()
