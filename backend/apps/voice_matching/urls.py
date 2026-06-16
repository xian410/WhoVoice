from django.urls import path
from .views import VoiceMatchView

urlpatterns = [
    path("match/", VoiceMatchView.as_view(), name="voice-match"),
]
