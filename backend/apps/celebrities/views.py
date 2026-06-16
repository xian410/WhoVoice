"""
明星列表 API
GET /api/celebrities/list/  — 返回已注册声纹的明星列表
"""
import json
from pathlib import Path
from rest_framework.views import APIView
from rest_framework.response import Response

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
FAISS_DIR = BASE_DIR / "vector_database" / "faiss_index"
METADATA_PATH = FAISS_DIR / "celebrity_metadata.json"


class CelebrityListView(APIView):
    """返回已注册声纹的明星列表"""

    def get(self, request):
        if not METADATA_PATH.exists():
            return Response({"celebrities": [], "count": 0})

        with open(METADATA_PATH, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        return Response({
            "celebrities": metadata.get("celebrities", []),
            "count": metadata.get("num_celebrities", 0),
            "embedding_dim": metadata.get("embedding_dim", 192),
        })
