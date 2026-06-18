"""
声纹匹配 API
POST /api/voice-matching/match/  — 上传音频，返回最相似的明星
"""
import os
import sys
import json
import numpy as np
from pathlib import Path
from typing import Optional
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status

# 确保能导入项目模块
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # /WhoVoice/backend/
PROJECT_ROOT = BASE_DIR.parent                             # /WhoVoice/
sys.path.insert(0, str(PROJECT_ROOT))

# macOS OpenMP 冲突修复
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")

from voice_recognition.model_loader import VoiceprintRecognizer
from vector_database.config import FAISS, EMBEDDING_DIM

import faiss


# 预处理的音频样本目录
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
RAW_DIR = PROJECT_ROOT / "data" / "raw"


def _resolve_device_from_env() -> Optional[bool]:
    """
    从环境变量 INFERENCE_DEVICE 解析推理设备

    返回值传给 VoiceprintRecognizer(use_gpu=...):
        True  → 强制 GPU
        False → 强制 CPU
        None  → 自动检测（推荐，有CUDA则GPU否则CPU）

    环境变量:
        INFERENCE_DEVICE=auto  自动检测（默认）
        INFERENCE_DEVICE=gpu   强制 GPU
        INFERENCE_DEVICE=cpu   强制 CPU
    """
    raw = os.environ.get("INFERENCE_DEVICE", "auto").strip().lower()
    mapping = {
        "auto": None,
        "gpu": True,
        "cpu": False,
    }
    result = mapping.get(raw, None)
    label = {None: "自动检测", True: "GPU", False: "CPU"}
    print(f"[VoiceMatch] INFERENCE_DEVICE={raw!r} → {label[result]}")
    return result


def _resolve_faiss_path() -> Path:
    """解析 FAISS 索引的绝对路径"""
    rel_path = FAISS["index_path"]
    path = Path(rel_path)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / rel_path


class VoiceMatchView(APIView):
    """声纹匹配接口"""
    parser_classes = (MultiPartParser, FormParser)

    # 类级别缓存：模型和索引只加载一次
    _recognizer = None
    _index = None
    _metadata = None
    _id_to_name = {}

    def _ensure_loaded(self):
        """懒加载模型和索引"""
        if self.__class__._recognizer is None:
            print("[VoiceMatch] 加载声纹模型...")
            self.__class__._recognizer = VoiceprintRecognizer(use_gpu=_resolve_device_from_env())

        if self.__class__._index is None:
            index_path = _resolve_faiss_path()
            meta_path = index_path.parent / "celebrity_metadata.json"

            if not index_path.exists():
                raise FileNotFoundError(f"FAISS 索引不存在: {index_path}")
            if not meta_path.exists():
                raise FileNotFoundError(f"元数据不存在: {meta_path}")

            self.__class__._index = faiss.read_index(str(index_path))
            with open(meta_path, "r", encoding="utf-8") as f:
                self.__class__._metadata = json.load(f)
            name_to_id = self.__class__._metadata.get("name_to_id", {})
            self.__class__._id_to_name = {v: k for k, v in name_to_id.items()}
            print(f"[VoiceMatch] 索引加载完成: {self.__class__._metadata['celebrities']}")

        return (
            self.__class__._recognizer,
            self.__class__._index,
            self.__class__._metadata,
            self.__class__._id_to_name,
        )

    def post(self, request):
        """处理音频上传并返回匹配结果"""
        try:
            recognizer, index, metadata, id_to_name = self._ensure_loaded()
        except FileNotFoundError as e:
            return Response({"error": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        # 获取上传的音频文件
        audio_file = request.FILES.get("audio")
        if not audio_file:
            print(f"[VoiceMatch] 请求文件: {request.FILES.keys()}")
            print(f"[VoiceMatch] Content-Type: {request.content_type}")
            return Response(
                {"error": f"请上传音频文件。收到字段: {list(request.FILES.keys())}, Content-Type: {request.content_type}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 保存临时文件
        import tempfile
        tmp_dir = Path(tempfile.gettempdir()) / "whovoice_uploads"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / audio_file.name
        with open(tmp_path, "wb") as f:
            for chunk in audio_file.chunks():
                f.write(chunk)

        try:
            # 提取声纹特征
            print(f"[VoiceMatch] 提取特征: {audio_file.name}")
            embedding = recognizer.extract_embedding(str(tmp_path))

            # 归一化 + 搜索
            query = embedding.reshape(1, -1).astype(np.float32)
            norm = np.linalg.norm(query)
            if norm > 0:
                query = query / norm

            top_k = min(int(request.data.get("top_k", 5)), len(metadata["celebrities"]))
            distances, indices = index.search(query, top_k)

            # 构建结果（始终返回 Top-K，不过滤）
            results = []
            for dist, idx in zip(distances[0], indices[0]):
                if idx == -1:
                    break
                name = id_to_name.get(int(idx), "未知")
                score = float(dist)
                results.append({
                    "name": name,
                    "score": round(score, 4),
                    "rank": len(results) + 1,
                    "likely_match": score >= 0.3,  # 相似度 >= 30% 认为是有效匹配
                })

            # 给第一条结果添加说明
            if results:
                top_score = results[0]["score"]
                if top_score >= 0.5:
                    results[0]["note"] = "✅ 声音非常相似！很可能是同一个人"
                elif top_score >= 0.3:
                    results[0]["note"] = "⚠️ 有一定相似度，但需要更多确认"
                elif top_score >= 0.1:
                    results[0]["note"] = "🔶 略微相似，但基本可以认为是不同人"
                else:
                    results[0]["note"] = "❌ 声纹特征差异很大，不是同一个人"
                    results[0]["likely_match"] = False

            return Response({"results": results})

        except Exception as e:
            print(f"[VoiceMatch] 匹配失败: {e}")
            return Response(
                {"error": f"声纹匹配失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        finally:
            # 清理临时文件
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass


class AudioSampleView(APIView):
    """
    获取歌手音频样本，用于前端试听
    GET /api/voice-matching/sample/<str:name>/
    返回一个随机的预处理切片 WAV 文件
    """

    def get(self, request, name):
        # 优先从 processed 目录找（预处理切片，较短）
        proc_dir = PROCESSED_DIR / name
        candidates = []
        if proc_dir.is_dir():
            candidates = list(proc_dir.rglob("*.wav"))

        # 如果没有预处理切片，从 raw 目录找（原始音频）
        if not candidates:
            raw_dir = RAW_DIR / name
            if raw_dir.is_dir():
                candidates = [
                    f for f in raw_dir.rglob("*.wav")
                    if "demucs_output" not in f.parts and "tmp" not in f.parts
                ]

        if not candidates:
            return Response(
                {"error": f"未找到 [{name}] 的音频样本"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # 随机选一个（避免每次返回同一个）
        import random
        sample_path = random.choice(candidates)

        try:
            from django.http import FileResponse, HttpResponseNotFound
            # 读取文件并返回
            with open(sample_path, "rb") as f:
                audio_data = f.read()
            from django.http import HttpResponse
            response = HttpResponse(audio_data, content_type="audio/wav")
            response["Content-Disposition"] = f'inline; filename="{sample_path.name}"'
            # 添加缓存控制（浏览器缓存1小时）
            response["Cache-Control"] = "public, max-age=3600"
            return response
        except Exception as e:
            return Response(
                {"error": f"读取音频文件失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
