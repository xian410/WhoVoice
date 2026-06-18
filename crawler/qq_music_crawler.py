"""
QQ音乐爬虫
通过 QQ音乐开放 API 搜索明星歌曲，获取纯净人声音频
（无访谈杂音，直接是工作室录制的纯净人声）
"""

import requests
import json
import hashlib
import time
from pathlib import Path
from crawler.base_crawler import BaseCrawler


class QqMusicCrawler(BaseCrawler):
    """QQ音乐爬虫实现"""

    def __init__(self, config: dict):
        super().__init__("qq_music", config)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://y.qq.com",
            "Origin": "https://y.qq.com",
        })

        # 支持手动指定的Cookie文件
        self._cookies_file = config.get("cookies_file", "")
        self._cookie_detected = bool(self._cookies_file and Path(self._cookies_file).exists())
        if self._cookie_detected:
            print(f"[QQ音乐] 使用Cookie文件: {self._cookies_file}")

    def search(self, keyword: str, max_results: int = 50) -> list:
        """
        搜索QQ音乐的明星歌曲
        返回歌曲信息列表: [{"title": ..., "url": ..., "duration": ...}, ...]
        """
        search_limit = min(max_results, self.config.get("search_limit", 50))
        results = []

        # 方式一：QQ音乐智能搜索（推荐，返回结构化数据）
        results = self._search_via_smartbox(keyword, search_limit)
        if results:
            return results

        # 方式二：直接搜索歌曲
        results = self._search_via_cgi(keyword, search_limit)

        return results

    def _search_via_smartbox(self, keyword: str, limit: int) -> list:
        """
        使用 QQ音乐智能搜索接口
        URL: https://c.y.qq.com/splcloud/fcgi-bin/smartbox_new.fcg
        """
        results = []
        url = "https://c.y.qq.com/splcloud/fcgi-bin/smartbox_new.fcg"
        params = {
            "key": f"{keyword}",
            "platform": "yqq",
            "format": "json",
            "needNewCode": "0",
            "uin": "0",
        }

        try:
            resp = self.session.get(url, params=params, timeout=15)
            data = resp.json()

            # 解析歌手的歌曲列表
            singers = (
                data.get("data", {})
                .get("singer", {})
                .get("itemlist", [])
            )
            songs = (
                data.get("data", {})
                .get("song", {})
                .get("itemlist", [])
            )

            # 优先取歌曲结果
            for song in songs[:limit]:
                mid = song.get("mid", "")
                song_name = song.get("name", "")
                singer_name = song.get("singer", "")
                album_mid = song.get("album", {}).get("mid", "") if isinstance(
                    song.get("album"), dict
                ) else ""

                # 构造 QQ音乐播放页 URL
                song_url = (
                    f"https://y.qq.com/n/ryqq/songDetail/{mid}"
                    if mid else ""
                )

                if song_url:
                    results.append({
                        "title": f"{singer_name} - {song_name}",
                        "url": song_url,
                        "duration": 240,  # QQ音乐API不直接返回时长，默认4分钟
                        "author": singer_name,
                        "song_mid": mid,
                        "album_mid": album_mid,
                        "source": "qqmusic_smartbox",
                    })

            # 如果没有歌曲结果，尝试取歌手的代表歌曲列表
            if not results:
                for singer in singers[:3]:
                    singer_mid = singer.get("mid", "")
                    singer_name = singer.get("name", "")
                    # 通过歌手 mid 获取热门歌曲
                    hot_songs = self._get_singer_songs(
                        singer_mid, singer_name, limit
                    )
                    results.extend(hot_songs)

        except Exception as e:
            print(f"[QQ音乐] 智能搜索失败: {e}")

        return results

    def _search_via_cgi(self, keyword: str, limit: int) -> list:
        """
        通过 QQ音乐 CGI 搜索接口搜索歌曲
        """
        results = []
        url = "https://u.y.qq.com/cgi-bin/musicu.fcn"

        data = {
            "music.search.SearchCgiService": {
                "method": "DoSearchForQQMusicDesktop",
                "module": "music.search.SearchCgiService",
                "param": {
                    "grp": 1,
                    "num_per_page": limit,
                    "page_num": 1,
                    "query": keyword,
                    "search_type": 0,  # 0=歌曲
                },
            }
        }

        try:
            resp = self.session.post(
                url, json=data, timeout=15
            )
            result = resp.json()

            song_list = (
                result.get("music.search.SearchCgiService", {})
                .get("data", {})
                .get("body", {})
                .get("song", {})
                .get("list", [])
            )

            for song in song_list[:limit]:
                song_mid = song.get("mid", "")
                song_name = song.get("title", "")
                singer_name = (
                    song.get("singer", [{}])[0].get("name", "")
                    if song.get("singer")
                    else ""
                )
                duration = song.get("interval", 0)  # 单位：秒

                song_url = (
                    f"https://y.qq.com/n/ryqq/songDetail/{song_mid}"
                    if song_mid else ""
                )

                if song_url and self._is_valid_duration(duration):
                    results.append({
                        "title": f"{singer_name} - {song_name}",
                        "url": song_url,
                        "duration": duration,
                        "author": singer_name,
                        "song_mid": song_mid,
                        "source": "qqmusic_cgi",
                    })

        except Exception as e:
            print(f"[QQ音乐] CGI搜索失败: {e}")

        return results

    def _get_singer_songs(
        self, singer_mid: str, singer_name: str, limit: int
    ) -> list:
        """
        通过歌手 MID 获取热门歌曲
        """
        results = []
        if not singer_mid:
            return results

        url = "https://u.y.qq.com/cgi-bin/musicu.fcn"
        data = {
            "music.musichallSong.PlayList.PlayListGet": {
                "method": "GetPlayList",
                "module": "music.musichallSong.PlayList.PlayListGet",
                "param": {
                    "singerMid": singer_mid,
                    "tab": 1,  # 热门歌曲
                    "num": limit,
                    "start": 0,
                },
            }
        }

        try:
            resp = self.session.post(url, json=data, timeout=15)
            result = resp.json()

            song_list = (
                result.get(
                    "music.musichallSong.PlayList.PlayListGet", {}
                )
                .get("data", {})
                .get("songList", [])
            )

            for item in song_list[:limit]:
                song = item.get("songInfo", {})
                song_mid = song.get("mid", "")
                song_name = song.get("title", "")
                duration = song.get("interval", 0)

                song_url = (
                    f"https://y.qq.com/n/ryqq/songDetail/{song_mid}"
                    if song_mid else ""
                )

                if song_url and self._is_valid_duration(duration):
                    results.append({
                        "title": f"{singer_name} - {song_name}",
                        "url": song_url,
                        "duration": duration,
                        "author": singer_name,
                        "song_mid": song_mid,
                        "source": "qqmusic_singer",
                    })

        except Exception as e:
            print(f"[QQ音乐] 获取歌手歌曲失败: {e}")

        return results

    def download(self, url: str, save_path: str) -> bool:
        """
        使用 yt-dlp 下载 QQ音乐 音频
        输出: 16kHz 单声道 WAV
        """
        try:
            import subprocess
            import os
            import sys

            base_cmd = [
                sys.executable, "-m", "yt_dlp",
                "-f", "bestaudio/best",
                "--extract-audio",
                "--audio-format", "wav",
                "--audio-quality", "0",
                "--postprocessor-args", "ffmpeg:-ac 1 -ar 16000",
                "-o", save_path.replace(".wav", ".%(ext)s"),
                "--ignore-errors",
            ]

            # 如果已指定有效的Cookie文件，带上它
            if self._cookie_detected:
                cmd = base_cmd + ["--cookies", self._cookies_file, url]
            else:
                cmd = base_cmd + [url]

            subprocess.run(cmd, check=True, timeout=600)
            return True

        except FileNotFoundError:
            print("[QQ音乐] yt-dlp 未安装，请先安装: pip install yt-dlp")
            return False
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode() if hasattr(e.stderr, 'decode') else str(e.stderr)
            if "registered users" in stderr:
                self._print_cookie_guide()
            else:
                print(f"[QQ音乐] 下载失败: {e}")
            return False
        except Exception as e:
            print(f"[QQ音乐] 下载失败 {url}: {e}")
            return False

    def _print_cookie_guide(self):
        """打印Cookie导出指引"""
        print(f"\n{'='*60}")
        print("  QQ音乐下载需要登录认证")
        print(f"{'='*60}")
        print("  原因: macOS 沙箱保护了浏览器Cookie文件，无法自动读取")
        print()
        print("  解决方案（只需操作一次）:")
        print()
        print("  Step 1: 在 Chrome/Safari 中登录 https://y.qq.com")
        print()
        print("  Step 2: 在终端执行以下命令导出Cookie:")
        print("    yt-dlp --cookies-from-browser chrome --cookies cookies.txt")
        print()
        print("  Step 3: 将 cookies.txt 放入项目根目录")
        print()
        print("  Step 4: 修改 crawler/config.py 取消注释:")
        print('    QQ_MUSIC["cookies_file"] = "cookies.txt"')
        print()
        print("  Step 5: 重新运行爬虫即可下载")
        print("=" * 60)

    def _is_valid_duration(self, duration_seconds: int) -> bool:
        """检查歌曲时长是否在合理范围内（1-10分钟）"""
        return 60 <= duration_seconds <= 600
