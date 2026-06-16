#!/usr/bin/env python3
"""
分批处理流水线：爬取 → 预处理 → 清理raw → 下一批 → 最终构建FAISS索引

流程:
  1. 读取 511 位明星列表
  2. 过滤出尚未处理的明星（跳过已有 data/processed/xxx 的）
  3. 按 BATCH_SIZE 分批
  4. 每批: 爬取(B站+QQ音乐) → 预处理 → 激进清理 raw
  5. 全部完成后: 提取声纹特征 → 构建 FAISS 索引

用法:
  python scripts/batch_pipeline.py                  # 全量处理（每批50人）
  python scripts/batch_pipeline.py --batch-size 30  # 自定义每批大小
  python scripts/batch_pipeline.py --dry-run        # 预览模式
"""

import sys
import time
import shutil
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crawler.scheduler import CrawlerScheduler
from preprocessing.pipeline import PreprocessingPipeline
from crawler.config import CELEBRITY_LIST, MAX_VIDEOS_PER_CELEBRITY

PROCESSED_DIR = Path("data/processed")
RAW_DIR = Path("data/raw")
BATCH_LOG = Path("batch_progress.json")


def get_unprocessed():
    """获取尚未处理的明星（跳过已有 processed 目录的）"""
    processed = {d.name for d in PROCESSED_DIR.iterdir() if d.is_dir()}
    new_celebrities = [c for c in CELEBRITY_LIST if c not in processed]
    return new_celebrities


def save_progress(batch_index: int, celeb_name: str = None):
    """保存进度以便断点续跑"""
    data = {"last_batch": batch_index}
    if celeb_name:
        data["last_celebrity"] = celeb_name
    with open(BATCH_LOG, "w") as f:
        import json
        json.dump(data, f)


def clean_raw_celebrity(celeb: str):
    """删除单个明星的 raw 目录"""
    celeb_dir = RAW_DIR / celeb
    if celeb_dir.exists():
        size = sum(f.stat().st_size for f in celeb_dir.rglob("*") if f.is_file())
        shutil.rmtree(str(celeb_dir))
        return size
    return 0


def human_size(n: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def main():
    parser = argparse.ArgumentParser(description="WhoVoice 分批处理流水线")
    parser.add_argument("--batch-size", type=int, default=50, help="每批人数（默认50）")
    parser.add_argument("--dry-run", action="store_true", help="预览模式：只显示计划不执行")
    args = parser.parse_args()

    batch_size = args.batch_size

    print("=" * 60)
    print("  WhoVoice - 分批处理流水线")
    print("  爬取 → 预处理 → 清理raw → (循环) → 声纹提取")
    print("=" * 60)

    # ── 第0步：确定需要处理的新明星 ──
    print("\n[0/5] 检查处理状态...")
    unprocessed = get_unprocessed()
    total_new = len(unprocessed)
    total_all = len(CELEBRITY_LIST)

    if total_new == 0:
        print(f"  ✅ 全部 {total_all} 位明星已处理完成！直接进入声纹提取")
    else:
        print(f"  总名单: {total_all} 位")
        print(f"  已处理: {total_all - total_new} 位")
        print(f"  待处理: {total_new} 位")

    # ── 第1步：清理旧 raw 中已处理的明星 ──
    processed_names = {d.name for d in PROCESSED_DIR.iterdir() if d.is_dir()}
    stale_raw = [d for d in RAW_DIR.iterdir() if d.is_dir() and d.name in processed_names]

    if stale_raw:
        print(f"\n[1/5] 清理旧 raw 缓存（已处理但未删除的原始音频）...")
        total_freed = 0
        for d in stale_raw:
            sz = 0
            if not args.dry_run:
                sz = clean_raw_celebrity(d.name)
            else:
                sz = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
            total_freed += sz
            print(f"  {'🔍 [预览]' if args.dry_run else '🗑️'}  {d.name}: {human_size(sz)}")
        print(f"  总计: {human_size(total_freed)} {'（预览，未实际删除）' if args.dry_run else '已释放'}")

    if total_new == 0:
        # 已全部处理，直接跳到声纹提取
        pass
    else:
        # ── 第2步：分批处理 ──
        batches = [unprocessed[i:i + batch_size] for i in range(0, total_new, batch_size)]
        total_batches = len(batches)

        print(f"\n[2/5] 分批处理 ({total_batches} 批, 每批 {batch_size} 人)")

        for batch_idx, batch in enumerate(batches):
            print(f"\n{'=' * 60}")
            print(f"  📦 第 {batch_idx + 1}/{total_batches} 批 ({len(batch)} 位)")
            print(f"{'=' * 60}")

            if args.dry_run:
                print(f"  预览: {', '.join(batch[:5])}... 等 {len(batch)} 位")
                save_progress(batch_idx)
                continue

            # 2a. 爬取
            print(f"\n  ▶ 阶段 A: 爬取 {len(batch)} 位明星...")
            scheduler = CrawlerScheduler(celebrities=batch)
            scheduler.run(max_videos_per_celebrity=MAX_VIDEOS_PER_CELEBRITY)

            # 统计本批实际下载到的明星数
            downloaded = [c for c in batch if (RAW_DIR / c).exists() and len(list((RAW_DIR / c).rglob("*.wav"))) > 0]
            print(f"  ⏺ 本批成功下载: {len(downloaded)}/{len(batch)} 位")

            # 2b. 预处理
            print(f"\n  ▶ 阶段 B: 预处理音频...")
            pipeline = PreprocessingPipeline()
            pipeline.run(celebrities=batch)

            # 2c. 清理 raw
            print(f"\n  ▶ 阶段 C: 清理 raw 缓存...")
            freed = 0
            for celeb in batch:
                freed += clean_raw_celebrity(celeb)
            print(f"  🗑️  已释放: {human_size(freed)}")

            # 保存进度
            save_progress(batch_idx)
            print(f"\n  ✅ 第 {batch_idx + 1} 批完成! 已释放 {human_size(freed)}")

    # ── 第5步：声纹特征提取 + FAISS 索引 ──
    print(f"\n{'=' * 60}")
    print(f"  🎯 全部批次处理完成！")
    print(f"  {'=' * 60}")

    if args.dry_run:
        print(f"\n  预览模式结束。运行不加 --dry-run 以执行。")
        return

    print(f"\n[5/5] 提取声纹特征并构建 FAISS 索引...")
    print(f"  增量模式：仅处理新明星，添加到已有 FAISS 索引\n")

    # 增量模式：仅提取新明星声纹并附加到现有索引
    import sys as _sys
    _orig_argv = _sys.argv
    _sys.argv = ["extract_embeddings", "--append"]
    from scripts.extract_embeddings import main as extract_main
    extract_main()
    _sys.argv = _orig_argv

    # 清理进度文件
    if BATCH_LOG.exists():
        BATCH_LOG.unlink()

    print(f"\n{'=' * 60}")
    print(f"  🎉 全流程完成! 511 位明星声纹库已就绪")
    print(f"  启动服务: python backend/manage.py runserver")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
