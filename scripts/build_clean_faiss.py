#!/usr/bin/env python3
"""
轻量化纯净人声 FAISS 索引构建
================================
流程: 现有 raw 音频 → Demucs 分离伴奏 → 副歌截取15s → CAM++ 提取 → FAISS 索引

8GB 显卡显存优化:
  1. Demucs 子进程分离（进程退出后显存完全释放）
  2. 分离完 → 清理 → 再加载 CAM++ 提取
  3. 提取完立即删除中间 wav，不积压磁盘
  4. 使用 htdemucs_2stems（人声/伴奏两路，显存减半）

输出: vector_database/faiss_index/celebrity_clean.index + .json
      （不覆盖现有的 celebrity.index，双索引共存）
"""

import sys, os, json, time, gc, shutil, subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if os.name == "nt":
    sys.stdout.reconfigure(encoding="utf-8")

import numpy as np

RAW_DIR = Path("data/raw")
NPY_DIR = Path("vector_database/faiss_index/clean_embeddings")
INDEX_FILE = Path("vector_database/faiss_index/celebrity_clean.index")
META_FILE = Path("vector_database/faiss_index/celebrity_clean_metadata.json")
DEMUCS_TMP = Path("data/tmp_demucs_clean")

# 跳过已处理的歌手（断点续跑）
SKIP_LIST = set(f.stem for f in NPY_DIR.glob("*.npy")) if NPY_DIR.exists() else set()


def find_ffmpeg():
    """跨平台查找可用 ffmpeg（复用 views.py 的逻辑）"""
    import shutil
    candidates = [
        shutil.which("ffmpeg"),
        shutil.which("ffmpeg.exe"),
        "/usr/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
        "ffmpeg",
    ]
    candidates = [c for c in candidates if c]
    for c in candidates:
        try:
            r = subprocess.run([c, "-version"], capture_output=True, timeout=5)
            if r.returncode == 0:
                return c
        except Exception:
            continue
    return ""


def run_demucs(audio_path):
    """子进程运行 Demucs，返回 vocals.wav 路径"""
    stem = Path(audio_path).stem
    out_dir = DEMUCS_TMP / "htdemucs" / stem
    vocal_path = out_dir / "vocals.wav"
    if vocal_path.exists():
        return str(vocal_path)

    cmd = [
        sys.executable, "-m", "demucs",
        "--two-stems", "vocals",
        "-n", "htdemucs",
        "-o", str(DEMUCS_TMP),
        "--device", "cuda",
        "--overlap", "0.1",
        str(audio_path),
    ]
    try:
        subprocess.run(cmd, check=True, timeout=600,
                       capture_output=True,
                       env={**os.environ, "TQDM_DISABLE": "1"})
        return str(vocal_path) if vocal_path.exists() else None
    except Exception as e:
        print(f"    [Demucs ERR] {Path(audio_path).name}: {e}")
        return None


def extract_chorus_segment(vocal_path, duration=15):
    """
    用 ffmpeg + librosa 检测副歌并截取 15s
    返回截取后的 .wav 路径
    """
    import librosa
    import numpy as np
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return vocal_path

    try:
        # 检测副歌起始
        y, sr = librosa.load(vocal_path, sr=16000, mono=True, duration=120)
        hop_sec = 0.5
        hop = int(sr * hop_sec)
        rms = librosa.feature.rms(y=y, hop_length=hop)[0]
        window = max(1, int(3.0 / hop_sec))
        kernel = np.ones(window) / window
        energy = np.convolve(rms, kernel, mode="same")

        skip_frames = int(10.0 / hop_sec)
        if skip_frames >= len(energy):
            chorus_start = 5.0
        else:
            global_max = np.max(energy)
            lookahead = int(4.0 / hop_sec)
            baseline_range = int(8.0 / hop_sec)
            gap = max(1, int(2.0 / hop_sec))

            # 最佳跃升
            best_r, best_p = 0.0, None
            for i in range(skip_frames + baseline_range + gap, len(energy) - lookahead):
                baseline = np.median(energy[i - baseline_range - gap: i - gap])
                cur = np.mean(energy[i: i + lookahead])
                if baseline > 1e-8 and cur > global_max * 0.08:
                    ratio = cur / baseline
                    if ratio > 1.25 and ratio > best_r:
                        best_r, best_p = ratio, i

            if best_p is not None and best_r >= 1.3:
                chorus_start = max(0, best_p * hop_sec - 1.0)
            else:
                chorus_start = 5.0

        # 截取
        out_path = vocal_path.replace(".wav", "_segment.wav")
        r = subprocess.run(
            [ffmpeg, "-y", "-i", vocal_path, "-ss", str(chorus_start),
             "-t", str(duration), "-ar", "16000", "-ac", "1",
             "-sample_fmt", "s16", "-f", "wav", out_path],
            capture_output=True, timeout=30,
        )
        if r.returncode == 0 and Path(out_path).exists() and Path(out_path).stat().st_size > 1000:
            return out_path
    except Exception as e:
        print(f"    [Chorus ERR] {e}")

    return vocal_path


def extract_embedding(recognizer, audio_path):
    """提取 embedding"""
    return recognizer.extract_embedding(audio_path)


def clean_singer_output(singer_name):
    """清理某歌手的所有中间文件"""
    # Demucs 输出
    demucs_dir = DEMUCS_TMP / "htdemucs"
    if demucs_dir.exists():
        for d in demucs_dir.iterdir():
            if d.is_dir():
                try:
                    shutil.rmtree(str(d))
                except Exception:
                    pass

    # 清理 CUDA 缓存
    gc.collect()
    try:
        import torch
        torch.cuda.empty_cache()
    except Exception:
        pass


def main():
    print("=" * 60)
    print("  纯净人声 FAISS 索引构建 (轻量化)")
    print("  Demucs 子进程分离 → 副歌15s → CAM++ 提取")
    print("  8GB 显存优化: 串行推理 + 逐歌手清理")
    print("=" * 60)

    NPY_DIR.mkdir(parents=True, exist_ok=True)
    DEMUCS_TMP.mkdir(parents=True, exist_ok=True)

    # 收集歌手
    all_singers = []
    for d in sorted(RAW_DIR.iterdir()):
        if not d.is_dir():
            continue
        files = sorted([
            str(f.absolute()) for f in d.rglob("*")
            if f.suffix.lower() in (".wav", ".mp3", ".m4a")
            and "demucs_output" not in f.parts and "tmp" not in f.parts
        ])
        if files:
            all_singers.append((d.name, files[:2]))  # 每人2首（配合原规范3首→取2）

    total = len(all_singers)
    done_count = len(SKIP_LIST)
    remaining = [(n, p) for n, p in all_singers if n not in SKIP_LIST]

    print(f"\n歌手总数: {total}")
    print(f"已完成: {done_count}")
    print(f"待处理: {len(remaining)}")

    if not remaining:
        print("全部已完成，直接构建 FAISS...")
        build_faiss(all_singers)
        return

    # 加载 CAM++（全程常驻，~1GB 显存）
    print(f"\n加载 CAM++ 声纹模型...")
    from voice_recognition.model_loader import VoiceprintRecognizer
    rec = VoiceprintRecognizer(use_gpu=True)
    t_start = time.time()

    # 逐个歌手处理
    for idx, (name, file_paths) in enumerate(remaining):
        print(f"\n[{idx + 1}/{len(remaining)}] {name} ({len(file_paths)} 首)...")

        singer_embs = []

        for fi, fpath in enumerate(file_paths):
            fname = Path(fpath).name
            print(f"  文件 {fi + 1}: {fname}")

            # Step 1: Demucs 子进程分离（结束后显存自动释放）
            t1 = time.time()
            vocal_path = run_demucs(fpath)
            if not vocal_path or not Path(vocal_path).exists():
                print(f"    ⏭ Demucs 失败，跳过")
                continue
            demucs_time = time.time() - t1
            print(f"    Demucs: {demucs_time:.0f}s ✅")

            # Step 2: 检测副歌并截取 15s
            t2 = time.time()
            segment_path = extract_chorus_segment(vocal_path)
            chorus_time = time.time() - t2
            print(f"    副歌截取: {chorus_time:.0f}s")

            # Step 3: CAM++ 提取 embedding
            t3 = time.time()
            try:
                emb = extract_embedding(rec, segment_path)
                singer_embs.append(emb)
                embed_time = time.time() - t3
                print(f"    CAM++: {embed_time:.0f}s ✅ ({len(emb)} 维)")
            except Exception as e:
                print(f"    CAM++ 失败: {e}")

        # 平均 embedding 并保存
        if singer_embs:
            avg_emb = np.mean(singer_embs, axis=0).astype(np.float32)
            norm = np.linalg.norm(avg_emb)
            if norm > 0:
                avg_emb /= norm
            np.save(str(NPY_DIR / f"{name}.npy"), avg_emb)
            print(f"  ✅ 保存 {name}.npy")

        # Step 4: 清理所有中间文件
        clean_singer_output(name)
        elapsed = time.time() - t_start
        done = done_count + idx + 1
        rate = done / (elapsed / 3600)
        print(f"  进度: {done}/{total} | {elapsed:.0f}s | {rate:.0f}人/h")

    # 全部完成，构建 FAISS
    del rec
    gc.collect()
    try:
        import torch
        torch.cuda.empty_cache()
    except Exception:
        pass

    build_faiss(all_singers)

    total_time = time.time() - t_start
    print(f"\n{'=' * 60}")
    print(f"  完成! 总耗时: {total_time:.0f}s ({total_time / 60:.1f}min)")
    print(f"  纯净人声索引: {INDEX_FILE}")
    print(f"  元数据: {META_FILE}")
    print(f"  现有索引（带伴奏）未被覆盖")
    print(f"{'=' * 60}")


def build_faiss(singers):
    """从 npy 构建 FAISS 索引"""
    import faiss

    all_embs, all_names, missing = [], [], []
    for name, _ in singers:
        npy = NPY_DIR / f"{name}.npy"
        if not npy.exists():
            missing.append(name)
            continue
        all_embs.append(np.load(str(npy)))
        all_names.append(name)

    print(f"\n[FAISS] 构建索引: {len(all_names)} 向量 (缺失: {len(missing)})")
    if not all_embs:
        print("[FAISS] 无向量，跳过")
        return

    matrix = np.array(all_embs, dtype=np.float32)
    faiss.normalize_L2(matrix)

    index = faiss.index_factory(matrix.shape[1], "Flat", faiss.METRIC_INNER_PRODUCT)
    index.add(matrix)

    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(INDEX_FILE))

    meta = {
        "celebrities": all_names,
        "embedding_dim": int(matrix.shape[1]),
        "num_celebrities": len(all_names),
        "model_type": "cam++",
        "source": "demucs_clean_vocals",
        "index_path": str(INDEX_FILE),
    }
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"  索引: {INDEX_FILE} ({index.ntotal} 向量)")
    print(f"  元数据: {META_FILE} ({len(all_names)} 位歌手)")


if __name__ == "__main__":
    main()
