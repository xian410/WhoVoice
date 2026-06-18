"""
预处理全流程流水线

执行顺序:
    原始音频 -> 人声分离 -> VAD端点检测(纯净人声) -> 音频标准化 -> VAD智能切片 -> 数据集清单
"""

import os
import sys
import shutil
import logging
from pathlib import Path
from typing import Optional

# 修复 Windows 终端编码
if os.name == "nt":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    os.system("chcp 65001 > nul 2>&1")

from preprocessing.config import RAW_DATA_DIR, PROCESSED_DATA_DIR
from preprocessing.vad.silero_vad import SileroVAD
from preprocessing.vad.webrtc_vad import WebRTCVAD
from preprocessing.separation.spleeter_separator import SpleeterSeparator
from preprocessing.separation.demucs_separator import DemucsSeparator
from preprocessing.standardization import AudioStandardizer
from preprocessing.slicer import AudioSlicer
from preprocessing.dataset_builder import DatasetBuilder

logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class PreprocessingPipeline:
    """预处理流水线"""

    def __init__(self, config: Optional[dict] = None):
        from preprocessing.config import (
            VAD_METHOD, SEPARATION_METHOD,
            TARGET_SAMPLE_RATE, TARGET_CHANNELS, TARGET_BIT_DEPTH,
            SLICE_DURATION_MIN, SLICE_DURATION_MAX,
        )
        self.config = config or {}

        # 初始化 VAD
        vad_method = self.config.get("vad_method", VAD_METHOD)
        if vad_method == "silero":
            self.vad = SileroVAD()
        else:
            self.vad = WebRTCVAD()

        # 初始化人声分离
        sep_method = self.config.get("separation_method", SEPARATION_METHOD)
        if sep_method == "spleeter":
            self.separator = SpleeterSeparator()
        else:
            # 使用 GPU 加速人声分离 (有 CUDA 时自动使用)
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self.separator = DemucsSeparator(device=device)

        # 初始化标准化和切片
        self.standardizer = AudioStandardizer(
            target_sr=self.config.get("target_sr", TARGET_SAMPLE_RATE),
            target_channels=self.config.get("target_channels", TARGET_CHANNELS),
            target_bit_depth=self.config.get("target_bit_depth", TARGET_BIT_DEPTH),
        )
        self.slicer = AudioSlicer(
            min_duration=self.config.get("min_duration", SLICE_DURATION_MIN),
            max_duration=self.config.get("max_duration", SLICE_DURATION_MAX),
        )
        self.dataset_builder = DatasetBuilder()

    def process_file(self, input_path: str, celebrity: str, output_dir: Optional[str] = None) -> list:
        """
        处理单个音频文件
        返回生成的切片文件路径列表
        优化: 提前过滤无效文件，及时清理中间产物
        """
        import gc

        input_path = Path(input_path)
        if not input_path.exists():
            logger.error(f"文件不存在: {input_path}")
            return []

        logger.info(f"处理文件: {input_path.name}")

        # 检查文件大小和时长，跳过无效文件
        file_size_mb = input_path.stat().st_size / (1024 * 1024)
        if file_size_mb < 0.1:
            logger.warning(f"  文件太小 ({file_size_mb:.1f}MB)，跳过")
            return []
        if file_size_mb > 200:
            logger.warning(f"  文件太大 ({file_size_mb:.0f}MB)，跳过")
            return []

        # 获取音频时长，跳过过短/过长的文件
        try:
            info = self.standardizer.get_audio_info(str(input_path))
            duration = info.get("duration", 0)
            if duration < 15:
                logger.warning(f"  音频太短 ({duration:.0f}s < 15s)，跳过")
                return []
            if duration > 600:
                logger.warning(f"  音频太长 ({duration:.0f}s > 600s)，跳过")
                return []
            logger.info(f"  音频信息: {duration:.0f}s, {file_size_mb:.0f}MB")
        except Exception as e:
            logger.warning(f"  获取音频信息失败: {e}，继续处理")

        # Step 1: 人声分离 - 去除伴奏
        logger.info("  步骤1: 人声分离...")
        vocal_path = self.separator.separate(str(input_path))
        if not vocal_path or not Path(vocal_path).exists():
            logger.warning("  人声分离失败，尝试使用原始音频进行 VAD")
            vocal_path = str(input_path)

        # Step 2: VAD 端点检测（在纯净人声上）
        logger.info("  步骤2: VAD 端点检测（纯净人声）...")
        speech_segments = self.vad.detect_speech(vocal_path)
        if not speech_segments:
            logger.warning("  VAD 在纯净人声中未检测到有效语音段，尝试使用原始音频")
            speech_segments = self.vad.detect_speech(str(input_path))
        if not speech_segments:
            logger.warning("  VAD 仍未检测到有效语音段")
            # 清理 demucs 输出
            self._cleanup_demucs_output(vocal_path, input_path)
            return []
        logger.info(f"  检测到 {len(speech_segments)} 个语音段")

        # Step 3: 音频标准化
        logger.info("  步骤3: 音频标准化...")
        temp_dir = Path(output_dir or f"{PROCESSED_DATA_DIR}/{celebrity}") / "tmp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        standardized_path = str(temp_dir / f"{Path(vocal_path).stem}_standardized.wav")
        standardized_path = self.standardizer.process(vocal_path, standardized_path)

        # Step 4: 基于 VAD 的智能切片
        logger.info("  步骤4: VAD 智能切片...")
        output_base = Path(output_dir or f"{PROCESSED_DATA_DIR}/{celebrity}")
        output_base.mkdir(parents=True, exist_ok=True)
        slice_paths = self.slicer.slice_vocal(standardized_path, speech_segments, str(output_base))
        logger.info(f"  生成 {len(slice_paths)} 个切片")

        # Step 5: 清理临时文件 + 清理 demucs 中间输出
        if slice_paths:
            try:
                shutil.rmtree(str(temp_dir))
                logger.info(f"  清理临时文件: {temp_dir}")
            except Exception as e:
                logger.warning(f"  临时文件清理失败: {e}")

        # 清理 demucs 输出目录（vocals.wav 已经拷贝或不再需要）
        self._cleanup_demucs_output(vocal_path, input_path)

        gc.collect()
        return slice_paths

    def _cleanup_demucs_output(self, vocal_path: str, original_path: Path):
        """清理 Demucs 产生的中间输出目录"""
        vocal = Path(vocal_path)
        # demucs 输出在 data/raw/{singer}/bilibili/demucs_output/...
        demucs_dir = vocal.parent.parent.parent if len(vocal.parents) >= 4 else None
        if demucs_dir and "demucs_output" in str(demucs_dir):
            if demucs_dir.exists():
                try:
                    shutil.rmtree(str(demucs_dir))
                    logger.info(f"  清理 Demucs 输出: {demucs_dir}")
                except Exception as e:
                    logger.warning(f"  清理 Demucs 输出失败: {e}")

    def run(self, celebrities: Optional[list] = None):
        """
        批量处理指定明星的所有原始音频
        """
        raw_dir = Path(RAW_DATA_DIR)
        if not raw_dir.exists():
            logger.error(f"原始数据目录不存在: {raw_dir}")
            return

        celeb_dirs = [raw_dir / c for c in celebrities] if celebrities else sorted(raw_dir.iterdir())

        for celeb_dir in celeb_dirs:
            if not celeb_dir.is_dir():
                continue
            celebrity = celeb_dir.name
            logger.info(f"\n===== 开始处理 [{celebrity}] =====")

            audio_files = [
                f for f in (list(celeb_dir.rglob("*.wav")) + list(celeb_dir.rglob("*.mp3")))
                if "demucs_output" not in f.parts and "tmp" not in f.parts
            ]
            logger.info(f"找到 {len(audio_files)} 个音频文件")

            for audio_file in audio_files:
                try:
                    self.process_file(str(audio_file), celebrity)
                except Exception as e:
                    logger.error(f"处理失败 [{audio_file.name}]: {e}")
                    continue

            logger.info(f"[{celebrity}] 处理完成\n")

        # 最后构建数据集清单
        self.dataset_builder.build_manifest()

    def run_single(self, audio_path: str, celebrity: str) -> list:
        """处理单个音频文件（对外接口）"""
        return self.process_file(audio_path, celebrity)


if __name__ == "__main__":
    pipeline = PreprocessingPipeline()
    pipeline.run()
