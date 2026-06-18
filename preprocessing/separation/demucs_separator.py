"""
Demucs 人声分离实现
使用 Meta 的 Demucs 模型进行高精度人声分离
"""

import subprocess
import sys
import os
from pathlib import Path
from typing import Optional


class DemucsSeparator:
    """Demucs 人声分离器（备选方案，质量更高但更慢）"""

    def __init__(self, model_name: str = "htdemucs", device: str = "cuda"):
        """
        Args:
            model_name: Demucs 模型名称
                - "htdemucs": 最新混合 Transformer + Demucs 模型 (推荐)
                - "demucs": 原始 Demucs 模型
                - "hdemucs": 高分辨率 Demucs
            device: 运行设备 "cpu" 或 "cuda" (当前使用 GPU)
        """
        self.model_name = model_name
        self.device = device
        self._check_installation()

    def _check_installation(self):
        """检查 demucs 是否已安装"""
        try:
            import demucs  # noqa
        except ImportError:
            print("[Demucs] demucs 未安装")
            print("[Demucs] 安装方式: pip install demucs")

    def separate(self, audio_path: str, output_dir: Optional[str] = None) -> Optional[str]:
        """
        执行人声分离
        Args:
            audio_path: 输入音频路径
            output_dir: 输出目录
        Returns:
            分离后的人声文件路径，失败返回 None
        优化: 只保留人声文件，立即清理无用中间文件
        """
        import gc

        try:
            audio_path = Path(audio_path)
            if not audio_path.exists():
                print(f"[Demucs] 输入文件不存在: {audio_path}")
                return None

            # 检查文件大小，过大则跳过
            file_size_mb = audio_path.stat().st_size / (1024 * 1024)
            if file_size_mb > 100:
                print(f"[Demucs] 文件太大 ({file_size_mb:.0f}MB)，跳过分离")
                return None

            output_base = Path(output_dir) if output_dir else audio_path.parent / "demucs_output"

            cmd = [
                sys.executable, "-m", "demucs",
                "--two-stems", "vocals",         # 只分离人声+伴奏
                "-n", self.model_name,
                "-o", str(output_base),
                "--device", self.device,
                "--overlap", "0.1",              # 减少overlap加速处理
                str(audio_path),
            ]
            subprocess.run(cmd, check=True, timeout=600, env={
                **os.environ,
                "TQDM_DISABLE": "1",  # 禁用 tqdm 进度条，避免终端乱码
            })

            # demucs 输出路径: output_base/model_name/audio_filename/vocals.wav
            out_dir = output_base / self.model_name / audio_path.stem
            vocal_path = out_dir / "vocals.wav"
            if vocal_path.exists():
                # 清理无用中间文件（no_vocals.wav等），只保留人声
                for f in out_dir.iterdir():
                    if f.name != "vocals.wav":
                        try:
                            f.unlink()
                        except OSError:
                            pass
                gc.collect()  # 提示回收内存
                return str(vocal_path)
            else:
                print(f"[Demucs] 未找到人声文件: {vocal_path}")
                return None

        except subprocess.TimeoutExpired:
            print(f"[Demucs] 处理超时: {audio_path}")
            return None
        except Exception as e:
            print(f"[Demucs] 分离失败: {e}")
            return None

    def separate_batch(self, audio_dir: str, pattern: str = "*.wav") -> dict:
        """批量分离目录下的所有音频文件"""
        result = {}
        for audio_file in Path(audio_dir).glob(pattern):
            vocal_path = self.separate(str(audio_file))
            result[str(audio_file)] = vocal_path
        return result
