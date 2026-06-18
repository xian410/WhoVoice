"""
明星列表 & 详情 API
GET /api/celebrities/list/       — 返回已注册声纹的明星列表（含头像、歌曲信息）
GET /api/celebrities/<name>/     — 返回单个明星详情
"""
import json
from pathlib import Path
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
FAISS_DIR = BASE_DIR / "vector_database" / "faiss_index"
METADATA_PATH = FAISS_DIR / "celebrity_metadata.json"
INFO_PATH = BASE_DIR / "data" / "metadata" / "celebrities_info.json"


def _load_info() -> dict:
    """加载歌手详情信息"""
    if INFO_PATH.exists():
        try:
            with open(INFO_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"singers": [], "total": 0}


def _build_info_dict(info_list: list) -> dict:
    """将歌手信息列表转为 name->info 字典"""
    return {s["name"]: s for s in info_list}


class CelebrityListView(APIView):
    """返回已注册声纹的明星列表（含头像、歌曲信息）"""

    def get(self, request):
        if not METADATA_PATH.exists():
            return Response({"celebrities": [], "count": 0})

        with open(METADATA_PATH, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        celeb_names = metadata.get("celebrities", [])
        info_data = _load_info()
        info_dict = _build_info_dict(info_data.get("singers", []))

        # 增强列表：附带头像颜色、首字母、歌曲数
        enhanced = []
        for name in celeb_names:
            if name == "test":
                continue
            info = info_dict.get(name, {})
            enhanced.append({
                "name": name,
                "avatar_color": info.get("avatar_color", "#1a1a2e"),
                "initial": info.get("initial", name[0] if name else "?"),
                "video_count": info.get("video_count", 0),
                "slice_count": info.get("slice_count", 0),
                "has_songs": bool(info.get("representative_songs")),
            })

        return Response({
            "celebrities": enhanced,
            "count": len(enhanced),
        })


class CelebrityDetailView(APIView):
    """返回单个明星详情"""

    def get(self, request, name):
        # 检查是否在已注册列表中
        if not METADATA_PATH.exists():
            return Response({"error": "声纹库未初始化"}, status=status.HTTP_404_NOT_FOUND)

        with open(METADATA_PATH, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        if name not in metadata.get("celebrities", []):
            return Response({"error": f"未找到 [{name}]"}, status=status.HTTP_404_NOT_FOUND)

        # 加载歌手详情
        info_data = _load_info()
        info_dict = _build_info_dict(info_data.get("singers", []))
        info = info_dict.get(name, {})

        # 加载 B站元数据（歌曲列表）
        bilibili_path = BASE_DIR / "data" / "metadata" / f"{name}_bilibili.json"
        songs = []
        if bilibili_path.exists():
            try:
                with open(bilibili_path, "r", encoding="utf-8") as f:
                    records = json.load(f)
                for i, rec in enumerate(records):
                    songs.append({
                        "index": i,
                        "title": rec.get("title", ""),
                        "url": rec.get("url", ""),
                        "duration": rec.get("duration", 0),
                    })
            except Exception:
                pass

        # 统计切片数
        proc_dir = BASE_DIR / "data" / "processed" / name
        slice_count = 0
        if proc_dir.is_dir():
            slice_count = len(list(proc_dir.rglob("*.wav")))

        return Response({
            "name": name,
            "avatar_color": info.get("avatar_color", "#1a1a2e"),
            "initial": info.get("initial", name[0] if name else "?"),
            "video_count": info.get("video_count", 0),
            "slice_count": slice_count,
            "representative_songs": info.get("representative_songs", []),
            "spk_id": info.get("spk_id", ""),
            "songs": songs[:20],  # 最多返回20首
        })
