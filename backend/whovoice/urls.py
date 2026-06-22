"""
WhoVoice 主 URL 配置
"""

from django.contrib import admin
from django.conf import settings
from django.urls import path, include, re_path
from django.views.generic import TemplateView
from django.views.static import serve

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/accounts/", include("apps.accounts.urls")),
    path("api/celebrities/", include("apps.celebrities.urls")),
    path("api/voice-matching/", include("apps.voice_matching.urls")),
    # 提供 Vue 构建产物的静态文件
    re_path(r"^assets/(?P<path>.*)$", serve, {
        "document_root": settings.BASE_DIR.parent / "frontend" / "dist" / "assets",
    }),
    # SPA 兜底：所有非 API / 非静态路径返回 index.html
    re_path(r"^.*$", TemplateView.as_view(template_name="index.html")),
]
