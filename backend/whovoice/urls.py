"""
WhoVoice 主 URL 配置
"""

from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/accounts/", include("apps.accounts.urls")),
    path("api/celebrities/", include("apps.celebrities.urls")),
    path("api/voice-matching/", include("apps.voice_matching.urls")),
]

# SPA 兜底：所有非 API 路径返回 index.html（让 Vue Router 处理路由）
urlpatterns += [
    re_path(r"^.*$", TemplateView.as_view(template_name="index.html")),
]
