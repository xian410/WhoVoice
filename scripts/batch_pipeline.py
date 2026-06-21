#!/usr/bin/env python3
"""
WhoVoice 全量流水线 v2
流程: 遍历 502 位歌手 逐位完成:
  1. 爬取 (酷我 > 酷狗 > B站, 3首)
  2. 预处理 (人声分离 + VAD + 切片)
  3. GPU 声纹提取 + 增量 FAISS
  4. 清理 raw + processed

用法:
  python scripts/batch_pipeline.py --rebuild   全量重建
  python scripts/batch_pipeline.py --dry-run   预览
"""

import sys, os, time, gc, json, shutil, argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if os.name == "nt":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from tqdm import tqdm
import numpy as np
from crawler.scheduler import CrawlerScheduler
from voice_recognition.model_loader import VoiceprintRecognizer
from vector_database.build_index import VectorIndexBuilder
from vector_database.config import FAISS, EMBEDDING_DIM
from crawler.config import CELEBRITY_LIST, MAX_VIDEOS_PER_CELEBRITY

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
INDEX_PATH = Path(FAISS["index_path"])
METADATA_PATH = INDEX_PATH.parent / "celebrity_metadata.json"


def clean_all():
    for d in [RAW_DIR, PROCESSED_DIR]:
        if d.exists():
            shutil.rmtree(str(d))
        d.mkdir(parents=True)
    for f in [INDEX_PATH, METADATA_PATH]:
        if f.exists():
            f.unlink()


def process_singer(celebrity, recognizer, builder, pbar):
    # 1. 爬取
    scheduler = CrawlerScheduler(celebrities=[celebrity])
    scheduler.run(max_videos_per_celebrity=MAX_VIDEOS_PER_CELEBRITY)
    if not (RAW_DIR / celebrity).exists() or len(list((RAW_DIR / celebrity).rglob("*"))) == 0:
        pbar.set_postfix_str("无资源")
        return
    # 2. 预处理
    try:
        from preprocessing.pipeline import PreprocessingPipeline
        PreprocessingPipeline().run(celebrities=[celebrity])
    except Exception as e:
        print(f"\n  [{celebrity}] 预处理失败: {e}")
        return
    # 3. 声纹提取
    proc_dir = PROCESSED_DIR / celebrity
    if not proc_dir.exists():
        return
    wav_files = [f for f in sorted(proc_dir.rglob("*.wav")) if "tmp" not in f.parts]
    if not wav_files:
        return
    embeddings = []
    for wav in wav_files:
        try:
            embeddings.append(recognizer.extract_embedding(str(wav)))
        except Exception:
            continue
    if embeddings:
        avg_emb = np.mean(embeddings, axis=0).astype(np.float32)
        avg_emb = avg_emb / np.linalg.norm(avg_emb)
        builder.add_to_faiss(embeddings=avg_emb[np.newaxis, :], celeb_names=[celebrity])
    # 4. 清理（只删除预处理切片，保留原始音频）
    if proc_dir.exists():
        shutil.rmtree(str(proc_dir))
    gc.collect()
    try:
        import torch; torch.cuda.empty_cache()
    except Exception:
        pass


def estimate_time(total):
    sec = total * 130
    return f"{sec//3600}h{(sec%3600)//60:02d}m"


def main():
    parser = argparse.ArgumentParser(description="WhoVoice 全量流水线 v2")
    parser.add_argument("--rebuild", action="store_true", help="全量重建清空旧数据")
    parser.add_argument("--dry-run", action="store_true", help="预览模式")
    parser.add_argument("--start-from", type=int, default=0, help="断点续跑: 从第几个开始")
    args = parser.parse_args()

    print("=" * 56)
    print("  WhoVoice 全量流水线 v2")
    print("  酷我音乐 | 3首/人 | GPU加速 | 保留原音频")
    print("=" * 56)

    total = len(CELEBRITY_LIST)
    print(f"\n  歌手总数: {total}")
    print(f"  预估耗时: {estimate_time(total)} (130s/人)")
    try:
        import torch
        print(f"  GPU:      {torch.cuda.get_device_name(0)}")
    except Exception:
        print("  GPU:      N/A")

    if args.dry_run:
        print("\n  预览模式:", CELEBRITY_LIST[0], "...", CELEBRITY_LIST[-1])
        return

    if args.rebuild:
        print("\n[1/4] 清空旧数据...")
        clean_all()
        print("  旧数据已清空")

    print("\n[2/4] 加载声纹模型 (GPU)...")
    recognizer = VoiceprintRecognizer(use_gpu=True)
    builder = VectorIndexBuilder(dimension=EMBEDDING_DIM)

    celebrities = CELEBRITY_LIST[args.start_from:]
    print(f"\n[3/4] 处理 {len(celebrities)} 位 (从第{args.start_from+1}位)")
    start_time = time.time()

    pbar = tqdm(celebrities, desc="流水线", unit="人", ncols=80)
    for idx, celeb in enumerate(pbar):
        actual = args.start_from + idx + 1
        pbar.set_description(f"[{actual}/{total}] {celeb[:10]}")
        try:
            process_singer(celeb, recognizer, builder, pbar)
        except Exception as e:
            pbar.set_postfix_str(f"错误:{str(e)[:20]}")
            gc.collect()
            try:
                import torch; torch.cuda.empty_cache()
            except Exception:
                pass
        if actual % 20 == 0:
            elapsed = time.time() - start_time
            pbar.write(f"  [{actual}/{total}] {elapsed/60:.0f}min | {actual/(elapsed/3600):.0f}人/h")
    pbar.close()

    elapsed = time.time() - start_time
    print(f"\n[4/4] 完成! {elapsed/60:.0f}min ({elapsed/3600:.1f}h)")
    print(f"  启动: python backend/manage.py runserver")


if __name__ == "__main__":
    main()
