import subprocess
import json
import sys
import requests
import re
from pathlib import Path
from crawler.base_crawler import BaseCrawler


class BilibiliCrawler(BaseCrawler):
    """B站爬虫实现 —— 只爬取歌手歌曲视频，时长≤6分钟"""

    def __init__(self, config: dict):
        super().__init__("bilibili", config)
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.bilibili.com",
            "Origin": "https://www.bilibili.com",
        }

        # 从cookies.txt自动加载B站Cookie
        self.cookies_file = config.get("cookies_file", "cookies.txt")
        self.cookies = self._load_bilibili_cookies()

    def _load_bilibili_cookies(self) -> dict:
        """从cookies.txt提取B站关键Cookie"""
        cookies = {}
        ck_path = Path(self.cookies_file)
        if not ck_path.exists():
            print("[Bilibili] cookies.txt 不存在，API搜索将不可用")
            return cookies

        # 只加载关键设备标识Cookie（过多Cookie会触发WAF）
        key_cookies = {"buvid3", "buvid4", "b_lsid", "b_nut", "fingerprint", "_uuid", "rpdid"}

        with open(ck_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 7 and "bilibili" in parts[0]:
                    name = parts[5]
                    if name in key_cookies:
                        cookies[name] = parts[6]

        if cookies:
            print(f"[Bilibili] 已加载 {len(cookies)} 个关键Cookie")
        return cookies

    def search(self, keyword: str, max_results: int = 50) -> list:
        """
        搜索 B站 视频
        优先使用 B站 API（带Cookie），失败则回退到 yt-dlp
        只搜索：歌曲、原唱、MV、完整版、现场演唱
        时长限制：≤6分钟
        """
        search_limit = min(max_results, self.config.get("search_limit", 50))

        # 方案一：B站 API 搜索（带Cookie）
        if self.cookies:
            results = self._search_via_api(keyword, search_limit)
            if results:
                return results

        # 方案二：yt-dlp 搜索（多关键词兜底）
        print("[Bilibili] API搜索无结果，尝试 yt-dlp 搜索...")
        return self._search_via_ytdlp(keyword, search_limit)

    def _search_via_ytdlp(self, keyword: str, limit: int) -> list:
        """
        使用 yt-dlp 搜索 B站 歌曲视频
        只搜：歌曲、MV、原唱、完整版
        """
        results = []
        seen_urls = set()
        
        # ====================== 核心修改 1 ======================
        # 只搜索歌曲相关，彻底去掉访谈/采访/综艺
        search_queries = [
            f"bilibili:{keyword} 歌曲",
            f"bilibili:{keyword} MV",
            f"bilibili:{keyword} 原唱",
            f"bilibili:{keyword} 完整版",
            f"bilibili:{keyword} 现场演唱",
        ]

        try:
            for query in search_queries:
                if len(results) >= limit:
                    break

                cmd = [
                    sys.executable, "-m", "yt_dlp",
                    f"ytsearch{limit}:{query}",
                    "--dump-json",
                    "--no-playlist",
                    "--default-search", "ytsearch",
                    "--ignore-errors",
                ]
                output = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=30
                )

                for line in output.stdout.strip().split("\n"):
                    if not line or len(results) >= limit:
                        continue
                    info = json.loads(line)
                    url = info.get("webpage_url", "")
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    duration = info.get("duration", 0)
                    if self._is_valid_duration(duration):
                        results.append({
                            "title": info.get("title", ""),
                            "url": url,
                            "duration": duration,
                            "author": info.get("channel", ""),
                            "source": "ytdlp",
                        })

        except FileNotFoundError:
            print("[Bilibili] yt-dlp 未安装，无法使用方案一")
        except Exception as e:
            print(f"[Bilibili] yt-dlp 搜索异常: {e}")

        return results

    def _search_via_api(self, keyword: str, limit: int) -> list:
        """
        通过 B站搜索 API 搜索歌曲视频
        只搜：歌曲、MV、原唱、完整版
        """
        results = []

        cookie_str = "; ".join([f"{k}={v}" for k, v in self.cookies.items()])
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/139.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.bilibili.com/",
            "Accept": "application/json, text/plain, */*",
            "Cookie": cookie_str,
        }

        # ====================== 核心修改 2 ======================
        # API 只搜索歌曲，去掉所有访谈类关键词
        search_queries = [
            f"{keyword} 歌曲",
            f"{keyword} MV",
            f"{keyword} 原唱",
            f"{keyword} 完整版",
        ]

        seen_bvids = set()
        for query in search_queries:
            if len(results) >= limit:
                break

            try:
                resp = requests.get(
                    "https://api.bilibili.com/x/web-interface/search/all/v2",
                    params={"keyword": query},
                    headers=headers,
                    timeout=15,
                )
                data = resp.json()

                if data.get("code") == 0:
                    sections = data.get("data", {}).get("result", [])
                    for section in sections:
                        if section.get("result_type") != "video":
                            continue
                        videos = section.get("data", [])
                        for v in videos:
                            if len(results) >= limit:
                                break
                            bvid = v.get("bvid", "")
                            if bvid in seen_bvids:
                                continue
                            seen_bvids.add(bvid)

                            duration_str = v.get("duration", "0:00")
                            duration = self._parse_duration(duration_str)
                            if self._is_valid_duration(duration):
                                results.append({
                                    "title": re.sub(r"<[^>]+>", "", v.get("title", "")),
                                    "url": f"https://www.bilibili.com/video/{bvid}",
                                    "duration": duration,
                                    "author": v.get("author", ""),
                                    "source": "api",
                                })
                elif data.get("code") == -412:
                    print("[Bilibili] API 被拦截(-412)，Cookie 可能过期")
                    return results

            except Exception as e:
                print(f"[Bilibili] API 搜索失败: {e}")

        return results

    def _parse_duration(self, duration_str: str) -> int:
        """将B站时长格式(MM:SS 或 HH:MM:SS)转为秒数"""
        try:
            parts = duration_str.strip().split(":")
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        except (ValueError, IndexError):
            pass
        return 0

    def download(self, url: str, save_path: str) -> bool:
        """
        使用 yt-dlp 下载 B站 视频并提取音频
        输出: 16kHz 单声道 WAV
        """
        try:
            cmd = [
                sys.executable, "-m", "yt_dlp",
                "-f", "bestaudio/best",
                "--extract-audio",
                "--audio-format", "wav",
                "--audio-quality", "0",
                "--postprocessor-args", "ffmpeg:-ac 1 -ar 16000",
                "-o", save_path.replace(".wav", ".%(ext)s"),
                "--ignore-errors",
            ]

            # 如果有Cookie文件，带上它（B站下载需要Cookie）
            if self.cookies and Path(self.cookies_file).exists():
                cmd += ["--cookies", self.cookies_file]

            cmd.append(url)

            subprocess.run(cmd, check=True, capture_output=True, timeout=600)
            return True
        except FileNotFoundError:
            print("[Bilibili] yt-dlp 未安装，请先安装: pip install yt-dlp")
            return False
        except Exception as e:
            print(f"[Bilibili] 下载失败 {url}: {e}")
            return False

    def _is_valid_duration(self, duration_seconds: int) -> bool:
        """
        ====================== 核心修改 3 ======================
        强制：视频时长 ≤ 6分钟（360秒）
        最短30秒，最长360秒
        """
        min_dur = 30
        max_dur = 360  # 6分钟 = 360秒
        return min_dur <= duration_seconds <= max_dur