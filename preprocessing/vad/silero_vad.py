"""
Silero VAD 语音端点检测实现
使用 silero-vad pip 包（本地加载，无需联网下载）
"""

import torch
import torchaudio
import numpy as np
from pathlib import Path
from typing import List, Tuple

from silero_vad.model import load_silero_vad
from silero_vad.utils_vad import get_speech_timestamps


class SileroVAD:
    """Silero VAD 端点检测器"""

    def __init__(self, threshold: float = 0.5, min_speech_duration: float = 1.0):
        self.threshold = threshold
        self.min_speech_duration = min_speech_duration
        self.model = self._load_model()

    def _load_model(self):
        """加载 Silero VAD 预训练模型（从本地 silero-vad 包加载）"""
        try:
            print("[SileroVAD] 正在加载本地模型...")
            model = load_silero_vad(onnx=False)
            print("[SileroVAD] 模型加载成功")
            return model
        except Exception as e:
            print(f"[SileroVAD] 模型加载失败: {e}")
            print("[SileroVAD] 请执行: pip install silero-vad")
            raise

    def detect_speech(self, audio_path: str) -> List[Tuple[float, float]]:
        """
        检测音频中的语音段
        返回: [(start_time, end_time), ...] 列表，单位为秒
        """
        try:
            # 加载音频
            waveform, sample_rate = torchaudio.load(audio_path)

            # 如果采样率不是 16kHz，需要重采样
            if sample_rate != 16000:
                resampler = torchaudio.transforms.Resample(sample_rate, 16000)
                waveform = resampler(waveform)
                sample_rate = 16000

            # 转为单声道并去掉 batch 维度
            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0)
            else:
                waveform = waveform.squeeze(0)

            # 获取语音时间戳
            speech_timestamps = get_speech_timestamps(
                waveform,
                self.model,
                threshold=self.threshold,
                sampling_rate=sample_rate,
                min_speech_duration_ms=int(self.min_speech_duration * 1000),
            )

            # 转为 (start, end) 秒格式
            segments = [
                (ts["start"] / sample_rate, ts["end"] / sample_rate)
                for ts in speech_timestamps
            ]

            return segments

        except Exception as e:
            print(f"[SileroVAD] 处理失败 [{audio_path}]: {e}")
            return []

    def get_voice_activity(self, audio_path: str) -> np.ndarray:
        """
        返回每个音频帧的语音活动标记
        适用于可视化/调试
        """
        segments = self.detect_speech(audio_path)
        if not segments:
            return np.array([])

        waveform, sample_rate = torchaudio.load(audio_path)
        total_frames = waveform.shape[1]
        voice_flags = np.zeros(total_frames, dtype=bool)

        for start, end in segments:
            start_frame = int(start * sample_rate)
            end_frame = int(end * sample_rate)
            voice_flags[start_frame:end_frame] = True

        return voice_flags
