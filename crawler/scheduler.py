"""
爬虫调度器
按明星列表批量调度各平台爬虫
支持多源优先级：酷我音乐（首选）→ Bilibili（兜底）
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
        """初始化爬虫：酷我音乐（首选）+ Bilibili（兜底）"""
        from crawler.config import KUWO_MUSIC, BILIBILI
        from crawler.kuwo_music_crawler import KuwoMusicCrawler
        platforms = [
            KuwoMusicCrawler(KUWO_MUSIC),
        ]
        # Bilibili 作为兜底源（需要 cookies.txt）
        if Path(BILIBILI.get("cookies_file", "cookies.txt")).exists():
            platforms.append(BilibiliCrawler(BILIBILI))
        return platforms

    @staticmethod
    def find_deficient(min_count: int = 2) -> List[dict]:
        """
        扫描 data/raw 目录，找出音频数量不足的歌手
        返回列表: [{"name": "xxx", "count": 0, "need": 2}, ...]
        """
        raw = Path(RAW_DATA_DIR)
        if not raw.exists():
            return []

        audio_exts = {'.wav', '.mp3', '.m4a', '.flac'}
        deficient = []

        for singer_dir in sorted(raw.iterdir()):
            if not singer_dir.is_dir():
                continue
            files = [f for f in singer_dir.rglob('*')
                     if f.is_file() and f.suffix.lower() in audio_exts]
            count = len(files)
            if count < min_count:
                deficient.append({
                    "name": singer_dir.name,
                    "count": count,
                    "need": min_count - count,
                })

        return deficient

    def run(self, max_videos_per_celebrity: int = 2, dry_run: bool = False):
        """
        运行全量爬取流程
        对每个明星，依次使用各平台爬虫搜索并下载
        若常规搜索不够，自动追加 "歌手名 live" 搜索（针对B站现场版）
        dry_run: 仅检测哪些歌手需要补爬，不实际下载
        """
        # 启动前检查磁盘空间
        if not dry_run:
            if not check_disk_space(self.celebrities, max_videos_per_celebrity):
                logger.error("磁盘空间不足，爬虫已中止")
                return

        if dry_run:
            logger.info(f"[DRY RUN] 检测模式，不实际下载")
            logger.info(f"目标: {len(self.celebrities)} 位歌手, 每位至少 {max_videos_per_celebrity} 首\n")

        skipped = 0
        for celebrity in self.celebrities:
            # 检查现有有效文件数量
            celeb_raw = Path(RAW_DATA_DIR) / celebrity
            audio_exts = {'.wav', '.mp3', '.m4a', '.flac'}
            existing = len([f for f in celeb_raw.rglob('*')
                           if f.is_file() and f.suffix.lower() in audio_exts]) if celeb_raw.exists() else 0

            if existing >= max_videos_per_celebrity:
                skipped += 1
                continue

            need = max_videos_per_celebrity - existing
            if dry_run:
                logger.info(f"  [需补爬] {celebrity}: 已有 {existing} 首, 还差 {need} 首")
                continue

            logger.info(f"开始爬取 [{celebrity}] 的语音数据 (已有{existing}首, 需补{need}首)...")

            # 两轮搜索关键词: 常规 → 追加 live
            search_keywords = [celebrity, f"{celebrity} live"]

            for keyword in search_keywords:
                if existing >= max_videos_per_celebrity:
                    break

                is_live_retry = (keyword != celebrity)
                if is_live_retry:
                    logger.info(f"  [Live搜索] 常规搜索不够，尝试 '{keyword}'...")

                for platform in self.platforms:
                    try:
                        # 重新检查现有数量（可能在上一平台下载了）
                        existing = len([f for f in celeb_raw.rglob('*')
                                       if f.is_file() and f.suffix.lower() in audio_exts]) if celeb_raw.exists() else 0
                        if existing >= max_videos_per_celebrity:
                            break

                        # 搜索 + 动态翻页：确保至少凑满1首有效歌曲
                        logger.info(f"  -> 在 {platform.platform_name} 上搜索 '{keyword}'...")
                        total_needed = max_videos_per_celebrity - existing
                        results = []

                        # Bilibili search 不支持 page 参数，只搜一次
                        supports_paging = hasattr(platform, '_search_via_rpc')
                        if supports_paging:
                            for page in range(5):  # 最多5页(30×5=150条)
                                page_results = platform.search(keyword, max_results=30, page=page)
                                results.extend(page_results)
                                if len(results) >= total_needed:
                                    break
                        else:
                            results = platform.search(keyword, max_results=30)

                        logger.info(f"     共 {len(results)} 个资源")

                        if not results:
                            continue

                        # 逐个下载直到凑满 max_videos_per_celebrity 首有效歌曲
                        downloaded = 0
                        for i, item in enumerate(results):
                            need = max_videos_per_celebrity - existing
                            if downloaded >= need:
                                break

                            save_dir = platform.get_save_dir(celebrity)
                            filename = platform.sanitize_filename(f"{downloaded:03d}_{item['title']}")
                            save_path = str(save_dir / f"{filename}.wav")
                            # 避免覆盖已有文件（旧版流水线残留的同名无效文件）
                            counter = 0
                            while os.path.exists(save_path):
                                counter += 1
                                filename = platform.sanitize_filename(f"{downloaded:03d}_{item['title']}_{counter}")
                                save_path = str(save_dir / f"{filename}.wav")

                            logger.info(f"     下载 [{downloaded+1}/{need}]: {item['title'][:40]}...")
                            success = platform.download(item["url"], save_path)

                            if success:
                                platform.save_metadata(celebrity, {
                                    "title": item["title"],
                                    "url": item["url"],
                                    "duration": item["duration"],
                                    "file_path": save_path,
                                })
                                downloaded += 1
                                existing += 1
                                logger.info(f"     下载成功 ({downloaded}/{need})")

                            time.sleep(2)

                        # 如果当前平台已凑满，不再尝试后续平台
                        if existing >= max_videos_per_celebrity:
                            break

                    except Exception as e:
                        logger.error(f"     [{platform.platform_name}] 爬取失败: {e}")
                        continue

                # 如果当前关键词已凑满，不进入 live 搜索
                if existing >= max_videos_per_celebrity:
                    break

            logger.info(f"[{celebrity}] 爬取完成\n")

        if dry_run:
            total_deficient = len(self.celebrities) - skipped
            logger.info(f"\n[DRY RUN] 扫描完毕: {skipped} 位已满足, {total_deficient} 位需要补爬")


if __name__ == "__main__":
    scheduler = CrawlerScheduler()
    scheduler.run()
