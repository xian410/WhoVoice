"""
酷我音乐爬虫
通过酷我音乐 API 搜索明星歌曲并下载纯净 MP3 音频
（直接是录音室版，无访谈杂音，最适合声纹提取）
"""

import ast
import requests
from pathlib import Path
from crawler.base_crawler import BaseCrawler


class KuwoMusicCrawler(BaseCrawler):
    """酷我音乐爬虫实现"""

    def __init__(self, config: dict):
        super().__init__("kuwo_music", config)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.kuwo.cn/",
        })

    def search(self, keyword: str, max_results: int = 10, page: int = 0) -> list:
        """
        搜索酷我音乐歌曲
        搜索量使用 config.search_limit，过滤合唱后再截取 max_results
        """
        fetch_size = self.config.get("search_limit", 30)
        results = []
        try:
            results = self._search_via_rpc(keyword, fetch_size, page=page)
        except Exception as e:
            print(f"[酷我音乐] 搜索失败: {e}")
        return results[:max_results]

    def _search_via_rpc(self, keyword: str, limit: int, page: int = 0) -> list:
        """
        通过 KVVC 搜索接口按歌手搜索歌曲
        """
        results = []
        url = "http://search.kuwo.cn/r.s"
        params = {
            "client": "kt",
            "all": keyword,
            "pn": page,
            "rn": limit,
            "encoding": "utf8",
            "rformat": "json",
            "show_copyright_off": 1,
            "source": "kwplayer_ar_5.2.0.0_apk",
            "vipver": 1,
            "ft": "music",  # 按类型过滤
        }

        resp = self.session.get(url, params=params, timeout=15)
        data = ast.literal_eval(resp.text)

        for item in data.get("abslist", []):
            artist = item.get("ARTIST", "")
            # 歌手名匹配：作品名包含关键词 或 完全匹配（兼容 G.E.M. 邓紫棋 等格式）
            if artist != keyword and keyword not in artist:
                continue

            music_id = item.get("MUSICRID", "")
            song_name = item.get("NAME", "")
            duration_sec = int(item.get("DURATION", 0))

            # 过滤多人合唱（声纹提取仅支持单人）
            if self._is_collaboration(song_name) or self._is_collaboration(artist):
                print(f"  [酷我音乐] 跳过合唱: {artist} - {song_name}")
                continue

            # 检查时长有效性
            if not self._is_valid_duration(duration_sec):
                continue

            results.append({
                "title": f"{artist} - {song_name}",
                "url": f"https://www.kuwo.cn/play_detail/{music_id}",
                "duration": duration_sec,
                "author": artist,
                "music_id": music_id,
                "source": "kuwo_music",
            })

        return results

    def download(self, url: str, save_path: str) -> bool:
        """
        通过 kuwo antiserver 接口下载 MP3 音频
        输出: 16kHz 单声道 WAV（通过 ffmpeg 转码）
        """
        # 从 URL 中提取 music_id
        music_id = self.extract_audio_id(url)
        if not music_id:
            print(f"[酷我音乐] 无法提取歌曲ID: {url}")
            return False

        # 获取真实下载 URL
        dl_url = self._get_real_download_url(music_id)
        if not dl_url:
            return False

        try:
            # 下载 MP3 到临时文件
            import subprocess
            import os

            tmp_mp3 = save_path.replace(".wav", "_tmp.mp3")
            resp = self.session.get(dl_url, timeout=300, stream=True)
            if resp.status_code != 200:
                print(f"[酷我音乐] 下载失败: HTTP {resp.status_code}")
                return False

            with open(tmp_mp3, "wb") as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)

            # 用 ffmpeg 转码为 16kHz 单声道 WAV
            ffmpeg_path = self._find_ffmpeg()
            cmd = [
                ffmpeg_path, "-i", tmp_mp3,
                "-acodec", "pcm_s16le",
                "-ac", "1",
                "-ar", "16000",
                "-y", save_path,
            ]
            subprocess.run(cmd, check=True, timeout=120,
                           capture_output=True, text=False,  # 二进制输出，避免 GBK 解码错误
                           env=self._get_ffmpeg_env())

            # 清理临时 MP3
            if os.path.exists(tmp_mp3):
                os.remove(tmp_mp3)

            # 校验时长：酷我常返回11秒预览片段
            if not self._check_duration(save_path, min_sec=15):
                os.remove(save_path)
                print(f"[酷我音乐] 预览片段(不足15s)，跳过")
                return False

            print(f"[酷我音乐] 下载成功: {save_path}")
            return True

        except subprocess.CalledProcessError as e:
            print(f"[酷我音乐] ffmpeg 转码失败: {e.stderr[:200]}")
            return False
        except Exception as e:
            print(f"[酷我音乐] 下载失败: {e}")
            return False

    def _get_real_download_url(self, music_id: str) -> str:
        """通过 anti 接口获取真实下载 URL（尝试多种格式）"""
        rid = music_id.replace("MUSIC_", "").replace("MP3_", "")

        # 多种尝试参数
        attempts = [
            {"type": "convert_url", "rid": rid, "format": "mp3", "response": "url"},
            {"type": "convert_url", "rid": rid, "format": "aac", "response": "url"},
            {"type": "convert_url", "rid": rid, "format": "mp3", "response": "url", "br": "192"},
            {"type": "convert_url", "rid": rid, "format": "wma", "response": "url"},
        ]

        for params in attempts:
            try:
                resp = self.session.get("http://antiserver.kuwo.cn/anti.s",
                                        params=params, timeout=15)
                dl_url = resp.text.strip()
                if "http" in dl_url and "antiserver" not in dl_url:
                    return dl_url
            except Exception:
                continue

        print(f"[酷我音乐] 所有格式均无法获取下载链接: {music_id}")
        return ""

    @staticmethod
    def _check_duration(wav_path: str, min_sec: int = 15) -> bool:
        """用 ffprobe 检查 WAV 时长，过滤预览片段"""
        import subprocess, json
        ffprobe = r"C:\Users\17367\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg.Essentials_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-essentials_build\bin\ffprobe.exe"
        try:
            r = subprocess.run([ffprobe, "-v", "quiet", "-print_format", "json", "-show_streams", wav_path],
                             capture_output=True, text=True, timeout=10)
            d = json.loads(r.stdout)
            dur = float(d.get("streams", [{}])[0].get("duration", 0))
            return dur >= min_sec
        except Exception:
            return True  # 无法检查时放行

    @staticmethod
    def _is_collaboration(song_name: str) -> bool:
        """检测是否为多人合唱歌曲"""
        indicators = [
            "\\u0026", "&", "合唱", "feat", "ft.", "ft ",
            "vs", "合作", "Duet", "对唱", "&amp;",
        ]
        name_lower = song_name.lower()
        return any(ind in name_lower for ind in indicators)

    @staticmethod
    def _find_ffmpeg() -> str:
        """查找系统中可用的 ffmpeg 完整路径"""
        # 优先使用包含 DLL 的完整安装路径
        ffmpeg_dirs = [
            Path(r"C:\Users\17367\AppData\Local\Microsoft\WinGet\Packages"
                 r"\Gyan.FFmpeg.Essentials_Microsoft.Winget.Source_8wekyb3d8bbwe"
                 r"\ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe"),
        ]
        for p in ffmpeg_dirs:
            if p.exists():
                return str(p.resolve())
        # fallback: 系统 PATH
        import shutil
        fallback = shutil.which("ffmpeg")
        return fallback or "ffmpeg"

    @staticmethod
    def _get_ffmpeg_env() -> dict:
        """获取包含 ffmpeg DLL 路径的环境变量"""
        import os
        env = os.environ.copy()
        ffmpeg_dir = Path(r"C:\Users\17367\AppData\Local\Microsoft\WinGet\Packages"
                          r"\Gyan.FFmpeg.Essentials_Microsoft.Winget.Source_8wekyb3d8bbwe"
                          r"\ffmpeg-8.1.1-essentials_build\bin")
        if ffmpeg_dir.exists():
            env["PATH"] = str(ffmpeg_dir) + os.pathsep + env.get("PATH", "")
        return env

    def extract_audio_id(self, url: str) -> str:
        """从 URL 中提取歌曲 ID"""
        import re
        # 支持多种 URL 格式
        # https://www.kuwo.cn/play_detail/MUSIC_123456
        # MP3_123456
        match = re.search(r'(?:MUSIC_|MP3_)(\d+)', url)
        if match:
            return f"MUSIC_{match.group(1)}"
        match = re.search(r'MUSIC_(\d+)', url)
        return match.group(0) if match else url

    def _is_valid_duration(self, duration_seconds: int) -> bool:
        """检查歌曲时长是否在合理范围内（30秒-10分钟）"""
        min_dur = self.config.get("min_duration", 30)
        max_dur = self.config.get("max_duration", 600)
        return min_dur <= duration_seconds <= max_dur
