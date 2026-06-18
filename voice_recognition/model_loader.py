"""
模型加载和推理接口
封装 mvector 库的 MVectorPredictor，提供统一的声纹特征提取和识别接口
使用预训练模型（CAM++ / ECAPA-TDNN）直接提取声纹 embedding，无需训练
"""

import os
import numpy as np
from pathlib import Path
from typing import List, Optional, Tuple


# 自动定位项目根目录（从任意子目录运行都可）
def _find_project_root() -> Path:
    """从当前文件向上查找项目根目录"""
    current = Path(__file__).resolve().parent
    for parent in [current, *current.parents]:
        if (parent / "voice_recognition").is_dir() and (parent / "vector_database").is_dir():
            return parent
    return Path.cwd()


PROJECT_ROOT = _find_project_root()

# 默认模型路径映射（相对于项目根目录）
DEFAULT_MODEL_PATHS = {
    "cam++": str(PROJECT_ROOT / "models/CAMPPlus_Fbank/best_model/model.pth"),
    "ecapa_tdnn": str(PROJECT_ROOT / "models/EcapaTdnn_Fbank/best_model/model.pth"),
    "eres2net": str(PROJECT_ROOT / "models/ERes2Net_Fbank/best_model/model.pth"),
}

# 对应 mvector/configs/ 中的配置名
MODEL_CONFIGS = {
    "cam++": "cam++",
    "ecapa_tdnn": "ecapa_tdnn",
    "eres2net": "eres2net",
}


class VoiceprintRecognizer:
    """
    声纹识别器
    使用 mvector 的 MVectorPredictor + 预训练模型，直接提取声纹特征

    使用示例:
        recognizer = VoiceprintRecognizer(model_type="cam++")
        embedding = recognizer.extract_embedding("audio.wav")
        similarity = recognizer.compare("audio1.wav", "audio2.wav")
    """

    def __init__(self, model_path: Optional[str] = None, model_type: str = "cam++", use_gpu: bool = False):
        """
        Args:
            model_path: 预训练模型 .pth 路径，None 则使用默认路径
            model_type: 模型类型，可选 cam++, ecapa_tdnn, eres2net
            use_gpu: 是否使用 GPU 推理
        """
        self.model_type = model_type
        self.use_gpu = use_gpu

        if model_path is None:
            model_path = DEFAULT_MODEL_PATHS.get(model_type)
            if model_path is None:
                raise ValueError(f"不支持的模型类型: {model_type}，可选: {list(DEFAULT_MODEL_PATHS.keys())}")

        self.model_path = model_path
        self.predictor = None
        self._load_model()

    def _load_model(self):
        """加载 mvector MVectorPredictor + 预训练权重"""
        try:
            from mvector.predict import MVectorPredictor

            config_name = MODEL_CONFIGS.get(self.model_type, "cam++")

            print(f"[VoiceprintRecognizer] 加载预训练模型: {self.model_type}")
            print(f"  Config: {config_name}")
            print(f"  Model:  {self.model_path}")
            print(f"  Device: {'GPU' if self.use_gpu else 'CPU'}")

            self.predictor = MVectorPredictor(
                configs=config_name,
                model_path=self.model_path,
                use_gpu=self.use_gpu,
                log_level="warning",
            )
            print(f"[VoiceprintRecognizer] 模型加载成功")

        except ImportError:
            print("[VoiceprintRecognizer] mvector 未安装，请执行:")
            print("  pip install mvector -i https://pypi.tuna.tsinghua.edu.cn/simple")
            raise
        except FileNotFoundError:
            print(f"[VoiceprintRecognizer] 模型文件未找到: {self.model_path}")
            print("请先执行: python scripts/download_pretrained_model.py")
            raise
        except Exception as e:
            print(f"[VoiceprintRecognizer] 模型加载失败: {e}")
            raise

    def extract_embedding(self, audio_path: str) -> np.ndarray:
        """
        提取声纹特征向量 (embedding)
        Args:
            audio_path: 音频文件路径（支持 .wav, .mp3）
        Returns:
            固定维度的声纹向量 (CAM++ 输出 192 维)
        """
        if self.predictor is None:
            raise RuntimeError("模型未加载")

        try:
            embedding = self.predictor.predict(audio_path)
            return np.array(embedding, dtype=np.float32)
        except Exception as e:
            print(f"[VoiceprintRecognizer] 特征提取失败 [{audio_path}]: {e}")
            raise

    def extract_embeddings_batch(self, audio_paths: List[str]) -> np.ndarray:
        """
        批量提取声纹特征
        Args:
            audio_paths: 音频文件路径列表
        Returns:
            声纹向量矩阵 (N, D)，N=音频数，D=192
        """
        embeddings = []
        for path in audio_paths:
            emb = self.extract_embedding(path)
            embeddings.append(emb)
        return np.array(embeddings)

    def compare(self, audio_path1: str, audio_path2: str) -> float:
        """
        比较两段音频的声纹相似度
        Returns:
            相似度 (0~1)，越高越相似
        """
        emb1 = self.extract_embedding(audio_path1)
        emb2 = self.extract_embedding(audio_path2)
        return float(self._cosine_similarity(emb1, emb2))

    def search(self, audio_path: str, gallery_embeddings: np.ndarray, top_k: int = 5) -> List[Tuple[int, float]]:
        """
        在声纹库中搜索最相似的说话人
        Args:
            audio_path: 查询音频路径
            gallery_embeddings: 声纹库矩阵 (N, D)
            top_k: 返回 Top-K 结果
        Returns:
            [(索引, 相似度), ...]
        """
        query_emb = self.extract_embedding(audio_path)
        similarities = self._batch_cosine_similarity(query_emb, gallery_embeddings)
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        return [(int(idx), float(similarities[idx])) for idx in top_indices]

    @staticmethod
    def _cosine_similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
        emb1 = emb1 / np.linalg.norm(emb1)
        emb2 = emb2 / np.linalg.norm(emb2)
        return float(np.dot(emb1, emb2))

    @staticmethod
    def _batch_cosine_similarity(query: np.ndarray, gallery: np.ndarray) -> np.ndarray:
        query = query / np.linalg.norm(query)
        gallery = gallery / np.linalg.norm(gallery, axis=1, keepdims=True)
        return np.dot(gallery, query)
