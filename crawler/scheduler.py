"""
爬虫调度器
按明星列表批量调度各平台爬虫
当前仅启用 B站 爬虫通道
"""

import os
import sys
import time
import logging
from pathlib import Path
from typing import List, Optional

# 修复 Windows 终端编码
if os.name == "nt":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    os.system("chcp 65001 > nul 2>&1")

from crawler.config import CELEBRITY_LIST, RAW_DATA_DIR
from crawler.base_crawler import BaseCrawler
from crawler.bilibili_crawler import BilibiliCrawler
from crawler.qq_music_crawler import QqMusicCrawler
from crawler.youtube_crawler import YouTubeCrawler

logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 预估每明星每视频的平均磁盘占用 (原始音视频 + Demucs 分离产物)
# 实际值随B站视频时长波动，此为保守估算
ESTIMATED_GB_PER_CELEBRITY = 0.5  # 每位明星约 0.5 GB
MIN_DISK_GB = 5.0  # 最低剩余空间阈值 (GB)


def check_disk_space(celebrities: list, max_videos_per: int) -> bool:
    """
    检查磁盘剩余空间是否充足
    返回 False 表示空间不足，应中止运行
    """
    try:
        import shutil
        usage = shutil.disk_usage(Path(RAW_DATA_DIR) if Path(RAW_DATA_DIR).exists() else ".")
        free_gb = usage.free / (1024 ** 3)

        # 预估所需空间
        est_needed = len(celebrities) * ESTIMATED_GB_PER_CELEBRITY

        logger.info(f"磁盘状态: 剩余 {free_gb:.1f} GB, 预估需 {est_needed:.1f} GB")
        logger.info(f"  (将爬取 {len(celebrities)} 位明星, 每位最多 {max_videos_per} 个视频)")

        if free_gb < 1.0:
            logger.error(f"磁盘空间严重不足 (仅剩 {free_gb:.1f} GB)，中止运行")
            logger.error(f"请运行 python scripts/cleanup.py --keep-raw 释放空间")
            return False

        if free_gb < MIN_DISK_GB:
            logger.warning(f"磁盘空间不足 (剩余 {free_gb:.1f} GB < {MIN_DISK_GB} GB)，建议清理")
            logger.warning(f"运行 python scripts/cleanup.py --dry-run 预览可释放空间")

        if free_gb < est_needed:
            logger.warning(f"预估空间不足: 剩余 {free_gb:.1f} GB < 预估需求 {est_needed:.1f} GB")
            logger.warning(f"继续运行可能导致磁盘写满，建议先清理旧数据")

        return True
    except Exception as e:
        logger.warning(f"磁盘空间检查失败: {e}，将继续运行")
        return True


class CrawlerScheduler:
    """爬虫调度器"""

    def __init__(self, celebrities: Optional[List[str]] = None):
        self.celebrities = celebrities or CELEBRITY_LIST
        self.platforms: List[BaseCrawler] = self._init_platforms()

    def _init_platforms(self) -> List[BaseCrawler]:
        """初始化各平台爬虫（酷我音乐 > 酷狗音乐 > B站）"""
        from crawler.config import BILIBILI, KUWO_MUSIC, KUGOU_MUSIC
        from crawler.kuwo_music_crawler import KuwoMusicCrawler
        from crawler.kugou_music_crawler import KugouMusicCrawler
        return [
            KuwoMusicCrawler(KUWO_MUSIC),   # 第一选择：酷我音乐
            KugouMusicCrawler(KUGOU_MUSIC),  # 第二选择：酷狗音乐
            BilibiliCrawler(BILIBILI),       # 第三选择：B站
        ]

    def run(self, max_videos_per_celebrity: int = 2):
        """
        运行全量爬取流程
        对每个明星，依次使用各平台爬虫搜索并下载
        """
        # 启动前检查磁盘空间
        if not check_disk_space(self.celebrities, max_videos_per_celebrity):
            logger.error("磁盘空间不足，爬虫已中止")
            return

        for celebrity in self.celebrities:
            logger.info(f"开始爬取 [{celebrity}] 的语音数据...")

            for platform in self.platforms:
                try:
                    # 检查歌手总目录是否已有足够文件（酷我成功后跳过后续平台）
                    celeb_raw = Path(RAW_DATA_DIR) / celebrity
                    existing = len(list(celeb_raw.rglob("*.wav"))) if celeb_raw.exists() else 0
                    if existing >= max_videos_per_celebrity:
                        logger.info(f"    已有 {existing} 个文件，跳过 {platform.platform_name}")
                        continue

                    logger.info(f"  -> 在 {platform.platform_name} 上搜索...")
                    results = platform.search(celebrity, max_results=max_videos_per_celebrity)
                    logger.info(f"     找到 {len(results)} 个资源")

                    for i, item in enumerate(results[:max_videos_per_celebrity]):
                        save_dir = platform.get_save_dir(celebrity)
                        filename = platform.sanitize_filename(f"{i:03d}_{item['title']}")
                        save_path = str(save_dir / f"{filename}.wav")

                        logger.info(f"     下载 [{i+1}/{len(results[:max_videos_per_celebrity])}]: {item['title'][:40]}...")
                        success = platform.download(item["url"], save_path)

                        if success:
                            platform.save_metadata(celebrity, {
                                "title": item["title"],
                                "url": item["url"],
                                "duration": item["duration"],
                                "file_path": save_path,
                            })
                            logger.info(f"     下载成功")

                        time.sleep(2)  # 请求间隔，避免触发反爬

                except Exception as e:
                    logger.error(f"     [{platform.platform_name}] 爬取失败: {e}")
                    continue

            logger.info(f"[{celebrity}] 爬取完成\n")


if __name__ == "__main__":
    scheduler = CrawlerScheduler()
    scheduler.run()
