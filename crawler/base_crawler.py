"""
爬虫基类
定义所有爬虫共用的接口和通用方法
"""

import os
import json
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime


class BaseCrawler(ABC):
    """爬虫基类，所有平台爬虫需继承此类"""

    def __init__(self, platform_name: str, config: dict):
        self.platform_name = platform_name
        self.config = config

    @abstractmethod
    def search(self, keyword: str, max_results: int = 50) -> list:
        """搜索关键词，返回资源列表"""
        pass

    @abstractmethod
    def download(self, url: str, save_path: str) -> bool:
        """下载资源到指定路径"""
        pass

    def extract_audio(self, video_path: str, audio_path: str) -> bool:
        """
        使用 ffmpeg 从视频中提取音频
        输出格式: 单声道 16kHz 16-bit PCM WAV
        """
        try:
            cmd = [
                "ffmpeg", "-i", video_path,
                "-vn",                     # 去除视频流
                "-acodec", "pcm_s16le",    # 16-bit PCM
                "-ac", "1",                # 单声道
                "-ar", "16000",            # 16kHz 采样率
                "-y",                      # 覆盖输出文件
                audio_path
            ]
            subprocess.run(cmd, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"[{self.platform_name}] 音频提取失败: {e}")
            return False

    def save_metadata(self, celebrity: str, metadata: dict) -> None:
        """保存元数据到 JSON 文件"""
        metadata_dir = Path("data/metadata")
        metadata_dir.mkdir(parents=True, exist_ok=True)
        file_path = metadata_dir / f"{celebrity}_{self.platform_name}.json"

        records = []
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                records = json.load(f)

        metadata["download_time"] = datetime.now().isoformat()
        metadata["platform"] = self.platform_name
        records.append(metadata)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

    def get_save_dir(self, celebrity: str) -> Path:
        """获取明星数据保存目录"""
        save_dir = Path(f"data/raw/{celebrity}/{self.platform_name}")
        save_dir.mkdir(parents=True, exist_ok=True)
        return save_dir

    def sanitize_filename(self, filename: str) -> str:
        """清理文件名中的非法字符"""
        invalid_chars = r'<>:"/\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, "_")
        return filename[:200]  # 限制文件名长度
