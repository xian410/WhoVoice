"""
YouTube爬虫
使用 yt-dlp 搜索并下载中文访谈/播客类视频
"""

import subprocess
import json
import sys
import os
from pathlib import Path
from crawler.base_crawler import BaseCrawler


class YouTubeCrawler(BaseCrawler):
    """YouTube爬虫实现"""

    def __init__(self, config: dict):
        super().__init__("youtube", config)
        # 查找 deno 运行时
        self.deno_path = self._find_deno()

    def _find_deno(self) -> str:
        """查找 deno 可执行文件路径"""
        # 刷新 PATH
        os.environ["PATH"] = (
            os.environ.get("PATH", "")
            + os.pathsep
            + os.environ.get("LOCALAPPDATA", "")
            + r"\Microsoft\WinGet\Links"
        )
        for path in [
            r"C:\Users\17367\AppData\Local\Microsoft\WinGet\Links\deno.exe",
        ]:
            if os.path.exists(path):
                print(f"[YouTube] 找到 deno 运行时: {path}")
                return path
        print("[YouTube] 未找到 deno 运行时")
        return ""

    def search(self, keyword: str, max_results: int = 50) -> list:
        """
        搜索 YouTube 视频
        返回视频信息列表: [{"title": ..., "url": ..., "duration": ...}, ...]
        """
        search_limit = min(max_results, self.config.get("search_limit", 50))
        results = []

        # 尝试多种搜索词，最大化找到歌曲的可能性
        queries = [
            f"{keyword} 歌曲",
            f"{keyword} official audio",
            f"{keyword} MV",
        ]
        seen_urls = set()
        for query in queries:
            try:
                cmd = [
                    sys.executable, "-m", "yt_dlp",
                    f"ytsearch{search_limit}:{query}",
                    "--dump-json",
                    "--flat-playlist",
                    "--no-playlist",
                    "--default-search", "ytsearch",
                    "--socket-timeout", "15",
                ]
                output = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
                for line in output.stdout.strip().split("\n"):
                    if not line:
                        continue
                    info = json.loads(line)
                    duration = info.get("duration", 0)
                    url = info.get("webpage_url", "")
                    if not self._is_valid_duration(duration) or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    results.append({
                        "title": info.get("title", ""),
                        "url": url,
                        "duration": duration,
                        "channel": info.get("channel", ""),
                    })
            except Exception as e:
                print(f"[YouTube] 搜索 '{query}' 失败: {e}")

        return results

    def download(self, url: str, save_path: str) -> bool:
        """
        使用 yt-dlp 下载音频
        输出 WAV 格式，限制最大大小和时长
        """
        try:
            cmd = [
                sys.executable, "-m", "yt_dlp",
                "-f", "bestaudio[ext=m4a]/bestaudio",
                "--extract-audio",
                "--audio-format", "wav",
                "--audio-quality", "0",
                "--postprocessor-args", "ffmpeg:-ac 1 -ar 16000",
                "--max-filesize", "50M",
                "--match-filter", "duration < 360",
            ]
            if self.deno_path:
                cmd += ["--js-runtimes", f"deno:{self.deno_path}"]
            cmd += [
                "-o", save_path.replace(".wav", ".%(ext)s"),
                "--ignore-errors",
                url,
            ]
            subprocess.run(cmd, check=True, timeout=600)
            return True
        except Exception as e:
            print(f"[YouTube] 下载失败 {url}: {e}")
            return False

    def _is_valid_duration(self, duration_seconds: int) -> bool:
        """检查视频时长是否在合理范围内"""
        min_dur = self.config.get("min_duration", 30)
        max_dur = self.config.get("max_duration", 3600)
        return min_dur <= duration_seconds <= max_dur
