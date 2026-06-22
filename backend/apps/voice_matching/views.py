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
from voice_recognition.audio_analyzer import analyze_audio, compute_star_mix, build_share_text
from vector_database.config import FAISS, EMBEDDING_DIM

import faiss


# 预处理的音频样本目录
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
RAW_DIR = PROJECT_ROOT / "data" / "raw"


# ── ffmpeg 转码辅助函数 ──
import shutil
_FFMPEG_CANDIDATES = [
    shutil.which("ffmpeg"),       # 系统 PATH
    "/usr/bin/ffmpeg",            # Linux 常见路径
    "/usr/local/bin/ffmpeg",      # 手动编译安装
    "ffmpeg",
    "ffmpeg.exe",
]
# 过滤 None
_FFMPEG_CANDIDATES = [c for c in _FFMPEG_CANDIDATES if c]
_FFMPEG_PATH = None


def _find_ffmpeg() -> str:
    """查找可用的 ffmpeg 路径"""
    global _FFMPEG_PATH
    if _FFMPEG_PATH is not None:
        return _FFMPEG_PATH
    import subprocess
    for candidate in _FFMPEG_CANDIDATES:
        try:
            r = subprocess.run([candidate, "-version"], capture_output=True, timeout=5)
            if r.returncode == 0:
                _FFMPEG_PATH = candidate
                return candidate
        except Exception:
            continue
    _FFMPEG_PATH = ""
    return ""


def _ffmpeg_convert_to_wav(input_path: str, output_path: str) -> bool:
    """用 ffmpeg 将任意音频转为 WAV (16kHz, 单声道, 16bit)"""
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        return False
    import subprocess
    try:
        r = subprocess.run(
            [ffmpeg, "-y", "-i", input_path,
             "-ar", "16000", "-ac", "1", "-sample_fmt", "s16",
             "-f", "wav", output_path],
            capture_output=True, timeout=30,
        )
        return r.returncode == 0 and Path(output_path).exists()
    except Exception:
        return False


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


# ── 服务启动时预加载模型和索引，避免首次请求超时 ──
print("[VoiceMatch] 预加载声纹模型...")
_PRELOAD_RECOGNIZER = VoiceprintRecognizer(use_gpu=_resolve_device_from_env())

# 带伴奏索引 (默认)
_PRELOAD_INDEX_PATH = _resolve_faiss_path()
_PRELOAD_META_PATH = _PRELOAD_INDEX_PATH.parent / "celebrity_metadata.json"
if _PRELOAD_INDEX_PATH.exists() and _PRELOAD_META_PATH.exists():
    _PRELOAD_INDEX = faiss.read_index(str(_PRELOAD_INDEX_PATH))
    with open(_PRELOAD_META_PATH, "r", encoding="utf-8") as _f:
        _PRELOAD_METADATA = json.load(_f)
    print(f"[VoiceMatch] 带伴奏索引: {_PRELOAD_METADATA.get('num_celebrities', 0)} 位明星")
else:
    _PRELOAD_INDEX = None
    _PRELOAD_METADATA = None

# 纯净人声索引 (可选)
_CLEAN_INDEX_PATH = _PRELOAD_INDEX_PATH.parent / "celebrity_clean.index"
_CLEAN_META_PATH = _PRELOAD_INDEX_PATH.parent / "celebrity_clean_metadata.json"
if _CLEAN_INDEX_PATH.exists() and _CLEAN_META_PATH.exists():
    _CLEAN_INDEX = faiss.read_index(str(_CLEAN_INDEX_PATH))
    with open(_CLEAN_META_PATH, "r", encoding="utf-8") as _f:
        _CLEAN_METADATA = json.load(_f)
    print(f"[VoiceMatch] 纯净人声索引: {_CLEAN_METADATA.get('num_celebrities', 0)} 位明星")
else:
    _CLEAN_INDEX = None
    _CLEAN_METADATA = None

print("[VoiceMatch] 索引预加载完成")


class VoiceMatchView(APIView):
    """声纹匹配接口"""
    parser_classes = (MultiPartParser, FormParser)

    # 类级别缓存：模型和索引只加载一次
    _recognizer = None
    _index = None
    _metadata = None
    _current_index_type = "raw"  # "raw" 或 "clean"

    def _ensure_loaded(self, index_type="raw"):
        """懒加载模型和索引，支持 index_type="raw" 或 "clean"""
        if self.__class__._recognizer is None:
            self.__class__._recognizer = _PRELOAD_RECOGNIZER

        # 如果索引类型切换了，重新加载
        if self.__class__._current_index_type != index_type or self.__class__._index is None:
            if index_type == "clean" and _CLEAN_INDEX is not None:
                self.__class__._index = _CLEAN_INDEX
                self.__class__._metadata = _CLEAN_METADATA
                self.__class__._current_index_type = "clean"
                print(f"[VoiceMatch] 切换到纯净人声索引 ({len(_CLEAN_METADATA['celebrities'])} 位)")
            else:
                # 默认使用带伴奏索引
                if _PRELOAD_INDEX is not None:
                    self.__class__._index = _PRELOAD_INDEX
                    self.__class__._metadata = _PRELOAD_METADATA
                    self.__class__._current_index_type = "raw"
                    if index_type == "clean":
                        print("[VoiceMatch] 纯净人声索引不可用，使用带伴奏索引")

        return (
            self.__class__._recognizer,
            self.__class__._index,
            self.__class__._metadata,
        )

    def post(self, request):
        """处理音频上传并返回匹配结果"""
        # 获取索引选择参数
        index_type = request.data.get("index", "clean")
        if index_type not in ("raw", "clean"):
            index_type = "raw"

        try:
            recognizer, index, metadata = self._ensure_loaded(index_type)
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
            distances, indices = index.search(query, top_k * 3)  # 搜索更多结果以过滤无音频的明星

            # 构建结果：只包含有音频可试听的明星，直到凑满 top_k
            celebrities = metadata["celebrities"]
            results = []
            for dist, idx in zip(distances[0], indices[0]):
                if idx == -1 or idx >= len(celebrities):
                    break
                if len(results) >= top_k:
                    break
                name = celebrities[int(idx)]
                score = float(dist)

                # 检查是否有可试听的音频
                has_audio = False
                for audio_root in [PROCESSED_DIR, RAW_DIR]:
                    celeb_dir = audio_root / name
                    if celeb_dir.is_dir():
                        for ext in (".wav", ".mp3", ".m4a"):
                            if list(celeb_dir.rglob(f"*{ext}")):
                                has_audio = True
                                break
                        if has_audio:
                            break

                # 跳过无音频的歌手
                if not has_audio:
                    continue

                results.append({
                    "name": name,
                    "score": round(score, 4),
                    "rank": len(results) + 1,
                    "likely_match": score >= 0.3,
                    "has_audio": has_audio,
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

            # ── 生成声纹海报数据 ──
            poster_data = None
            try:
                # 先用 ffmpeg 转码为 WAV，确保 librosa 兼容
                wav_for_poster = tmp_path.with_suffix(".poster.wav")
                _ = _ffmpeg_convert_to_wav(str(tmp_path), str(wav_for_poster))
                poster_audio = str(wav_for_poster) if _ else str(tmp_path)

                audio_analysis = analyze_audio(poster_audio)
                star_mix = compute_star_mix(results)
                share_text = build_share_text(star_mix, audio_analysis["fun_title"])
                poster_data = {
                    "radar": audio_analysis["radar"],
                    "radar_labels": ["磁性", "甜美", "力量", "清澈", "独特"],
                    "voice_tags": audio_analysis["voice_tags"],
                    "fun_title": audio_analysis["fun_title"],
                    "star_mix": star_mix,
                    "share_text": share_text,
                }
            except Exception as e:
                print(f"[VoiceMatch] 海报数据分析失败 (不影响匹配结果): {e}")
            finally:
                # 清理临时转码文件
                if 'wav_for_poster' in dir() and wav_for_poster.exists():
                    try:
                        wav_for_poster.unlink()
                    except Exception:
                        pass

            response_data = {
                "results": results,
                "total_celebrities": len(metadata["celebrities"]),
                "index_type": self.__class__._current_index_type,
            }
            if poster_data:
                response_data["poster_data"] = poster_data

            return Response(response_data)

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


class FaissIndexDownloadView(APIView):
    """
    下载 FAISS 索引文件
    GET /api/voice-matching/faiss-index/     — 原始 FlatIP 索引（用于声纹匹配）
    GET /api/voice-matching/faiss-index/?viz=1 — IVF_FLAT 索引（用于 Feder 可视化）
    """

    def get(self, request):
        is_viz = request.query_params.get("viz", "") == "1"
        index_path = _resolve_faiss_path()

        if is_viz:
            # 使用 IVF_FLAT 索引（Feder 可视化专用）
            ivf_path = index_path.parent / "celebrity_ivf.index"
            if ivf_path.exists():
                index_path = ivf_path

        if not index_path.exists():
            return Response(
                {"error": f"FAISS 索引不存在: {index_path}"},
                status=status.HTTP_404_NOT_FOUND,
            )

        from django.http import HttpResponse
        with open(index_path, "rb") as f:
            data = f.read()
        response = HttpResponse(data, content_type="application/octet-stream")
        response["Content-Disposition"] = 'attachment; filename="celebrity.index"'
        response["Access-Control-Allow-Origin"] = "*"
        response["Cache-Control"] = "public, max-age=3600"
        return response


class FaissVisualizerView(APIView):
    """
    FAISS 索引可视化页面（使用 Feder.js）
    GET /api/voice-matching/faiss-visualizer/
    返回完整的 HTML 页面
    """

    def get(self, request):
        index_path = _resolve_faiss_path()
        if not index_path.exists():
            return Response(
                {"error": f"FAISS 索引不存在: {index_path}"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # 使用相对路径，避免 localhost vs 127.0.0.1 跨域问题
        # 使用 IVF_FLAT 索引（Feder 可视化需要 IVF 格式）
        index_url = "/api/voice-matching/faiss-index/?viz=1"

        # 加载元数据以获取明星名列表
        meta_path = index_path.parent / "celebrity_metadata.json"
        celeb_names = []
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            celeb_names = meta.get("celebrities", [])

        html = self._build_feder_html(index_url, celeb_names)
        from django.http import HttpResponse
        return HttpResponse(html, content_type="text/html; charset=utf-8")

    def _build_feder_html(self, index_url: str, celeb_names: list) -> str:
        from .feder_template import FEDER_HTML_TEMPLATE
        names_json = json.dumps([n for n in celeb_names], ensure_ascii=False)
        total = len(celeb_names)
        max_id = total - 1
        html = FEDER_HTML_TEMPLATE
        html = html.replace("__TOTAL__", str(total))
        html = html.replace("__MAX_ID__", str(max_id))
        html = html.replace("__NAMES_JSON__", names_json)
        html = html.replace("__INDEX_URL__", index_url)
        return html


class FaissScatterView(APIView):
    """
    散点图方式可视化声纹向量分布
    GET /api/voice-matching/faiss-scatter/
    """

    def get(self, request):
        index_path = _resolve_faiss_path()
        meta_path = index_path.parent / "celebrity_metadata.json"

        if not meta_path.exists():
            return Response({"error": "元数据不存在"}, status=404)

        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        celeb_names = meta.get("celebrities", [])

        # 加载向量并计算 PCA 投影 + 聚类分析
        points, cluster_info = self._compute_pca_projection(index_path, celeb_names)

        from django.http import HttpResponse
        from .scatter_template import SCATTER_HTML_TEMPLATE
        points_json = json.dumps(points, ensure_ascii=False)
        cluster_json = json.dumps(cluster_info, ensure_ascii=False)
        html = SCATTER_HTML_TEMPLATE
        html = html.replace("__TOTAL__", str(len(points)))
        html = html.replace("__POINTS_JSON__", points_json)
        html = html.replace("__CLUSTER_INFO__", cluster_json)
        return HttpResponse(html, content_type="text/html; charset=utf-8")

    def _compute_pca_projection(self, index_path: Path, celeb_names: list) -> tuple:
        import faiss

        if index_path.exists():
            idx = faiss.read_index(str(index_path))
            n = idx.ntotal
            if hasattr(idx, "xb"):
                vectors = faiss.vector_float_to_array(idx.xb).reshape(n, -1)
            else:
                vectors = np.zeros((n, idx.d), dtype=np.float32)
                for i in range(n):
                    idx.reconstruct(i, vectors[i])
        else:
            return [{"name": n, "x": 0, "y": 0} for n in celeb_names], {}

        n_vectors = vectors.shape[0]
        names = celeb_names[:n_vectors]

        # 中心化
        mean = np.mean(vectors, axis=0)
        centered = vectors - mean

        # SVD 求 PCA
        U, S, Vt = np.linalg.svd(centered, full_matrices=False)
        pca_2d = centered @ Vt[:2].T

        # 归一化到 [-1, 1]
        max_abs = np.max(np.abs(pca_2d))
        if max_abs > 0:
            pca_2d = pca_2d / max_abs

        # ── K-means 聚类 ──
        n_clusters = min(10, max(2, n_vectors // 40))
        cluster_labels = np.zeros(n_vectors, dtype=int)
        centroids = None
        if n_vectors >= n_clusters:
            kmeans = faiss.Kmeans(d=vectors.shape[1], k=n_clusters, niter=20, gpu=False)
            kmeans.train(vectors)
            _, cluster_labels = kmeans.index.search(vectors, 1)
            cluster_labels = cluster_labels.flatten()
            centroids = np.array(kmeans.centroids, dtype=np.float32).reshape(n_clusters, -1)

        # ── 分析每个聚类的声学特征，生成名称 ──
        cluster_info = self._analyze_clusters(
            vectors, cluster_labels, centroids, names, n_clusters
        )

        points = []
        for i, name in enumerate(names):
            points.append({
                "name": name,
                "x": round(float(pca_2d[i, 0]), 6),
                "y": round(float(pca_2d[i, 1]), 6),
                "c": int(cluster_labels[i]),
            })

        return points, cluster_info

    def _analyze_clusters(self, vectors, labels, centroids, names, n_clusters):
        """
        分析每个聚类的声学特征并生成描述性名称
        返回: { cluster_id: { "name": "...", "desc": "..." } }
        """
        import librosa

        result = {}
        raw_dir = PROJECT_ROOT / "data" / "raw"

        for cid in range(n_clusters):
            # 找出该聚类的所有成员索引
            member_idx = np.where(labels == cid)[0]
            if len(member_idx) == 0:
                result[cid] = {"name": f"聚类 {cid}", "desc": ""}
                continue

            # 找到距离聚类中心最近的 1 个明星作为代表（减少分析量）
            rep_names = []
            if centroids is not None:
                centroid = centroids[cid]
                dists = np.linalg.norm(vectors[member_idx] - centroid, axis=1)
                nearest = member_idx[np.argsort(dists)[:1]]
                rep_names = [names[i] for i in nearest]
            else:
                rep_names = [names[member_idx[0]]]

            # ── 音频特征分析（每个代表取 8 秒）──
            all_f0 = []
            all_sc = []
            all_rms = []
            audio_loaded = 0

            for rname in rep_names:
                audio_paths = list(raw_dir.glob(f"{rname}/**/*.wav"))
                if not audio_paths:
                    audio_paths = list(raw_dir.glob(f"{rname}/**/*.mp3"))
                if not audio_paths:
                    continue

                try:
                    y, sr = librosa.load(str(audio_paths[0]), sr=16000, duration=8)
                    if len(y) < sr:
                        continue

                    # 用更快的 Yin 法估算音高（替代 pyin）
                    f0 = librosa.yin(y, fmin=librosa.note_to_hz('C2'),
                                     fmax=librosa.note_to_hz('C7'), sr=sr)
                    f0_vals = f0[~np.isnan(f0)]
                    if len(f0_vals) > 0:
                        all_f0.append(np.mean(f0_vals))

                    sc = librosa.feature.spectral_centroid(y=y, sr=sr)
                    all_sc.append(np.mean(sc))

                    rms = librosa.feature.rms(y=y)
                    all_rms.append(np.mean(rms))

                    audio_loaded += 1
                except Exception:
                    continue

            # ── 生成聚类名称 ──
            if audio_loaded == 0:
                # 无音频数据，用已知类别名
                result[cid] = self._guess_cluster_name(
                    cid, rep_names, len(member_idx), n_clusters
                )
            else:
                mean_f0 = np.mean(all_f0) if all_f0 else 0
                mean_sc = np.mean(all_sc) if all_sc else 0
                mean_rms = np.mean(all_rms) if all_rms else 0

                name_parts = []
                desc_parts = []

                # 性别 + 音高 (主标签)
                gender_label = ""
                pitch_label = ""

                if mean_f0 > 210:
                    pitch_label = "高音"
                elif mean_f0 > 185:
                    pitch_label = "偏高"
                elif mean_f0 > 165:
                    pitch_label = "中音"
                elif mean_f0 > 145:
                    pitch_label = "偏低"
                else:
                    pitch_label = "低音"

                if mean_f0 > 195:
                    gender_label = "女声"
                elif mean_f0 < 155:
                    gender_label = "男声"
                else:
                    gender_label = ""

                # 音色 (次标签，增加区分度)
                timbre_label = ""
                if mean_sc > 3200:
                    timbre_label = "清亮"
                elif mean_sc > 2600:
                    timbre_label = "明亮"
                elif mean_sc > 2100:
                    timbre_label = "温暖"
                elif mean_sc > 1600:
                    timbre_label = "厚实"
                else:
                    timbre_label = "浑厚"

                # 力度
                power_label = ""
                if mean_rms > 0.14:
                    power_label = "力量"
                elif mean_rms > 0.10:
                    power_label = "饱满"
                elif mean_rms > 0.06:
                    power_label = "均衡"
                else:
                    power_label = "轻柔"

                # 拼接名称
                main = pitch_label
                if gender_label:
                    main = gender_label + " " + main
                full_name = main + " · " + timbre_label + " · " + power_label

                # 描述信息
                desc_parts.append(f"F0={mean_f0:.0f}Hz")
                desc_parts.append(f"SC={mean_sc:.0f}")
                desc_parts.append(f"RMS={mean_rms:.3f}")
                desc = " | ".join(desc_parts)
                desc += f" | {len(member_idx)}人 | 代表: {rep_names[0]}"

                result[cid] = {"name": full_name, "desc": desc}

        # 去重：同名聚类加编号后缀
        name_counts = {}
        for cid in range(n_clusters):
            name = result[cid]["name"]
            if name not in name_counts:
                name_counts[name] = 0
            name_counts[name] += 1
        name_seen = {}
        for cid in range(n_clusters):
            name = result[cid]["name"]
            name_seen[name] = name_seen.get(name, 0) + 1
            if name_counts[name] > 1:
                result[cid]["name"] = f"{name} #{name_seen[name]}"

        return result

    def _guess_cluster_name(self, cid, rep_names, count, total_clusters):
        """
        无音频数据时的 fallback：用代表明星名推测
        这里返回中性名称
        """
        cluster_labels = [
            "声纹类型 A", "声纹类型 B", "声纹类型 C",
            "声纹类型 D", "声纹类型 E", "声纹类型 F",
            "声纹类型 G", "声纹类型 H", "声纹类型 I",
            "声纹类型 J",
        ]
        name = cluster_labels[cid] if cid < len(cluster_labels) else f"聚类 {cid}"
        desc = f"{count}人"
        if rep_names:
            desc += f" | 代表: {rep_names[0]}"
        return {"name": name, "desc": desc}


class AudioSampleView(APIView):
    """
    获取歌手音频样本，用于前端试听
    GET /api/voice-matching/sample/<str:name>/
    返回 ~15 秒的音频预览（WAV 格式）
    """

    # 音频格式扩展名列表（按优先级排序）
    AUDIO_EXTENSIONS = (".wav", ".mp3", ".m4a")

    @classmethod
    def _find_ffmpeg(cls) -> str:
        """查找可用的 ffmpeg 路径（共享模块级函数）"""
        return _find_ffmpeg()

    @classmethod
    def _find_voice_start(cls, audio_path: str, sample_rate: int = 16000) -> float:
        """
        用 librosa 检测人声起始位置（跳过前奏/间奏）
        返回起始秒数，检测失败时返回 0
        """
        try:
            import librosa
            import numpy as np

            y, sr = librosa.load(audio_path, sr=sample_rate, mono=True, duration=60)

            hop_length = int(sr * 0.025)  # 25ms
            win_length = int(sr * 0.05)   # 50ms
            rms = librosa.feature.rms(y=y, frame_length=win_length, hop_length=hop_length)[0]

            threshold = np.max(rms) * 0.08
            if threshold < 1e-6:
                return 0.0

            start_frame = int(0.5 / 0.025)
            if start_frame >= len(rms):
                return 0.0

            for i in range(start_frame, len(rms)):
                if rms[i] > threshold:
                    onset = max(0, (i * hop_length / sr) - 0.3)
                    return onset

            return 0.0
        except Exception as e:
            print(f"[AudioSample] 人声检测失败: {e}，从头开始")
            return 0.0
    @classmethod
    def _find_chorus_start(cls, audio_path: str, sample_rate: int = 16000) -> float:
        """
        检测副歌（chorus）起始位置
        策略：找能量跃升最显著的位置（而非绝对值最高）
        对慢歌/抒情歌特别优化：避免被小波动误触发
        返回起始秒数，检测失败时回退到 _find_voice_start
        """
        try:
            import librosa
            import numpy as np

            y, sr = librosa.load(audio_path, sr=sample_rate, mono=True, duration=120)

            hop_sec = 0.5
            hop_length = int(sr * hop_sec)
            rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]

            if len(rms) < 24:
                return cls._find_voice_start(audio_path, sample_rate)

            # 3 秒平滑
            window = max(1, int(3.0 / hop_sec))
            kernel = np.ones(window) / window
            energy = np.convolve(rms, kernel, mode="same")

            skip_frames = int(10.0 / hop_sec)
            if skip_frames >= len(energy):
                return cls._find_voice_start(audio_path, sample_rate)

            global_max = np.max(energy)
            if global_max < 1e-6:
                return cls._find_voice_start(audio_path, sample_rate)

            # ── 策略1：找能量跃升最显著的位置 ──
            # 对每个位置计算"未来4秒 / 过去8秒"的能量比值
            # 选比值最大的位置（而非第一个达标的）
            lookahead = int(4.0 / hop_sec)
            baseline_range = int(8.0 / hop_sec)
            gap = max(1, int(2.0 / hop_sec))
            abs_threshold = global_max * 0.08  # 绝对能量门槛（比之前更低，让慢歌也能过）

            best_ratio = 0.0
            best_pos = None

            for i in range(skip_frames + baseline_range + gap, len(energy) - lookahead):
                baseline = np.median(energy[i - baseline_range - gap : i - gap])
                current = np.mean(energy[i : i + lookahead])

                if baseline > 1e-8 and current > abs_threshold:
                    ratio = current / baseline
                    # 小幅波动过滤：当前能量必须明显高于全局平均
                    if ratio > 1.25 and ratio > best_ratio:
                        best_ratio = ratio
                        best_pos = i

            # 如果找到跃升最显著的位置，检查是否合理
            if best_pos is not None and best_ratio >= 1.3:
                start_sec = max(0, best_pos * hop_sec - 1.0)
                print(f"[AudioSample] 检测到副歌起始(最佳跃升): {start_sec:.1f}s (ratio={best_ratio:.2f})")
                return start_sec

            # ── 策略1b：从全局峰值向后回溯（找副歌段） ──
            # 先找全局最大值，然后向后找到能量显著下降的位置
            peak_idx = int(np.argmax(energy[skip_frames:])) + skip_frames
            peak_energy = energy[peak_idx]

            # 从峰值向后走到下降40%的位置
            drop_thresh = peak_energy * 0.60
            chorus_start_idx = peak_idx
            for j in range(peak_idx, skip_frames, -1):
                if energy[j] < drop_thresh:
                    chorus_start_idx = j + 1
                    break

            start_sec = max(0, chorus_start_idx * hop_sec - 1.0)

            # 如果峰值位置>50s，且前方还有另一个显著峰值，优先选前面的（第二段副歌可能更高但第一段更好）
            if start_sec > 50:
                # 在前半段找另一个峰值
                mid = max(skip_frames, peak_idx - int(30.0 / hop_sec))  # 30秒前
                if mid > skip_frames:
                    second_peak = int(np.argmax(energy[skip_frames:mid])) + skip_frames
                    second_val = energy[second_peak]
                    if second_val > peak_energy * 0.70:
                        # 前面的峰值也够高，优先用它
                        for j in range(second_peak, skip_frames, -1):
                            if energy[j] < second_val * 0.60:
                                chorus_start_idx = j + 1
                                break
                        start_sec = max(0, chorus_start_idx * hop_sec - 1.0)
                        print(f"[AudioSample] 检测到副歌起始(全局峰值-前段): {start_sec:.1f}s")
                        return start_sec

            print(f"[AudioSample] 检测到副歌起始(全局峰值): {start_sec:.1f}s")

            # ── 策略1c：如果结果<20s（太早），尝试找"低谷后跃升" ──
            # 适合整首歌一直很响、无明显verse/chorus区分的歌
            if start_sec < 20:
                # 检查前30秒是否都保持高能（无intro/verse低谷）
                early_win = energy[skip_frames : skip_frames + int(30.0 / hop_sec)]
                if len(early_win) > 0 and np.min(early_win) > global_max * 0.25:
                    # 歌曲从头响到尾，跳到35-40s区域（通常覆盖第二段副歌）
                    start_sec = 37.0
                    print(f"[AudioSample] 检测到副歌起始(高能跳转): {start_sec:.1f}s")
                    return start_sec

                # 否则尝试找能量低谷后的上升沿
                valley_thresh = global_max * 0.35
                look_end = min(len(energy), int(60.0 / hop_sec))
                for i in range(skip_frames + int(5.0 / hop_sec), look_end):
                    if energy[i] < valley_thresh:
                        # 找到低谷，往后找第一个上升沿
                        for k in range(i, min(len(energy) - lookahead, look_end)):
                            after = np.mean(energy[k : k + lookahead])
                            if after > valley_thresh * 1.3:
                                start_sec = max(0, k * hop_sec - 1.0)
                                print(f"[AudioSample] 检测到副歌起始(低谷跃升): {start_sec:.1f}s")
                                return start_sec
                        break

            return start_sec

        except Exception as e:
            print(f"[AudioSample] 副歌检测失败: {e}，回退到简单人声检测")
            return cls._find_voice_start(audio_path, sample_rate)

    @classmethod
    def _trim_audio(cls, input_path: str) -> tuple:
        """
        用 ffmpeg 截取 15 秒人声片段，返回 (wav_bytes, content_type)
        先检测人声起始位置，跳过前奏
        """
        import subprocess

        ffmpeg = cls._find_ffmpeg()
        if not ffmpeg:
            with open(input_path, "rb") as f:
                return f.read(), cls._guess_content_type(input_path)

        # 检测副歌起始位置（跳过前奏和主歌，直接到副歌）
        chorus_start = cls._find_chorus_start(input_path)
        if chorus_start > 0:
            print(f"[AudioSample] 最终截取起始: {chorus_start:.1f}s")
        else:
            # 副歌检测失败，回退到简单人声检测
            chorus_start = cls._find_voice_start(input_path)
            if chorus_start > 0:
                print(f"[AudioSample] 回退到人声起始: {chorus_start:.1f}s")

        try:
            r = subprocess.run(
                [ffmpeg, "-i", input_path, "-ss", str(chorus_start), "-t", "15", "-f", "wav", "-"],
                capture_output=True, timeout=30,
            )
            if r.returncode == 0 and len(r.stdout) > 100:
                return r.stdout, "audio/wav"
            # ffmpeg 失败时回退原始文件
            with open(input_path, "rb") as f:
                return f.read(), cls._guess_content_type(input_path)
        except Exception as e:
            print(f"[AudioSample] ffmpeg 截取失败: {e}，回退原始文件")
            with open(input_path, "rb") as f:
                return f.read(), cls._guess_content_type(input_path)

    @staticmethod
    def _guess_content_type(path: Path) -> str:
        """根据文件扩展名返回 MIME 类型"""
        ext = path.suffix.lower()
        return {
            ".wav": "audio/wav",
            ".mp3": "audio/mpeg",
            ".m4a": "audio/mp4",
        }.get(ext, "audio/wav")

    def get(self, request, name):
        # 优先从 processed 目录找（预处理切片，较短）
        proc_dir = PROCESSED_DIR / name
        candidates = []
        if proc_dir.is_dir():
            for ext in self.AUDIO_EXTENSIONS:
                candidates.extend(proc_dir.rglob(f"*{ext}"))

        # 如果没有预处理切片，从 raw 目录找（原始音频）
        if not candidates:
            raw_dir = RAW_DIR / name
            if raw_dir.is_dir():
                for ext in self.AUDIO_EXTENSIONS:
                    candidates.extend(
                        f for f in raw_dir.rglob(f"*{ext}")
                        if "demucs_output" not in f.parts and "tmp" not in f.parts
                    )

        if not candidates:
            return Response(
                {"error": f"未找到 [{name}] 的音频样本"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # 随机选一个
        import random
        sample_path = random.choice(candidates)

        try:
            # 截取前 15 秒作为预览（ffmpeg 截取为 WAV）
            audio_data, content_type = self._trim_audio(str(sample_path))

            from django.http import HttpResponse
            response = HttpResponse(audio_data, content_type=content_type)
            response["Content-Disposition"] = f'inline; filename="{sample_path.stem}_preview.wav"'
            response["Cache-Control"] = "public, max-age=3600"
            return response
        except Exception as e:
            return Response(
                {"error": f"读取音频文件失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
