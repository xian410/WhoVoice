"""
WhoVoice 主 URL 配置
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/accounts/", include("apps.accounts.urls")),
    path("api/celebrities/", include("apps.celebrities.urls")),
    path("api/voice-matching/", include("apps.voice_matching.urls")),
]
