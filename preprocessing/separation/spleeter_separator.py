"""
Spleeter 人声分离实现
使用 Deezer 的 Spleeter 模型将人声与背景音乐分离
"""

import os
import subprocess
from pathlib import Path
from typing import Optional


class SpleeterSeparator:
    """Spleeter 人声分离器"""

    def __init__(self, model_name: str = "spleeter:2stems"):
        """
        Args:
            model_name: Spleeter 模型名称
                - "spleeter:2stems": 人声 + 伴奏 (推荐)
                - "spleeter:4stems": 人声 + 鼓 + 贝斯 + 其他
                - "spleeter:5stems": 人声 + 鼓 + 贝斯 + 钢琴 + 其他
        """
        self.model_name = model_name
        self._check_installation()

    def _check_installation(self):
        """检查 Spleeter 是否已安装"""
        try:
            import spleeter  # noqa
        except ImportError:
            print("[Spleeter] spleeter 未安装，请执行: pip install spleeter")
            print("[Spleeter] 或使用 demucs 作为替代方案")

    def separate(self, audio_path: str, output_dir: Optional[str] = None) -> Optional[str]:
        """
        执行人声分离
        Args:
            audio_path: 输入音频路径
            output_dir: 输出目录，默认为 audio_path 所在目录的 separation_output/
        Returns:
            分离后的人声文件路径，失败返回 None
        """
        try:
            audio_path = Path(audio_path)
            if not audio_path.exists():
                print(f"[Spleeter] 输入文件不存在: {audio_path}")
                return None

            output_base = Path(output_dir) if output_dir else audio_path.parent / "separation_output"

            # 调用 spleeter 命令行
            cmd = [
                "spleeter", "separate",
                "-i", str(audio_path),
                "-o", str(output_base),
                "-p", self.model_name,
            ]
            subprocess.run(cmd, check=True, timeout=300)

            # spleeter 输出路径: output_base/audio_filename/vocals.wav
            vocal_path = output_base / audio_path.stem / "vocals.wav"
            if vocal_path.exists():
                return str(vocal_path)
            else:
                print(f"[Spleeter] 未找到人声文件: {vocal_path}")
                return None

        except subprocess.TimeoutExpired:
            print(f"[Spleeter] 处理超时: {audio_path}")
            return None
        except Exception as e:
            print(f"[Spleeter] 分离失败: {e}")
            return None

    def separate_batch(self, audio_dir: str, pattern: str = "*.wav") -> dict:
        """批量分离目录下的所有音频文件"""
        result = {}
        for audio_file in Path(audio_dir).glob(pattern):
            vocal_path = self.separate(str(audio_file))
            result[str(audio_file)] = vocal_path
        return result
