"""
YouTube爬虫
使用 yt-dlp 搜索并下载中文访谈/播客类视频
"""

import subprocess
import json
from pathlib import Path
from crawler.base_crawler import BaseCrawler


class YouTubeCrawler(BaseCrawler):
    """YouTube爬虫实现"""

    def __init__(self, config: dict):
        super().__init__("youtube", config)

    def search(self, keyword: str, max_results: int = 50) -> list:
        """
        搜索 YouTube 视频
        返回视频信息列表: [{"title": ..., "url": ..., "duration": ...}, ...]
        """
        search_limit = min(max_results, self.config.get("search_limit", 50))
        results = []

        try:
            query = f"{keyword} 访谈 interview"
            cmd = [
                "yt-dlp",
                f"ytsearch{search_limit}:{query}",
                "--dump-json",
                "--no-playlist",
                "--default-search", "ytsearch",
            ]
            output = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            for line in output.stdout.strip().split("\n"):
                if not line:
                    continue
                info = json.loads(line)
                duration = info.get("duration", 0)
                if self._is_valid_duration(duration):
                    results.append({
                        "title": info.get("title", ""),
                        "url": info.get("webpage_url", ""),
                        "duration": duration,
                        "channel": info.get("channel", ""),
                    })
        except Exception as e:
            print(f"[YouTube] 搜索失败: {e}")

        return results

    def download(self, url: str, save_path: str) -> bool:
        """
        使用 yt-dlp 下载音频
        输出 WAV 格式
        """
        try:
            cmd = [
                "yt-dlp",
                "-f", "bestaudio[ext=m4a]/bestaudio",
                "--extract-audio",
                "--audio-format", "wav",
                "--audio-quality", "0",
                "--postprocessor-args", "ffmpeg:-ac 1 -ar 16000",
                "-o", save_path.replace(".wav", ".%(ext)s"),
                url,
            ]
            subprocess.run(cmd, check=True, capture_output=True, timeout=600)
            return True
        except Exception as e:
            print(f"[YouTube] 下载失败 {url}: {e}")
            return False

    def _is_valid_duration(self, duration_seconds: int) -> bool:
        """检查视频时长是否在合理范围内"""
        min_dur = self.config.get("min_duration", 30)
        max_dur = self.config.get("max_duration", 3600)
        return min_dur <= duration_seconds <= max_dur
