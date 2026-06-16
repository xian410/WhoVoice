"""
WebRTC VAD 语音端点检测实现
使用 webrtcvad 库进行快速语音检测
"""

import webrtcvad
import wave
import numpy as np
from pathlib import Path
from typing import List, Tuple


class WebRTCVAD:
    """WebRTC VAD 端点检测器（轻量快速方案）"""

    def __init__(self, mode: int = 3, sample_rate: int = 16000):
        """
        Args:
            mode: VAD 激进程度 (0-3), 3 最激进（去静音最干净）
            sample_rate: 音频采样率 (仅支持 8000, 16000, 32000, 48000)
        """
        self.mode = mode
        self.sample_rate = sample_rate
        self.vad = webrtcvad.Vad(mode)
        self.frame_duration_ms = 30  # 每帧时长 (ms)
        self.frame_size = int(sample_rate * self.frame_duration_ms / 1000)  # 每帧采样点数

    def detect_speech(self, audio_path: str) -> List[Tuple[float, float]]:
        """
        检测音频中的语音段
        返回: [(start_time, end_time), ...] 列表，单位为秒
        """
        segments = []
        try:
            with wave.open(audio_path, "rb") as wf:
                frames = wf.getnframes()
                audio_bytes = wf.readframes(frames)

            # 按帧检测
            num_frames = len(audio_bytes) // (self.frame_size * 2)  # 16-bit = 2 bytes
            speech_frames = []

            for i in range(num_frames):
                start = i * self.frame_size * 2
                end = start + self.frame_size * 2
                frame = audio_bytes[start:end]

                if len(frame) < self.frame_size * 2:
                    break

                is_speech = self.vad.is_speech(frame, self.sample_rate)
                speech_frames.append(is_speech)

            # 合并连续语音帧为段落
            in_speech = False
            speech_start = 0

            for i, is_speech in enumerate(speech_frames):
                if is_speech and not in_speech:
                    speech_start = i * self.frame_duration_ms / 1000.0
                    in_speech = True
                elif not is_speech and in_speech:
                    speech_end = i * self.frame_duration_ms / 1000.0
                    if speech_end - speech_start >= 1.0:  # 过滤小于1秒的片段
                        segments.append((speech_start, speech_end))
                    in_speech = False

            # 处理末尾语音段
            if in_speech:
                speech_end = len(speech_frames) * self.frame_duration_ms / 1000.0
                if speech_end - speech_start >= 1.0:
                    segments.append((speech_start, speech_end))

        except Exception as e:
            print(f"[WebRTCVAD] 处理失败 [{audio_path}]: {e}")

        return segments

    def get_voice_activity(self, audio_path: str) -> np.ndarray:
        """返回每个 VAD 帧的语音活动标记"""
        segments = self.detect_speech(audio_path)
        if not segments:
            return np.array([])

        # 先获取音频总时长
        with wave.open(audio_path, "rb") as wf:
            total_frames = wf.getnframes()
            total_duration = total_frames / self.sample_rate

        total_vad_frames = int(total_duration / (self.frame_duration_ms / 1000))
        voice_flags = np.zeros(total_vad_frames, dtype=bool)

        for start, end in segments:
            start_frame = int(start / (self.frame_duration_ms / 1000))
            end_frame = int(end / (self.frame_duration_ms / 1000))
            voice_flags[start_frame:end_frame] = True

        return voice_flags
