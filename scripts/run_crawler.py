#!/usr/bin/env python3
"""
爬虫启动脚本
用法:
    python scripts/run_crawler.py                           # 爬取所有明星
    python scripts/run_crawler.py --celebrities 周杰伦 林俊杰  # 指定明星
    python scripts/run_crawler.py --max 5                     # 每个明星最多5个视频
"""

import argparse
import sys
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
