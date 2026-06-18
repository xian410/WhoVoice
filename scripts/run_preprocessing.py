#!/usr/bin/env python3
"""
预处理启动脚本
用法:
    python scripts/run_preprocessing.py                        # 处理所有明星
    python scripts/run_preprocessing.py --celebrities 周杰伦    # 指定明星
    python scripts/run_preprocessing.py --single audio.wav 周杰伦  # 单个文件
"""

import os
import sys

# 修复 Windows 终端编码
if os.name == "nt":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    os.system("chcp 65001 > nul 2>&1")

import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from preprocessing.pipeline import PreprocessingPipeline


def main():
    parser = argparse.ArgumentParser(description="WhoVoice 预处理启动脚本")
    parser.add_argument(
        "--celebrities", nargs="+",
        help="指定处理的明星列表"
    )
    parser.add_argument(
        "--single", nargs=2, metavar=("AUDIO_PATH", "CELEBRITY"),
        help="处理单个音频文件: --single audio.wav 周杰伦"
    )
    args = parser.parse_args()

    pipeline = PreprocessingPipeline()

    if args.single:
        audio_path, celebrity = args.single
        print(f"处理单个文件: {audio_path} (明星: {celebrity})")
        slices = pipeline.run_single(audio_path, celebrity)
        print(f"生成 {len(slices)} 个切片")
    else:
        pipeline.run(celebrities=args.celebrities)


if __name__ == "__main__":
    main()
