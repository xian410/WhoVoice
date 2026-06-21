#!/usr/bin/env python3
"""
爬虫启动脚本
用法:
    python scripts/run_crawler.py                           # 爬取所有明星
    python scripts/run_crawler.py --celebrities 周杰伦 林俊杰  # 指定明星
    python scripts/run_crawler.py --max 5                     # 每个明星最多5个视频
    python scripts/run_crawler.py --fix-missing               # 增量补爬：仅处理不足的歌手
    python scripts/run_crawler.py --fix-missing --min 2       # 补爬至每歌手至少2首
    python scripts/run_crawler.py --fix-missing --dry-run     # 预览哪些歌手需要补爬
"""

import os
import sys

# 修复 Windows 终端编码
if os.name == "nt":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    os.system("chcp 65001 > nul 2>&1")

import argparse
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crawler.scheduler import CrawlerScheduler
from crawler.config import CELEBRITY_LIST, MAX_VIDEOS_PER_CELEBRITY


def main():
    parser = argparse.ArgumentParser(description="WhoVoice 爬虫启动脚本")
    parser.add_argument(
        "--celebrities", nargs="+",
        help="指定爬取的明星列表，默认使用 config.py 中的配置"
    )
    parser.add_argument(
        "--max", type=int, default=MAX_VIDEOS_PER_CELEBRITY,
        help=f"每个明星最多下载的视频数 (默认: {MAX_VIDEOS_PER_CELEBRITY})"
    )
    parser.add_argument(
        "--fix-missing", action="store_true",
        help="增量补爬模式：自动检测并仅处理音频不足的歌手"
    )
    parser.add_argument(
        "--min", type=int, default=2,
        help="补爬目标：每歌手至少N首 (默认: 2, 仅 --fix-missing 生效)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="预览模式：仅检测哪些歌手需要补爬，不实际下载"
    )
    args = parser.parse_args()

    # ── 增量补爬模式 ──
    if args.fix_missing:
        deficient = CrawlerScheduler.find_deficient(min_count=args.min)
        if not deficient:
            print(f"[INFO] 所有歌手均已满足 >= {args.min} 首音频，无需补爬")
            return

        # 按缺少数量排序：0首的优先
        deficient.sort(key=lambda x: x["count"])

        names = [d["name"] for d in deficient]
        print(f"[增量补爬] 检测到 {len(deficient)} 位歌手音频不足 (< {args.min} 首):")
        for d in deficient:
            print(f"  {d['name']:<15}  已有 {d['count']} 首, 还差 {d['need']} 首")
        print()

        if args.dry_run:
            print("[DRY RUN] 以上歌手将被补爬，当前仅预览不下载。")
            print(f"  移除 --dry-run 参数即可开始下载。")
            # 仍然走 scheduler 的 dry_run 以输出完整统计
            scheduler = CrawlerScheduler(celebrities=names)
            scheduler.run(max_videos_per_celebrity=args.min, dry_run=True)
            return

        print(f"开始增量补爬 {len(deficient)} 位歌手...\n")
        scheduler = CrawlerScheduler(celebrities=names)
        scheduler.run(max_videos_per_celebrity=args.max)
        return

    # ── 全量/指定模式 ──
    celebrities = args.celebrities or CELEBRITY_LIST
    print(f"目标明星: {len(celebrities)} 位")
    print(f"每个明星最多下载: {args.max} 个视频\n")

    scheduler = CrawlerScheduler(celebrities=celebrities)
    scheduler.run(max_videos_per_celebrity=args.max, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
爬虫启动脚本
用法:
    python scripts/run_crawler.py                           # 爬取所有明星
    python scripts/run_crawler.py --celebrities 周杰伦 林俊杰  # 指定明星
    python scripts/run_crawler.py --max 5                     # 每个明星最多5个视频
"""

import os
import sys

# 修复 Windows 终端编码
if os.name == "nt":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    os.system("chcp 65001 > nul 2>&1")

import argparse
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crawler.scheduler import CrawlerScheduler
from crawler.config import CELEBRITY_LIST, MAX_VIDEOS_PER_CELEBRITY


def main():
    parser = argparse.ArgumentParser(description="WhoVoice 爬虫启动脚本")
    parser.add_argument(
        "--celebrities", nargs="+",
        help="指定爬取的明星列表，默认使用 config.py 中的配置"
    )
    parser.add_argument(
        "--max", type=int, default=MAX_VIDEOS_PER_CELEBRITY,
        help=f"每个明星最多下载的视频数 (默认: {MAX_VIDEOS_PER_CELEBRITY})"
    )
    args = parser.parse_args()

    celebrities = args.celebrities or CELEBRITY_LIST
    print(f"目标明星: {celebrities}")
    print(f"每个明星最多下载: {args.max} 个视频\n")

    scheduler = CrawlerScheduler(celebrities=celebrities)
    scheduler.run(max_videos_per_celebrity=args.max)


if __name__ == "__main__":
    main()
