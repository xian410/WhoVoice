"""
明星列表 & 详情 API
GET /api/celebrities/list/       — 返回已注册声纹的明星列表（含头像、歌曲信息）
GET /api/celebrities/<name>/     — 返回单个明星详情
"""
import json
import re
import urllib.parse
from pathlib import Path
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
FAISS_DIR = BASE_DIR / "vector_database" / "faiss_index"
METADATA_PATH = FAISS_DIR / "celebrity_metadata.json"
INFO_PATH = BASE_DIR / "data" / "metadata" / "celebrities_info.json"
METADATA_DIR = BASE_DIR / "data" / "metadata"

# 平台显示配置
PLATFORM_META = {
    "kuwo_music": {"label": "酷我音乐", "icon": "🎵", "color": "#ff6b35"},
    "bilibili":    {"label": "B站",      "icon": "📺", "color": "#00a1d6"},
    "qq_music":   {"label": "QQ音乐",   "icon": "🎶", "color": "#31c27c"},
}

# 搜索链接模板
SEARCH_LINKS = {
    "kuwo":     {"label": "酷我音乐", "url": "https://www.kuwo.cn/search/list?key={q}"},
    "bilibili": {"label": "Bilibili", "url": "https://search.bilibili.com/all?keyword={q}"},
    "qq_music": {"label": "QQ音乐",   "url": "https://y.qq.com/portal/search.html#page=1&searchid=1&remoteplace=txt.yqq.top&t=song&w={q}"},
    "netease":  {"label": "网易云音乐", "url": "https://music.163.com/#/search/m/?s={q}&type=1"},
}


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
            return Response({"celebrities": [], "count": 0, "debug_path": str(METADATA_PATH)})

        with open(METADATA_PATH, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        celeb_names = metadata.get("celebrities", [])
        info_data = _load_info()
        info_dict = _build_info_dict(info_data.get("singers", []))

        # DEBUG
        import sys
        print(f"[DEBUG] METADATA_PATH={METADATA_PATH}", file=sys.stderr)
        print(f"[DEBUG] celeb_names count={len(celeb_names)}", file=sys.stderr)
        print(f"[DEBUG] info_dict count={len(info_dict)}", file=sys.stderr)

        # 增强列表：附带头像、简介、首字母、歌曲数
        enhanced = []
        for name in celeb_names:
            if name == "test":
                continue
            info = info_dict.get(name, {})
            enhanced.append({
                "name": name,
                "avatar_color": info.get("avatar_color", "#1a1a2e"),
                "avatar_url": info.get("avatar_url", ""),
                "initial": info.get("initial", name[0] if name else "?"),
                "video_count": info.get("video_count", 0),
                "slice_count": info.get("slice_count", 0),
                "has_songs": bool(info.get("representative_songs")),
                "bio": (info.get("bio", "") or "")[:120],
                "genre": info.get("genre", ""),
                "nationality": info.get("nationality", ""),
            })

        return Response({
            "celebrities": enhanced,
            "count": len(enhanced),
            "debug": {"path": str(METADATA_PATH), "meta_count": len(celeb_names), "info_count": len(info_dict)},
        })


class CelebrityDetailView(APIView):
    """返回单个明星详情（含多平台歌曲、外部链接、头像等）"""

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

        # 加载所有平台的元数据歌曲
        all_songs = []
        platform_counts = {}
        for platform_key, platform_info in PLATFORM_META.items():
            meta_path = METADATA_DIR / f"{name}_{platform_key}.json"
            if not meta_path.exists():
                continue
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    records = json.load(f)
                platform_counts[platform_key] = len(records)
                for i, rec in enumerate(records):
                    all_songs.append({
                        "index": len(all_songs),
                        "title": rec.get("title", ""),
                        "url": rec.get("url", ""),
                        "duration": rec.get("duration", 0),
                        "platform": platform_key,
                        "platform_label": platform_info["label"],
                        "platform_icon": platform_info["icon"],
                        "platform_color": platform_info["color"],
                    })
            except Exception:
                pass

        # 统计切片数
        proc_dir = BASE_DIR / "data" / "processed" / name
        slice_count = 0
        if proc_dir.is_dir():
            slice_count = len(list(proc_dir.rglob("*.wav")))

        # 构建外部跳转链接
        encoded_name = urllib.parse.quote(name)
        external_links = []
        for link_key, link_cfg in SEARCH_LINKS.items():
            external_links.append({
                "platform": link_key,
                "label": link_cfg["label"],
                "url": link_cfg["url"].format(q=encoded_name),
            })

        # 头像 URL — 优先使用真实头像，否则回退到 DiceBear 生成
        real_avatar = info.get("avatar_url", "")
        if real_avatar:
            avatar_url = real_avatar
        else:
            avatar_style = "initials"  # 首字母风格
            avatar_url = (
                f"https://api.dicebear.com/9.x/{avatar_style}/svg"
                f"?seed={encoded_name}"
                f"&backgroundColor={info.get('avatar_color', '#1a1a2e').lstrip('#')}"
                f"&textColor=ffffff"
                f"&fontSize=42"
            )

        # 代表作（从 info 获取，清理标题）
        rep_songs = info.get("representative_songs", [])

        # 平台统计信息
        platforms = []
        for pk, pc in platform_counts.items():
            pm = PLATFORM_META.get(pk, {})
            platforms.append({
                "key": pk,
                "label": pm.get("label", pk),
                "icon": pm.get("icon", ""),
                "color": pm.get("color", "#666"),
                "count": pc,
            })

        return Response({
            "name": name,
            "avatar_color": info.get("avatar_color", "#1a1a2e"),
            "avatar_url": avatar_url,
            "initial": info.get("initial", name[0] if name else "?"),
            "video_count": info.get("video_count", 0),
            "slice_count": slice_count,
            "total_songs": len(all_songs),
            "representative_songs": rep_songs,
            "spk_id": info.get("spk_id", ""),
            "bio": info.get("bio", ""),
            "genre": info.get("genre", ""),
            "nationality": info.get("nationality", ""),
            "birth_date": info.get("birth_date", ""),
            "info_source": info.get("info_source", ""),
            "songs": all_songs[:30],
            "platforms": platforms,
            "platform_counts": platform_counts,
            "external_links": external_links,
        })


# ─────────────────────────────────────────────
# 热门歌词模板 API
# ─────────────────────────────────────────────

LYRICS_PATH = BASE_DIR / "data" / "lyrics" / "famous_lines.json"


class LyricsTemplateView(APIView):
    """
    返回热门歌曲的经典歌词句子，供用户录音时选择
    GET /api/celebrities/lyrics-templates/
    """

    def get(self, request):
        if not LYRICS_PATH.exists():
            return Response({"lyrics": [], "count": 0})

        try:
            with open(LYRICS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return Response({"lyrics": [], "count": 0})

        lyrics = data.get("lyrics", [])

        # 支持按歌手筛选
        singer = request.query_params.get("singer", "")
        if singer:
            lyrics = [l for l in lyrics if l["singer"] == singer]

        # 支持按情绪筛选
        mood = request.query_params.get("mood", "")
        if mood:
            lyrics = [l for l in lyrics if l["mood"] == mood]

        return Response({
            "lyrics": lyrics,
            "count": len(lyrics),
            "singers": sorted(set(l["singer"] for l in lyrics)),
        })
