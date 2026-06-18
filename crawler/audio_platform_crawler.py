"""
音频平台爬虫
从喜马拉雅、荔枝FM等平台下载明星相关音频
"""

import requests
import re
import json
from pathlib import Path
from crawler.base_crawler import BaseCrawler


class AudioPlatformCrawler(BaseCrawler):
    """音频平台爬虫实现"""

    def __init__(self, config: dict):
        super().__init__("audio_platform", config)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.ximalaya.com",
            "Origin": "https://www.ximalaya.com",
        })

        # 从 config 读取 Cookie（可选，不配置也能搜，但结果可能受限）
        xm_cookie = config.get("ximalaya_cookie", "")
        if xm_cookie:
            self.session.headers["Cookie"] = xm_cookie

    def search(self, keyword: str, max_results: int = 50) -> list:
        """
        搜索音频平台内容
        返回音频信息列表: [{"title": ..., "url": ..., "duration": ...}, ...]
        """
        results = []
        search_limit = min(max_results, self.config.get("search_limit", 50))

        # 喜马拉雅搜索
        try:
            ximalaya_results = self._search_ximalaya(keyword, search_limit)
            results.extend(ximalaya_results)
        except Exception as e:
            print(f"[音频平台] 喜马拉雅搜索失败: {e}")

        return results

    def _search_ximalaya(self, keyword: str, limit: int) -> list:
        """
        喜马拉雅搜索
        使用 revision/search/main 接口
        """
        results = []

        # 1. 搜索专辑（访谈类节目）
        url = "https://www.ximalaya.com/revision/search/main"
        params = {
            "core": "album",
            "keyword": f"{keyword} 访谈 语音",
            "page": 1,
            "rows": limit,
            "spellchecker": "true",
            "device": "web",
        }
        resp = self.session.get(url, params=params, timeout=15)

        if resp.status_code != 200:
            print(f"[喜马拉雅] HTTP {resp.status_code}")
            return results

        try:
            data = resp.json()
        except json.JSONDecodeError:
            print("[喜马拉雅] 响应解析失败")
            return results

        # 喜马拉雅新版 API 返回结构可能变化，兼容处理
        album_data = data.get("data", {})
        if isinstance(album_data, dict):
            albums = album_data.get("album", {}).get("docs", [])
        elif isinstance(album_data, list):
            albums = album_data
        else:
            albums = []

        for album in albums[:limit]:
            # 兼容不同版本的字段名
            title = album.get("title") or album.get("albumTitle") or ""
            kind = album.get("kind") or album.get("type") or "album"
            album_id = album.get("id") or album.get("albumId") or 0
            nickname = album.get("nickname") or album.get("authorName") or ""
            duration = album.get("duration") or album.get("lastUptrackAt") or 0

            results.append({
                "title": title,
                "url": f"https://www.ximalaya.com/{kind}/{album_id}",
                "duration": duration,
                "author": nickname,
                "source": "ximalaya",
            })

        return results

    def download(self, url: str, save_path: str) -> bool:
        """
        下载音频文件
        使用 yt-dlp 下载，支持喜马拉雅、荔枝FM等
        """
        try:
            import subprocess
            cmd = [
                "yt-dlp",
                "-f", "bestaudio/best",
                "--extract-audio",
                "--audio-format", "wav",
                "--audio-quality", "0",
                "--postprocessor-args", "ffmpeg:-ac 1 -ar 16000",
                "-o", save_path.replace(".wav", ".%(ext)s"),
                "--ignore-errors",
                url,
            ]
            subprocess.run(cmd, check=True, timeout=600)
            return True
        except FileNotFoundError:
            print("[音频平台] yt-dlp 未安装，请先安装: brew install yt-dlp")
            return False
        except Exception as e:
            print(f"[音频平台] 下载失败 {url}: {e}")
            return False

    def extract_audio_id(self, url: str) -> str:
        """从 URL 中提取音频 ID"""
        match = re.search(r'/(\d+)$', url)
        return match.group(1) if match else ""
