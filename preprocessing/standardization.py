"""
音频标准化模块
将音频统一格式化为: 单声道, 16kHz, 16-bit PCM WAV
"""

import subprocess
import wave
import numpy as np
from pathlib import Path
from typing import Optional, Tuple


class AudioStandardizer:
    """音频标准化器"""

    def __init__(
        self,
        target_sr: int = 16000,
        target_channels: int = 1,
        target_bit_depth: int = 16,
    ):
        self.target_sr = target_sr
        self.target_channels = target_channels
        self.target_bit_depth = target_bit_depth

    def process(self, input_path: str, output_path: Optional[str] = None) -> str:
        """
        将音频标准化为标准格式
        使用 ffmpeg 处理

        Args:
            input_path: 输入音频路径
            output_path: 输出路径，默认在原文件名后加 _standardized

        Returns:
            输出文件路径
        """
        input_path = Path(input_path)
        if not input_path.exists():
            raise FileNotFoundError(f"输入文件不存在: {input_path}")

        if output_path is None:
            output_path = str(input_path.parent / f"{input_path.stem}_standardized.wav")

        cmd = [
            "ffmpeg",
            "-i", str(input_path),
            "-ac", str(self.target_channels),         # 声道数
            "-ar", str(self.target_sr),               # 采样率
            "-sample_fmt", "s16",                     # 16-bit signed PCM
            "-acodec", "pcm_s16le",                   # PCM 编码
            "-vn",                                    # 去除视频流
            "-y",                                     # 覆盖输出
            output_path,
        ]

        try:
            subprocess.run(cmd, check=True, timeout=120)
            return output_path
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"音频标准化失败")

    def get_audio_info(self, audio_path: str) -> dict:
        """
        获取音频文件信息
        使用 ffprobe（比 audioread 更轻量，不加载音频数据到内存）
        """
        import json
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            audio_path,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            data = json.loads(result.stdout)
            stream = data.get("streams", [{}])[0]
            duration_str = stream.get("duration", "0")
            try:
                duration = float(duration_str)
            except (ValueError, TypeError):
                duration = 0
            return {
                "channels": stream.get("channels", 1),
                "samplerate": int(stream.get("sample_rate", 16000)),
                "duration": duration,
                "format": stream.get("codec_name", "pcm_s16le"),
            }
        except (subprocess.TimeoutExpired, json.JSONDecodeError, IndexError, KeyError):
            # 兜底：用 audioread
            try:
                import audioread
                with audioread.audio_open(audio_path) as f:
                    return {
                        "channels": f.channels,
                        "samplerate": f.samplerate,
                        "duration": f.duration,
                        "format": str(f.format),
                    }
            except Exception:
                return {"channels": 1, "samplerate": 16000, "duration": 0, "format": "unknown"}

    def normalize_volume(self, audio_path: str, target_db: float = -3.0) -> str:
        """
        音量归一化
        使用 ffmpeg loudnorm 或简单增益调整
        """
        output_path = str(Path(audio_path).parent / f"{Path(audio_path).stem}_normalized.wav")

        cmd = [
            "ffmpeg",
            "-i", audio_path,
            "-af", f"loudnorm=I={target_db}:LRA=11:TP=-1.5",
            "-y", output_path,
        ]

        try:
            subprocess.run(cmd, check=True, timeout=120)
            return output_path
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"音量归一化失败")
