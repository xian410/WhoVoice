"""
模型加载和推理接口
使用 FunASR (ModelScope CAM++) 提取声纹 embedding
替代 mvector（模型下载链接已失效）
"""

import os
import numpy as np
from pathlib import Path
from typing import List, Optional, Tuple


def _find_project_root() -> Path:
    current = Path(__file__).resolve().parent
    for parent in [current, *current.parents]:
        if (parent / "voice_recognition").is_dir() and (parent / "vector_database").is_dir():
            return parent
    return Path.cwd()


PROJECT_ROOT = _find_project_root()

FUNASR_MODEL_DIR = PROJECT_ROOT / "models" / "campplus_modelscope"


class VoiceprintRecognizer:

    MODEL_SCOPE_NAMES = {
        "cam++": "damo/speech_campplus_sv_zh-cn_16k-common",
    }

    @staticmethod
    def _cuda_available() -> bool:
        try:
            import torch
            return torch.cuda.is_available()
        except Exception:
            return False

    @staticmethod
    def resolve_device(use_gpu=None) -> bool:
        if use_gpu is True:
            ok = VoiceprintRecognizer._cuda_available()
            print(f"[VoiceprintRecognizer] 推理设备: {'GPU' if ok else 'CPU(回退)'}")
            return ok
        elif use_gpu is False:
            print(f"[VoiceprintRecognizer] 推理设备: CPU")
            return False
        else:
            cuda = VoiceprintRecognizer._cuda_available()
            print(f"[VoiceprintRecognizer] 推理设备: {'GPU' if cuda else 'CPU'}")
            return cuda

    def __init__(self, model_path=None, model_type="cam++", use_gpu=None):
        self.model_type = model_type
        self.use_gpu = self.resolve_device(use_gpu)
        self.model = None
        self._load_model()

    def _load_model(self):
        try:
            from funasr import AutoModel
            model_name = self.MODEL_SCOPE_NAMES.get(self.model_type, "damo/speech_campplus_sv_zh-cn_16k-common")
            device = "cuda" if self.use_gpu else "cpu"
            print(f"[VoiceprintRecognizer] 加载 FunASR 模型: {model_name}")
            cache = FUNASR_MODEL_DIR if FUNASR_MODEL_DIR.is_dir() else None
            self.model = AutoModel(
                model=model_name,
                model_revision="master",
                cache_dir=str(cache) if cache else None,
                disable_update=True,
                device=device,
            )
            print(f"[VoiceprintRecognizer] FunASR 模型加载成功")
        except ImportError:
            print("[VoiceprintRecognizer] 请安装 funasr: pip install funasr")
            raise
        except Exception as e:
            print(f"[VoiceprintRecognizer] 模型加载失败: {e}")
            raise

    def extract_embedding(self, audio_path: str) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("模型未加载")
        try:
            result = self.model.generate(input=audio_path)
            embedding = result[0]["spk_embedding"].cpu().numpy().flatten()
            return np.array(embedding, dtype=np.float32)
        except Exception as e:
            print(f"[VoiceprintRecognizer] 特征提取失败 [{audio_path}]: {e}")
            raise

    def extract_embeddings_batch(self, audio_paths):
        return np.array([self.extract_embedding(p) for p in audio_paths])

    def compare(self, a, b):
        return float(self._cosine_similarity(self.extract_embedding(a), self.extract_embedding(b)))

    @staticmethod
    def _cosine_similarity(e1, e2):
        e1 = e1 / np.linalg.norm(e1)
        e2 = e2 / np.linalg.norm(e2)
        return float(np.dot(e1, e2))
