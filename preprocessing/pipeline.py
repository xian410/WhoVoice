"""
预处理全流程流水线

执行顺序:
    原始音频 -> 人声分离 -> VAD端点检测(纯净人声) -> 音频标准化 -> VAD智能切片 -> 数据集清单
"""

import logging
import shutil
from pathlib import Path
from typing import Optional

from preprocessing.config import RAW_DATA_DIR, PROCESSED_DATA_DIR
from preprocessing.vad.silero_vad import SileroVAD
from preprocessing.vad.webrtc_vad import WebRTCVAD
from preprocessing.separation.spleeter_separator import SpleeterSeparator
from preprocessing.separation.demucs_separator import DemucsSeparator
from preprocessing.standardization import AudioStandardizer
from preprocessing.slicer import AudioSlicer
from preprocessing.dataset_builder import DatasetBuilder

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
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
            self.separator = DemucsSeparator()

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
        """
        input_path = Path(input_path)
        if not input_path.exists():
            logger.error(f"文件不存在: {input_path}")
            return []

        logger.info(f"处理文件: {input_path.name}")

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
            return []
        logger.info(f"  检测到 {len(speech_segments)} 个语音段")

        # Step 3: 音频标准化（放到临时目录，避免污染原始数据）
        logger.info("  步骤3: 音频标准化...")
        temp_dir = Path(output_dir or f"{PROCESSED_DATA_DIR}/{celebrity}") / "tmp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        standardized_path = str(temp_dir / f"{Path(vocal_path).stem}_standardized.wav")
        standardized_path = self.standardizer.process(vocal_path, standardized_path)

        # Step 4: 基于 VAD 的智能切片 - 只保留有语音活动的片段
        logger.info("  步骤4: VAD 智能切片...")
        output_base = Path(output_dir or f"{PROCESSED_DATA_DIR}/{celebrity}")
        output_base.mkdir(parents=True, exist_ok=True)
        slice_paths = self.slicer.slice_vocal(standardized_path, speech_segments, str(output_base))
        logger.info(f"  生成 {len(slice_paths)} 个切片")

        # Step 5: 清理标准化中间文件
        if slice_paths:
            try:
                shutil.rmtree(str(temp_dir))
                logger.info(f"  清理临时文件: {temp_dir}")
            except Exception as e:
                logger.warning(f"  临时文件清理失败: {e}")

        return slice_paths

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

            audio_files = list(celeb_dir.rglob("*.wav")) + list(celeb_dir.rglob("*.mp3"))
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
