"""
酷狗音乐爬虫
通过酷狗音乐 API 搜索和下载歌曲音频
（使用 PC 客户端 API 和 trackercdn 两种方式获取下载链接）
"""

import hashlib
import requests
import subprocess
from pathlib import Path
from crawler.base_crawler import BaseCrawler


class KugouMusicCrawler(BaseCrawler):
    """酷狗音乐爬虫"""

    def __init__(self, config: dict):
        super().__init__("kugou_music", config)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "http://www.kugou.com/",
        })

    def search(self, keyword: str, max_results: int = 10) -> list:
        search_limit = min(max_results, self.config.get("search_limit", 10))
        results = []
        try:
            results = self._search_via_mobile_api(keyword, search_limit)
        except Exception as e:
            print(f"[酷狗音乐] 搜索失败: {e}")
        return results

    def _search_via_mobile_api(self, keyword: str, limit: int) -> list:
        results = []
        url = "http://mobilecdn.kugou.com/api/v3/search/song"
        params = {"format": "json", "keyword": keyword, "page": 1, "pagesize": limit}
        resp = self.session.get(url, params=params, timeout=15)
        data = resp.json()

        for item in data.get("data", {}).get("info", []):
            singer = item.get("singername", "")
            song_name = item.get("songname", "")
            h = item.get("hash", "").upper()
            album_id = item.get("album_id", "")
            duration = int(item.get("duration", 0))

            if keyword not in singer:
                continue
            if not self._is_valid_duration(duration):
                continue

            results.append({
                "title": f"{singer} - {song_name}",
                "url": f"kugou://{h}?album_id={album_id}",
                "duration": duration,
                "author": singer,
                "hash": h,
                "album_id": album_id,
                "source": "kugou_music",
            })
        return results

    def _get_play_url(self, hash_val: str) -> str:
        """获取 Kugou 歌曲的真实下载 URL"""
        methods = [
            self._try_pc_api,
            self._try_trackercdn_v2,
            self._try_web_api,
        ]
        for method in methods:
            try:
                url = method(hash_val)
                if url:
                    return url
            except Exception:
                continue
        return ""

    def _try_pc_api(self, hash_val: str) -> str:
        """方法1: PC客户端API"""
        key = hashlib.md5(f"{hash_val}kgcloudv2".encode()).hexdigest()
        r = self.session.get("http://trackercdn.kugou.com/i/v2/", params={
            "appid": 1005, "pid": 2, "cmd": 25, "behavior": "play",
            "hash": hash_val, "key": key,
        }, timeout=10)
        d = r.json()
        return d.get("url", "")

    def _try_trackercdn_v2(self, hash_val: str) -> str:
        """方法2: trackercdn 直链"""
        r = self.session.get(f"http://trackercdn.kugou.com/i/", params={
            "cmd": 4, "hash": hash_val, "key": hashlib.md5(f"{hash_val}kgcloud".encode()).hexdigest(),
            "pid": 1, "forceDown": 0, "vip": 1,
        }, timeout=10)
        d = r.json()
        return d.get("url", "")

    def _try_web_api(self, hash_val: str) -> str:
        """方法3: Web播放页API"""
        r = self.session.get("http://www.kugou.com/yy/index.php", params={
            "r": "play/getdata", "hash": hash_val, "mid": "1234567890"
        }, timeout=10, headers={"Cookie": ""})
        d = r.json()
        if d.get("data"):
            return d["data"].get("play_url", "")
        return ""

    def download(self, url: str, save_path: str) -> bool:
        # 从 URL 提取 hash
        if "kugou://" in url:
            hash_val = url.replace("kugou://", "").split("?")[0]
        else:
            return False

        play_url = self._get_play_url(hash_val)
        if not play_url:
            print(f"[酷狗音乐] 无法获取下载链接: {hash_val[:16]}...")
            return False

        try:
            import os, subprocess
            tmp_mp3 = save_path.replace(".wav", "_tmp.mp3")
            resp = self.session.get(play_url, timeout=300, stream=True)
            if resp.status_code != 200:
                print(f"[酷狗音乐] 下载失败: HTTP {resp.status_code}")
                return False

            with open(tmp_mp3, "wb") as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)

            # ffmpeg 转码
            from crawler.kuwo_music_crawler import KuwoMusicCrawler
            ffmpeg = KuwoMusicCrawler._find_ffmpeg()
            env = KuwoMusicCrawler._get_ffmpeg_env()
            subprocess.run([ffmpeg, "-i", tmp_mp3, "-acodec", "pcm_s16le",
                          "-ac", "1", "-ar", "16000", "-y", save_path],
                         check=True, timeout=120, capture_output=True, env=env)
            if os.path.exists(tmp_mp3):
                os.remove(tmp_mp3)
            print(f"[酷狗音乐] 下载成功")
            return True
        except Exception as e:
            print(f"[酷狗音乐] 下载异常: {e}")
            return False

    def extract_audio_id(self, url: str) -> str:
        if "kugou://" in url:
            return url.replace("kugou://", "").split("?")[0]
        return url

    def _is_valid_duration(self, duration_seconds: int) -> bool:
        min_dur = self.config.get("min_duration", 30)
        max_dur = self.config.get("max_duration", 600)
        return min_dur <= duration_seconds <= max_dur
