"""
音频切片模块
将标准化后的音频按指定时长切割为短片段
"""

import logging
import os

# 修复 librosa/joblib 缓存问题
os.environ.setdefault("LIBROSA_CACHE_DIR", "/tmp/librosa_cache")
os.environ.setdefault("JOBLIB_CACHE_DIR", "/tmp/joblib_cache")

# 禁用 joblib 缓存（修复 macOS 上 librosa 的 '__o_fold' 缓存错误）
import joblib
joblib.memory.Memory.cache = lambda self, func=None, **kwargs: func if func else (lambda f: f)

import librosa
import soundfile as sf
import numpy as np
from pathlib import Path
from typing import List, Optional


class AudioSlicer:
    """音频切片器"""

    def __init__(self, min_duration: float = 5.0, max_duration: float = 10.0):
        """
        Args:
            min_duration: 最小切片时长（秒）
            max_duration: 最大切片时长（秒）
        """
        self.min_duration = min_duration
        self.max_duration = max_duration

    def slice_audio(self, audio_path: str, output_dir: str, overlap: float = 0.0) -> List[str]:
        """
        将音频文件切割为多个短片段

        Args:
            audio_path: 输入音频路径
            output_dir: 输出目录
            overlap: 切片之间的重叠时长（秒）

        Returns:
            切片文件路径列表
        """
        audio_path = Path(audio_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 加载音频
        waveform, sr = librosa.load(audio_path, sr=None, mono=True)

        total_duration = len(waveform) / sr
        if total_duration < self.min_duration:
            # 音频太短，直接复制
            output_path = output_dir / f"{audio_path.stem}_000.wav"
            sf.write(str(output_path), waveform, sr)
            return [str(output_path)]

        # 计算切片参数
        frame_length = int(self.max_duration * sr)
        hop_length = int(frame_length - overlap * sr)

        if hop_length <= 0:
            hop_length = frame_length  # 无重叠

        slice_paths = []
        num_slices = 0

        for start_sample in range(0, len(waveform), hop_length):
            end_sample = start_sample + frame_length

            # 取实际切片
            segment = waveform[start_sample:end_sample]
            segment_duration = len(segment) / sr

            # 丢弃过短的末尾切片
            if segment_duration < self.min_duration:
                continue

            # 如果末尾不足 max_duration，检查是否值得保留
            if segment_duration < self.max_duration:
                # 只在超过 min_duration 时保留
                if segment_duration < self.min_duration:
                    continue

            output_path = output_dir / f"{audio_path.stem}_{num_slices:04d}.wav"
            sf.write(str(output_path), segment, sr)
            slice_paths.append(str(output_path))
            num_slices += 1

        return slice_paths

    def slice_with_vad(self, audio_path: str, speech_segments: List[tuple], output_dir: str) -> List[str]:
        """
        基于 VAD 检测结果进行智能切片
        在每个语音段内按规则切割

        Args:
            audio_path: 输入音频路径
            speech_segments: [(start, end), ...] 语音段列表（秒）
            output_dir: 输出目录

        Returns:
            切片文件路径列表
        """
        waveform, sr = librosa.load(audio_path, sr=None, mono=True)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        slice_paths = []
        num_slices = 0

        for start_time, end_time in speech_segments:
            start_sample = int(start_time * sr)
            end_sample = int(end_time * sr)
            segment = waveform[start_sample:end_sample]
            duration = len(segment) / sr

            if duration < self.min_duration:
                # 语音段太短，尝试与相邻段合并
                if slice_paths and duration > 0.5:
                    # 追加到上一个切片
                    prev_path = Path(slice_paths[-1])
                    prev_wav, _ = librosa.load(str(prev_path), sr=sr, mono=True)
                    merged = np.concatenate([prev_wav, segment])
                    sf.write(str(prev_path), merged, sr)
                continue

            if duration <= self.max_duration:
                # 语音段不超过最大时长，直接保存
                output_path = output_dir / f"vad_slice_{num_slices:04d}.wav"
                sf.write(str(output_path), segment, sr)
                slice_paths.append(str(output_path))
                num_slices += 1
            else:
                # 超长语音段（> max_duration），均匀切割
                num_chunks = int(np.ceil(duration / self.max_duration))
                chunk_duration = duration / num_chunks
                for i in range(num_chunks):
                    chunk_start = int(i * chunk_duration * sr)
                    chunk_end = int((i + 1) * chunk_duration * sr)
                    chunk = segment[chunk_start:chunk_end]
                    output_path = output_dir / f"vad_slice_{num_slices:04d}.wav"
                    sf.write(str(output_path), chunk, sr)
                    slice_paths.append(str(output_path))
                    num_slices += 1

        return slice_paths

    def slice_vocal(self, audio_path: str, speech_segments: List[tuple], output_dir: str,
                    min_voice_ratio: float = 0.3) -> List[str]:
        """
        基于 VAD 的纯净人声切片（slice_with_vad 的增强版）
        - 只保留 VAD 检测到的有效语音段
        - 太短的片段自动合并
        - 过长片段均匀切割

        Args:
            audio_path: 纯净人声音频路径
            speech_segments: [(start, end), ...] VAD 语音段列表（秒）
            output_dir: 输出目录
            min_voice_ratio: 切片中有声占比低于此值则丢弃

        Returns:
            切片文件路径列表
        """
        waveform, sr = librosa.load(audio_path, sr=None, mono=True)
        total_duration = len(waveform) / sr
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if not speech_segments:
            return []

        # 合并密集的 VAD 段：间距小于 1.5 秒的合并
        merged_segments = [list(speech_segments[0])]
        for start, end in speech_segments[1:]:
            prev_end = merged_segments[-1][1]
            gap = start - prev_end
            if gap < 1.5:  # 间距 < 1.5s 合并
                merged_segments[-1][1] = end
            else:
                merged_segments.append([start, end])
        merged_segments = [(s, e) for s, e in merged_segments]

        # 过滤：丢弃太短的语音段 (< min_duration)
        filtered_segments = [(s, e) for s, e in merged_segments
                             if (e - s) >= self.min_duration]

        if not filtered_segments:
            return []

        slice_paths = []
        num_slices = 0
        audio_name = Path(audio_path).stem

        for start_time, end_time in filtered_segments:
            seg_duration = end_time - start_time

            if seg_duration <= self.max_duration:
                # 直接保存该语音段为一个切片
                start_sample = int(start_time * sr)
                end_sample = int(end_time * sr)
                segment = waveform[start_sample:end_sample]
                output_path = output_dir / f"{audio_name}_{num_slices:04d}.wav"
                sf.write(str(output_path), segment, sr)
                slice_paths.append(str(output_path))
                num_slices += 1
            else:
                # 超长语音段，均匀切割为多个切片
                num_chunks = int(np.ceil(seg_duration / self.max_duration))
                chunk_duration = seg_duration / num_chunks
                base_sample = int(start_time * sr)
                for i in range(num_chunks):
                    chunk_start = base_sample + int(i * chunk_duration * sr)
                    chunk_end = base_sample + int((i + 1) * chunk_duration * sr)
                    chunk = waveform[chunk_start:chunk_end]
                    output_path = output_dir / f"{audio_name}_{num_slices:04d}.wav"
                    sf.write(str(output_path), chunk, sr)
                    slice_paths.append(str(output_path))
                    num_slices += 1

        logger = logging.getLogger(__name__)
        covered_duration = sum(e - s for s, e in filtered_segments)
        logger.info(f"  VAD 语音段: {len(filtered_segments)} 段 "
                    f"(有效时长 {covered_duration:.1f}s / 总时长 {total_duration:.1f}s, "
                    f"有声占比 {covered_duration/total_duration:.1%})")
        logger.info(f"  VAD 切片: {len(slice_paths)} 个")

        return slice_paths
